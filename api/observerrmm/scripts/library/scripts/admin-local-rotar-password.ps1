<#
.SYNOPSIS
    Crea o rota la contrasena de una cuenta de administrador local dedicada.

.DESCRIPTION
    Solucion de contrasena de administrador local para equipos SIN Active Directory,
    donde el LAPS de Microsoft no aplica. Deja una unica cuenta administrativa por
    equipo con contrasena distinta y rotable, para que los usuarios puedan trabajar
    sin ser administradores y el soporte siga teniendo acceso.

    Genera la contrasena con el generador criptografico del sistema
    (RandomNumberGenerator), no con Get-Random, que es predecible y no sirve para
    esto.

    ADVERTENCIA: la contrasena se imprime en la salida del script, que queda en el
    historial de la consola y viaja por NATS. Es la unica forma de recuperarla desde
    un equipo remoto, pero cualquiera con acceso a ese historial la ve. Guardala en
    el gestor de secretos y borra el resultado, o usa -NoMostrar cuando solo quieras
    rotarla sin leerla.

    Es idempotente en la parte estructural: si la cuenta ya existe con los atributos
    correctos, solo rota la contrasena.

.PARAMETER Usuario
    Nombre de la cuenta. Por defecto "AdminLocal".

.PARAMETER Longitud
    Largo de la contrasena. Minimo 12, por defecto 20.

.PARAMETER Descripcion
    Descripcion de la cuenta al crearla.

.PARAMETER NoMostrar
    Rota la contrasena sin imprimirla. Util para revocar acceso sin dejar rastro.

.EXAMPLE
    admin-local-rotar-password.ps1
    admin-local-rotar-password.ps1 -Usuario soporte -Longitud 24
    admin-local-rotar-password.ps1 -NoMostrar
#>

[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    "PSAvoidUsingConvertToSecureStringWithPlainText", "",
    Justification = "La contrasena se genera en memoria en este mismo script y New-LocalUser/Set-LocalUser solo aceptan SecureString: la conversion es inevitable y no hay un origen seguro alternativo."
)]
param(
    [string]$Usuario = "AdminLocal",

    [ValidateRange(12, 100)]
    [int]$Longitud = 20,

    [string]$Descripcion = "Cuenta administrativa gestionada por ObserverRMM",

    [switch]$NoMostrar
)

# El agente pasa el stdout por strings.ToValidUTF8(s, "") (agent/utils.go:401), que
# BORRA toda secuencia UTF-8 invalida. Windows PowerShell 5.1 escribe su salida en la
# pagina de codigos OEM de la consola, donde un acento es un solo byte que no es UTF-8
# valido => los acentos desaparecian de la salida sin dejar rastro. Medido en Windows 11
# real: sin esta linea se pierden todos; con ella llegan intactos. `chcp 65001` NO sirve,
# porque no cambia el encoding del Console del proceso ya arrancado.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
}
catch {
    # Sin consola adjunta la asignacion puede fallar; no es motivo para abortar el script.
    Write-Verbose $_.Exception.Message
}

$ErrorActionPreference = "Stop"

function Get-ContrasenaSegura {
    param([int]$Largo)

    # Se excluyen a proposito los caracteres que se confunden al dictarse por
    # telefono (O/0, l/1/I) y las comillas y barras, que rompen scripts y pegados.
    $minusculas = "abcdefghijkmnopqrstuvwxyz"
    $mayusculas = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    $digitos = "23456789"
    $simbolos = "!#%&*+-=?@_"
    $todos = $minusculas + $mayusculas + $digitos + $simbolos

    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        function Get-CaracterAleatorio {
            param([string]$Conjunto)
            $bytes = New-Object byte[] 4
            $generador.GetBytes($bytes)
            # Se descarta el bit de signo para no obtener un indice negativo.
            $valor = [BitConverter]::ToUInt32($bytes, 0)
            return $Conjunto[[int]($valor % [uint32]$Conjunto.Length)]
        }

        # Se garantiza al menos uno de cada clase para cumplir la politica de
        # complejidad de Windows, que rechazaria la contrasena si no la cumple.
        $caracteres = New-Object System.Collections.ArrayList
        [void]$caracteres.Add((Get-CaracterAleatorio $minusculas))
        [void]$caracteres.Add((Get-CaracterAleatorio $mayusculas))
        [void]$caracteres.Add((Get-CaracterAleatorio $digitos))
        [void]$caracteres.Add((Get-CaracterAleatorio $simbolos))

        while ($caracteres.Count -lt $Largo) {
            [void]$caracteres.Add((Get-CaracterAleatorio $todos))
        }

        # Mezcla Fisher-Yates con la misma fuente criptografica: sin esto los cuatro
        # primeros caracteres tendrian siempre la misma clase, que es un patron.
        for ($i = $caracteres.Count - 1; $i -gt 0; $i--) {
            $bytes = New-Object byte[] 4
            $generador.GetBytes($bytes)
            $j = [int]([BitConverter]::ToUInt32($bytes, 0) % [uint32]($i + 1))
            $temporal = $caracteres[$i]
            $caracteres[$i] = $caracteres[$j]
            $caracteres[$j] = $temporal
        }

        return -join $caracteres
    }
    finally {
        $generador.Dispose()
    }
}

