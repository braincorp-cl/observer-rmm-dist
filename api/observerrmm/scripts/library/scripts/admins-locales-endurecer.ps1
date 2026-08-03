<#
.SYNOPSIS
    Deshabilita las cuentas de administrador local en equipos unidos a dominio o Entra ID.

.DESCRIPTION
    En un equipo unido a un dominio las cuentas de administrador local son
    superficie de ataque: nadie las usa para trabajar, pero sirven para persistir.
    Este script las deshabilita, con tres frenos deliberados que el original del
    catálogo no tenía:

      1. Por defecto solo INFORMA (modo 'estado'). Hay que pedir 'aplicar' explícito.
      2. Nunca toca la cuenta Administrador integrada (RID 500) salvo que se pase
         -IncluirIntegrada. Es el acceso de emergencia si se rompe la confianza con
         el dominio, y deshabilitarla junto con todo lo demás es la forma clásica de
         quedarse afuera de un equipo remoto.
      3. Si el equipo NO está unido a dominio ni a Entra ID, se niega a actuar: ahí
         las cuentas locales son el único acceso que existe.

    No toca cuentas de dominio ni cuentas de servicio que no sean administradoras
    locales.

.PARAMETER Modo
    estado (por defecto, solo informa) o aplicar.

.PARAMETER Excluir
    Nombres de cuenta a dejar intactas, separados por coma.

.PARAMETER IncluirIntegrada
    Incluye la cuenta Administrador integrada (RID 500). Usar con cuidado.

.EXAMPLE
    admins-locales-endurecer.ps1
    admins-locales-endurecer.ps1 -Modo aplicar
    admins-locales-endurecer.ps1 -Modo aplicar -Excluir "soporte,respaldo"
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "aplicar")]
    [string]$Modo = "estado",

    [string]$Excluir = "",

    [switch]$IncluirIntegrada
)

$ErrorActionPreference = "Stop"

$excluidos = @()
if ($Excluir) {
    $excluidos = $Excluir.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

Write-Output "== Pertenencia a dominio =="

$unidoDominio = $false
$unidoEntra = $false

try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    $unidoDominio = $sistema.PartOfDomain
    Write-Output "  unido a dominio AD:  $unidoDominio"
    if ($unidoDominio) {
        Write-Output "  dominio:             $($sistema.Domain)"
    }
}
catch {
    Write-Output "  No se pudo consultar Win32_ComputerSystem: $($_.Exception.Message)"
}

# dsregcmd es la fuente autoritativa para Entra ID (ex Azure AD). AzureAdJoined
# es unión de dispositivo; WorkplaceJoined es solo registro de usuario y NO
# equivale a estar administrado, así que no cuenta como respaldo de acceso.
try {
    $dsreg = & dsregcmd /status 2>$null
    if ($dsreg) {
        $lineaEntra = $dsreg | Select-String -Pattern "AzureAdJoined\s*:\s*(\w+)" | Select-Object -First 1
        if ($lineaEntra -and $lineaEntra.Matches[0].Groups[1].Value -eq "YES") {
            $unidoEntra = $true
        }
    }
    Write-Output "  unido a Entra ID:    $unidoEntra"
}
catch {
    Write-Output "  unido a Entra ID:    no se pudo determinar (dsregcmd no disponible)"
}

if (-not ($unidoDominio -or $unidoEntra)) {
    Write-Output ""
    Write-Output "El equipo NO está unido a dominio ni a Entra ID."
    Write-Output "Deshabilitar los administradores locales lo dejaría sin ningún acceso"
    Write-Output "administrativo. No se hace nada."
    exit 0
}

Write-Output ""
Write-Output "== Administradores locales =="

try {
    $miembros = @(Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop)
}
catch {
    # En Windows en español el grupo se llama "Administradores". Se resuelve por SID
    # conocido (S-1-5-32-544) para no depender del idioma del sistema.
    try {
        $grupo = Get-LocalGroup -SID "S-1-5-32-544" -ErrorAction Stop
        $miembros = @(Get-LocalGroupMember -Group $grupo.Name -ErrorAction Stop)
    }
    catch {
        Write-Output "  No se pudo enumerar el grupo de administradores: $($_.Exception.Message)"
        exit 1
    }
}

$candidatos = New-Object System.Collections.ArrayList

foreach ($miembro in $miembros) {
    # Solo cuentas LOCALES: los miembros de dominio tienen ObjectClass User pero
    # PrincipalSource Domain o AzureAD, y no se tocan.
    if ($miembro.ObjectClass -ne "User") { continue }
    if ($miembro.PrincipalSource -ne "Local") {
        Write-Output "  (dominio) $($miembro.Name) — no se toca"
        continue
    }

    $nombreCorto = $miembro.Name.Split("\")[-1]

    try {
        $cuenta = Get-LocalUser -Name $nombreCorto -ErrorAction Stop
    }
    catch {
        Write-Output "  $nombreCorto — no se pudo leer la cuenta, se omite"
        continue
    }

    $esIntegrada = $cuenta.SID.Value -match "-500$"
    $estaExcluida = $excluidos -contains $nombreCorto

    $motivo = ""
    if ($esIntegrada -and -not $IncluirIntegrada) {
        $motivo = "cuenta integrada (RID 500) — protegida, usá -IncluirIntegrada para incluirla"
    }
    elseif ($estaExcluida) {
        $motivo = "excluida por parámetro"
    }
    elseif (-not $cuenta.Enabled) {
        $motivo = "ya está deshabilitada"
    }

    Write-Output ""
    Write-Output "  $nombreCorto"
    Write-Output "    SID:          $($cuenta.SID)"
    Write-Output "    habilitada:   $($cuenta.Enabled)"
    Write-Output "    último logon: $(if ($cuenta.LastLogon) { $cuenta.LastLogon } else { 'nunca' })"
    if ($motivo) {
        Write-Output "    acción:       NO se deshabilita ($motivo)"
    }
    else {
        Write-Output "    acción:       se deshabilitaría"
        [void]$candidatos.Add($cuenta)
    }
}

Write-Output ""
Write-Output "== Resultado =="

if ($candidatos.Count -eq 0) {
    Write-Output "  No hay cuentas de administrador local que deshabilitar."
    exit 0
}

if ($Modo -eq "estado") {
    Write-Output "  $($candidatos.Count) cuenta(s) se deshabilitarían."
    Write-Output "  Modo 'estado': no se modificó nada. Volvé a correr con -Modo aplicar."
    exit 0
}

$deshabilitadas = 0
$errores = 0

foreach ($cuenta in $candidatos) {
    try {
        Disable-LocalUser -Name $cuenta.Name -ErrorAction Stop
        # Verificación por efecto: releer la cuenta en vez de confiar en el cmdlet.
        $verificada = Get-LocalUser -Name $cuenta.Name -ErrorAction Stop
        if ($verificada.Enabled) {
            Write-Output "  FALLA: $($cuenta.Name) sigue habilitada tras deshabilitarla."
            $errores++
        }
        else {
            Write-Output "  deshabilitada: $($cuenta.Name)"
            $deshabilitadas++
        }
    }
    catch {
        Write-Output "  ERROR con $($cuenta.Name): $($_.Exception.Message)"
        $errores++
    }
}

Write-Output ""
Write-Output "  $deshabilitadas deshabilitada(s), $errores con error."

if ($errores -gt 0) { exit 1 }
exit 0
