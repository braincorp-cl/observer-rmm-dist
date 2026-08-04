<#
.SYNOPSIS
    Deshabilita las cuentas de administrador local en equipos unidos a dominio o Entra ID.

.DESCRIPTION
    En un equipo unido a un dominio las cuentas de administrador local son
    superficie de ataque: nadie las usa para trabajar, pero sirven para persistir.
    Este script las deshabilita, con tres frenos deliberados que el original del
    catalogo no tenia:

      1. Por defecto solo INFORMA (modo 'estado'). Hay que pedir 'aplicar' explicito.
      2. Nunca toca la cuenta Administrador integrada (RID 500) salvo que se pase
         -IncluirIntegrada. Es el acceso de emergencia si se rompe la confianza con
         el dominio, y deshabilitarla junto con todo lo demas es la forma clasica de
         quedarse afuera de un equipo remoto.
      3. Si el equipo NO esta unido a dominio ni a Entra ID, se niega a actuar: ahi
         las cuentas locales son el unico acceso que existe.

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

# SID del grupo integrado de administradores locales. Es el mismo en toda instalacion
# de Windows y en todo idioma; el NOMBRE del grupo no lo es.
$SID_ADMINISTRADORES = "S-1-5-32-544"

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
# es union de dispositivo; WorkplaceJoined es solo registro de usuario y NO
# equivale a estar administrado, asi que no cuenta como respaldo de acceso.
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
    Write-Output "El equipo NO esta unido a dominio ni a Entra ID."
    Write-Output "Deshabilitar los administradores locales lo dejaria sin ningun acceso"
    Write-Output "administrativo. No se hace nada."
    exit 0
}

Write-Output ""
Write-Output "== Administradores locales =="

# El grupo se resuelve SIEMPRE por SID, nunca por nombre: se llama "Administrators" en
# un Windows en ingles y "Administradores" en uno en espanol, pero su SID es
# S-1-5-32-544 en los dos. Buscar por nombre y dejar el SID de plan B invierte el
# orden: convierte en excepcion el caso que en una flota chilena es la mitad del parque.
try {
    $grupo = Get-LocalGroup -SID $SID_ADMINISTRADORES -ErrorAction Stop
    $miembros = @(Get-LocalGroupMember -Group $grupo.Name -ErrorAction Stop)
}
catch {
    Write-Output "  No se pudo enumerar el grupo de administradores: $($_.Exception.Message)"
    exit 1
}

$candidatos = New-Object System.Collections.ArrayList

foreach ($miembro in $miembros) {
    # Solo cuentas LOCALES: los miembros de dominio tienen ObjectClass User pero
    # PrincipalSource Domain o AzureAD, y no se tocan.
    if ($miembro.ObjectClass -ne "User") { continue }
    if ($miembro.PrincipalSource -ne "Local") {
        Write-Output "  (dominio) $($miembro.Name) - no se toca"
        continue
    }

    $nombreCorto = $miembro.Name.Split("\")[-1]

    try {
        $cuenta = Get-LocalUser -Name $nombreCorto -ErrorAction Stop
    }
    catch {
        Write-Output "  $nombreCorto - no se pudo leer la cuenta, se omite"
        continue
    }

    $esIntegrada = $cuenta.SID.Value -match "-500$"
    $estaExcluida = $excluidos -contains $nombreCorto

    $motivo = ""
    if ($esIntegrada -and -not $IncluirIntegrada) {
        $motivo = "cuenta integrada (RID 500) - protegida, usa -IncluirIntegrada para incluirla"
    }
    elseif ($estaExcluida) {
        $motivo = "excluida por parametro"
    }
    elseif (-not $cuenta.Enabled) {
        $motivo = "ya esta deshabilitada"
    }

    Write-Output ""
    Write-Output "  $nombreCorto"
    Write-Output "    SID:          $($cuenta.SID)"
    Write-Output "    habilitada:   $($cuenta.Enabled)"
    Write-Output "    ultimo logon: $(if ($cuenta.LastLogon) { $cuenta.LastLogon } else { 'nunca' })"
    if ($motivo) {
        Write-Output "    accion:       NO se deshabilita ($motivo)"
    }
    else {
        Write-Output "    accion:       se deshabilitaria"
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
    Write-Output "  $($candidatos.Count) cuenta(s) se deshabilitarian."
    Write-Output "  Modo 'estado': no se modifico nada. Volve a correr con -Modo aplicar."
    exit 0
}

$deshabilitadas = 0
$errores = 0

foreach ($cuenta in $candidatos) {
    try {
        Disable-LocalUser -Name $cuenta.Name -ErrorAction Stop
        # Verificacion por efecto: releer la cuenta en vez de confiar en el cmdlet.
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