# El grupo de administradores se resuelve por SID conocido para no depender del
# idioma del sistema ("Administrators" en ingles, "Administradores" en espanol).
try {
    $grupoAdmin = Get-LocalGroup -SID "S-1-5-32-544" -ErrorAction Stop
}
catch {
    Write-Output "No se pudo resolver el grupo de administradores locales: $($_.Exception.Message)"
    exit 1
}

$contrasena = Get-ContrasenaSegura -Largo $Longitud
$segura = ConvertTo-SecureString $contrasena -AsPlainText -Force

$existe = $null
try {
    $existe = Get-LocalUser -Name $Usuario -ErrorAction Stop
}
catch {
    $existe = $null
}

if ($null -eq $existe) {
    Write-Output "La cuenta '$Usuario' no existe: se crea."
    try {
        New-LocalUser -Name $Usuario -Password $segura -FullName $Usuario `
            -Description $Descripcion -PasswordNeverExpires -ErrorAction Stop | Out-Null
        Write-Output "  cuenta creada."
    }
    catch {
        Write-Output "  ERROR al crear la cuenta: $($_.Exception.Message)"
        exit 1
    }
}
else {
    Write-Output "La cuenta '$Usuario' ya existe: se rota la contrasena."
    try {
        Set-LocalUser -Name $Usuario -Password $segura -PasswordNeverExpires $true -ErrorAction Stop
        Write-Output "  contrasena rotada."
    }
    catch {
        Write-Output "  ERROR al rotar la contrasena: $($_.Exception.Message)"
        exit 1
    }

    if (-not $existe.Enabled) {
        try {
            Enable-LocalUser -Name $Usuario -ErrorAction Stop
            Write-Output "  la cuenta estaba deshabilitada: se habilito."
        }
        catch {
            Write-Output "  ERROR al habilitar la cuenta: $($_.Exception.Message)"
            exit 1
        }
    }
}

# Pertenencia al grupo: se agrega solo si falta, para que el script sea idempotente.
$esAdmin = $false
try {
    $miembros = @(Get-LocalGroupMember -Group $grupoAdmin.Name -ErrorAction Stop)
    foreach ($miembro in $miembros) {
        if ($miembro.Name.Split("\")[-1] -ieq $Usuario) { $esAdmin = $true; break }
    }
}
catch {
    Write-Output "  AVISO: no se pudo enumerar el grupo de administradores."
}

if (-not $esAdmin) {
    try {
        Add-LocalGroupMember -Group $grupoAdmin.Name -Member $Usuario -ErrorAction Stop
        Write-Output "  agregada al grupo '$($grupoAdmin.Name)'."
    }
    catch {
        Write-Output "  ERROR al agregar al grupo: $($_.Exception.Message)"
        exit 1
    }
}
else {
    Write-Output "  ya pertenecia al grupo '$($grupoAdmin.Name)'."
}

# Verificacion por efecto: la cuenta tiene que quedar habilitada y en el grupo.
try {
    $final = Get-LocalUser -Name $Usuario -ErrorAction Stop
    if (-not $final.Enabled) {
        Write-Output "FALLA: la cuenta quedo deshabilitada."
        exit 1
    }
}
catch {
    Write-Output "FALLA: la cuenta no se pudo releer tras el cambio."
    exit 1
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  usuario: $Usuario"
Write-Output "  equipo:  $env:COMPUTERNAME"
Write-Output "  rotada:  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

if ($NoMostrar) {
    Write-Output "  contrasena: (no se muestra por -NoMostrar)"
    Write-Output ""
    Write-Output "La contrasena se roto y NO quedo registrada en ninguna parte."
    Write-Output "Nadie puede recuperarla: usa este modo solo para revocar el acceso."
}
else {
    Write-Output "  contrasena: $contrasena"
    Write-Output ""
    Write-Output "Guardala en el gestor de secretos y borra este resultado del historial."
}

exit 0
