<#
.SYNOPSIS
    Gestiona las cuentas locales: listar, crear, habilitar o deshabilitar.

.DESCRIPTION
    Reemplaza los tres scripts separados del catálogo original (crear usuario,
    habilitar/deshabilitar y listar) por uno con modo.

    En modo 'listar' solo LEE y muestra, por cada cuenta local, si está habilitada,
    cuándo entró por última vez y si es administradora, que es la pregunta que en
    realidad se quiere responder cuando se pide "la lista de usuarios".

    Los grupos se resuelven por SID conocido, no por nombre, para que funcione igual
    en Windows en español y en inglés.

.PARAMETER Modo
    listar (por defecto), crear, habilitar, deshabilitar.

.PARAMETER Usuario
    Cuenta sobre la que actuar. Obligatorio salvo en modo 'listar'.

.PARAMETER Contrasena
    Contraseña para el modo 'crear'.

.PARAMETER NombreCompleto
    Nombre completo para el modo 'crear'.

.PARAMETER Grupo
    Grupo al que agregar la cuenta creada. Por defecto el grupo de usuarios
    (S-1-5-32-545). Usar "administradores" para el grupo de administradores.

.EXAMPLE
    usuarios-locales.ps1
    usuarios-locales.ps1 -Modo crear -Usuario kiosco -Contrasena "..." -NombreCompleto "Kiosco recepción"
    usuarios-locales.ps1 -Modo deshabilitar -Usuario extemporal
#>

[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    "PSAvoidUsingConvertToSecureStringWithPlainText", "",
    Justification = "La contrasena llega como argumento del script porque el operador la define al crear la cuenta; New-LocalUser solo acepta SecureString."
)]
param(
    [ValidateSet("listar", "crear", "habilitar", "deshabilitar")]
    [string]$Modo = "listar",

    [string]$Usuario,

    [string]$Contrasena,

    [string]$NombreCompleto,

    [string]$Grupo = "usuarios"
)

$ErrorActionPreference = "Stop"

$SID_ADMINISTRADORES = "S-1-5-32-544"
$SID_USUARIOS = "S-1-5-32-545"

