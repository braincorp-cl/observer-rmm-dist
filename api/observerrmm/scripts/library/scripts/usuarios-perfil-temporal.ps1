<#
.SYNOPSIS
    Detecta usuarios que entraron con un perfil temporal.

.DESCRIPTION
    Solo LEE. Cuando Windows no puede cargar el perfil de un usuario, lo entra con
    un perfil temporal: el escritorio aparece vacio, los documentos "desaparecen" y
    todo lo que el usuario haga en esa sesion se pierde al cerrarla. El usuario
    reporta "perdi mis archivos" y el equipo se ve perfectamente sano en el panel.

    Busca las dos evidencias que deja el problema:

      1. Perfiles con sufijo .bak en la lista de perfiles del registro. Windows
         renombra el perfil danado agregandole .bak y crea uno nuevo; si existen a
         la vez el SID y el SID.bak, ese usuario esta usando un perfil temporal.
      2. Eventos 1511, 1515 y 1521 del proveedor User Profile Service.

    Sale con 1 si detecta algun perfil temporal, para que sirva como check.

.PARAMETER Dias
    Ventana en dias para buscar eventos. Por defecto 7.

.EXAMPLE
    usuarios-perfil-temporal.ps1
    usuarios-perfil-temporal.ps1 -Dias 30
#>

[CmdletBinding()]
param(
    [int]$Dias = 7
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

$ErrorActionPreference = "Continue"

$rutaPerfiles = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
$afectados = New-Object System.Collections.ArrayList

Write-Output "== Perfiles registrados =="

try {
    $claves = @(Get-ChildItem -Path $rutaPerfiles -ErrorAction Stop)
}
catch {
    Write-Output "  No se pudo leer la lista de perfiles: $($_.Exception.Message)"
    exit 1
}

$sids = @{}
foreach ($clave in $claves) {
    $nombreClave = Split-Path $clave.Name -Leaf
    try {
        $datos = Get-ItemProperty -Path $clave.PSPath -ErrorAction Stop
    }
    catch {
        continue
    }
    $sids[$nombreClave] = $datos.ProfileImagePath
}

foreach ($nombreClave in ($sids.Keys | Sort-Object)) {
    if ($nombreClave -notlike "*.bak") { continue }

    $sidBase = $nombreClave -replace "\.bak$", ""
    $rutaRespaldo = $sids[$nombreClave]

    # Se traduce el SID a nombre de cuenta: el SID crudo no le dice nada a quien
    # atiende el ticket.
    $cuenta = $sidBase
    try {
        $objetoSid = New-Object System.Security.Principal.SecurityIdentifier($sidBase)
        $cuenta = $objetoSid.Translate([System.Security.Principal.NTAccount]).Value
    }
    catch {
        # Cuenta borrada o SID de otro dominio: se informa el SID.
        Write-Verbose $_.Exception.Message
    }

    Write-Output ""
    Write-Output "  PERFIL TEMPORAL DETECTADO"
    Write-Output "    cuenta:            $cuenta"
    Write-Output "    SID:               $sidBase"
    Write-Output "    perfil danado en:  $rutaRespaldo"

    if ($sids.ContainsKey($sidBase)) {
        Write-Output "    perfil en uso:     $($sids[$sidBase])"
        Write-Output "    diagnostico:       existen el perfil original (.bak) y uno nuevo:"
        Write-Output "                       el usuario esta trabajando sobre un perfil temporal."
    }
    else {
        Write-Output "    diagnostico:       hay un .bak sin perfil activo asociado."
        Write-Output "                       Resto de un problema anterior, ya sin sesion afectada."
    }

    [void]$afectados.Add($cuenta)
}

if ($afectados.Count -eq 0) {
    Write-Output "  Sin perfiles marcados como danados (.bak)."
}

Write-Output ""
Write-Output "== Eventos del servicio de perfiles (ultimos $Dias dia[s]) =="

# 1511: no se encontro el perfil local, se cargo uno temporal.
# 1515: Windows respaldo el perfil y creo uno nuevo.
# 1521: no se pudo cargar el perfil, posible problema de red o permisos.
$idsRelevantes = @(1511, 1515, 1521)

try {
    $desde = (Get-Date).AddDays(-1 * [Math]::Abs($Dias))
    $filtro = @{
        LogName   = "Application"
        Id        = $idsRelevantes
        StartTime = $desde
    }
    $eventos = @(Get-WinEvent -FilterHashtable $filtro -ErrorAction Stop)
}
catch {
    $eventos = @()
    # Get-WinEvent lanza si no hay NINGUN evento que coincida: eso no es un error,
    # es la respuesta "no hubo eventos". Solo se informa si el mensaje no es ese.
    if ($_.Exception.Message -notmatch "No events were found|No se encontraron eventos") {
        Write-Output "  No se pudieron consultar los eventos: $($_.Exception.Message)"
    }
}

if ($eventos.Count -eq 0) {
    Write-Output "  Sin eventos 1511/1515/1521 en la ventana consultada."
}
else {
    foreach ($evento in ($eventos | Sort-Object TimeCreated -Descending | Select-Object -First 20)) {
        Write-Output ""
        Write-Output "  $($evento.TimeCreated) - evento $($evento.Id)"
        $mensaje = $evento.Message
        if ($mensaje) {
            $primeraLinea = ($mensaje -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
            Write-Output "    $primeraLinea"
        }
    }
    if ($eventos.Count -gt 20) {
        Write-Output ""
        Write-Output "  (se muestran los 20 mas recientes de $($eventos.Count))"
    }
}

Write-Output ""
Write-Output "== Resultado =="

if ($afectados.Count -gt 0) {
    Write-Output "  $($afectados.Count) perfil(es) temporal(es): $($afectados -join ', ')"
    Write-Output ""
    Write-Output "  Antes de tocar nada: los archivos del usuario estan en el perfil .bak."
    Write-Output "  Cerrar la sesion sin rescatarlos pierde lo hecho en la sesion temporal."
    exit 1
}

if ($eventos.Count -gt 0) {
    Write-Output "  Sin perfiles temporales activos, pero hubo eventos del servicio de"
    Write-Output "  perfiles en la ventana consultada: revisar si fue un incidente puntual."
    exit 0
}

Write-Output "  Sin indicios de perfiles temporales."
exit 0