function Get-GrupoPorSid {
    param([string]$Sid)
    try {
        return Get-LocalGroup -SID $Sid -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Get-AdministradorLocal {
    $grupo = Get-GrupoPorSid $SID_ADMINISTRADORES
    if (-not $grupo) { return @() }
    try {
        return @(Get-LocalGroupMember -Group $grupo.Name -ErrorAction Stop |
            ForEach-Object { $_.Name.Split("\")[-1] })
    }
    catch {
        return @()
    }
}

if ($Modo -eq "listar") {
    $administradores = Get-AdministradorLocal

    try {
        $cuentas = @(Get-LocalUser -ErrorAction Stop)
    }
    catch {
        Write-Output "No se pudieron enumerar las cuentas locales: $($_.Exception.Message)"
        exit 1
    }

    $habilitadas = 0
    foreach ($cuenta in ($cuentas | Sort-Object Name)) {
        if ($cuenta.Enabled) { $habilitadas++ }
        $esAdmin = $administradores -contains $cuenta.Name

        Write-Output ""
        Write-Output "$($cuenta.Name)"
        Write-Output "  habilitada:       $($cuenta.Enabled)"
        Write-Output "  administradora:   $(if ($esAdmin) { 'SÍ' } else { 'no' })"
        Write-Output "  nombre completo:  $(if ($cuenta.FullName) { $cuenta.FullName } else { '(sin definir)' })"
        Write-Output "  último logon:     $(if ($cuenta.LastLogon) { $cuenta.LastLogon } else { 'nunca' })"
        Write-Output "  contraseña expira: $(if ($cuenta.PasswordExpires) { $cuenta.PasswordExpires } else { 'no expira' })"
        Write-Output "  último cambio:    $(if ($cuenta.PasswordLastSet) { $cuenta.PasswordLastSet } else { 'nunca' })"
        Write-Output "  SID:              $($cuenta.SID)"
    }

    Write-Output ""
    Write-Output "Total: $($cuentas.Count) cuenta(s) local(es), $habilitadas habilitada(s)."
    exit 0
}

if (-not $Usuario) {
    Write-Output "El modo '$Modo' exige el parámetro -Usuario."
    exit 1
}

$existe = $null
try {
    $existe = Get-LocalUser -Name $Usuario -ErrorAction Stop
}
catch {
    $existe = $null
}

switch ($Modo) {
    "crear" {
        if ($existe) {
            Write-Output "La cuenta '$Usuario' ya existe. No se modifica."
            Write-Output "Para cambiar su contraseña usá el script de rotación de admin local."
            exit 0
        }
        if (-not $Contrasena) {
            Write-Output "El modo 'crear' exige el parámetro -Contrasena."
            exit 1
        }

        $sidGrupo = if ($Grupo -imatch "^admin") { $SID_ADMINISTRADORES } else { $SID_USUARIOS }
        $grupoDestino = Get-GrupoPorSid $sidGrupo
        if (-not $grupoDestino) {
            Write-Output "No se pudo resolver el grupo destino (SID $sidGrupo)."
            exit 1
        }

        $segura = ConvertTo-SecureString $Contrasena -AsPlainText -Force
        try {
            $argumentos = @{
                Name        = $Usuario
                Password    = $segura
                ErrorAction = "Stop"
            }
            if ($NombreCompleto) { $argumentos["FullName"] = $NombreCompleto }
            New-LocalUser @argumentos | Out-Null
            Write-Output "Cuenta '$Usuario' creada."
        }
        catch {
            Write-Output "ERROR al crear la cuenta: $($_.Exception.Message)"
            Write-Output "Si menciona la política de contraseñas, la contraseña no cumple"
            Write-Output "los requisitos de complejidad o longitud del equipo."
            exit 1
        }

        try {
            Add-LocalGroupMember -Group $grupoDestino.Name -Member $Usuario -ErrorAction Stop
            Write-Output "Agregada al grupo '$($grupoDestino.Name)'."
        }
        catch {
            Write-Output "ERROR al agregar al grupo: $($_.Exception.Message)"
            exit 1
        }
    }

    "habilitar" {
        if (-not $existe) {
            Write-Output "La cuenta '$Usuario' no existe."
            exit 1
        }
        if ($existe.Enabled) {
            Write-Output "Nada que hacer: '$Usuario' ya estaba habilitada."
            exit 0
        }
        try {
            Enable-LocalUser -Name $Usuario -ErrorAction Stop
            Write-Output "Cuenta '$Usuario' habilitada."
        }
        catch {
            Write-Output "ERROR: $($_.Exception.Message)"
            exit 1
        }
    }

    "deshabilitar" {
        if (-not $existe) {
            Write-Output "La cuenta '$Usuario' no existe."
            exit 1
        }
        if (-not $existe.Enabled) {
            Write-Output "Nada que hacer: '$Usuario' ya estaba deshabilitada."
            exit 0
        }

        # Freno: no dejar el equipo sin ningún administrador habilitado. Es el
        # escenario en que un "deshabilitar la cuenta X" deja el equipo inaccesible.
        $administradores = Get-AdministradorLocal
        if ($administradores -contains $Usuario) {
            $otrosHabilitados = 0
            foreach ($nombre in $administradores) {
                if ($nombre -ieq $Usuario) { continue }
                try {
                    $otra = Get-LocalUser -Name $nombre -ErrorAction Stop
                    if ($otra.Enabled) { $otrosHabilitados++ }
                }
                catch {
                    # Los miembros de dominio no son cuentas locales: cuentan como acceso.
                    $otrosHabilitados++
                }
            }
            if ($otrosHabilitados -eq 0) {
                Write-Output "ABORTADO: '$Usuario' es el único administrador habilitado."
                Write-Output "Deshabilitarla dejaría el equipo sin acceso administrativo."
                exit 1
            }
        }

        try {
            Disable-LocalUser -Name $Usuario -ErrorAction Stop
            Write-Output "Cuenta '$Usuario' deshabilitada."
        }
        catch {
            Write-Output "ERROR: $($_.Exception.Message)"
            exit 1
        }
    }
}

# Verificación por efecto para los modos que escriben.
try {
    $final = Get-LocalUser -Name $Usuario -ErrorAction Stop
    Write-Output ""
    Write-Output "Estado verificado: '$($final.Name)' habilitada=$($final.Enabled)"
}
catch {
    Write-Output "FALLA: la cuenta no se pudo releer tras el cambio."
    exit 1
}

exit 0
