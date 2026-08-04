<#
.SYNOPSIS
    Lanza un escaneo de Microsoft Defender: rapido, completo o de una ruta.

.DESCRIPTION
    Reemplaza los dos scripts separados de escaneo rapido y completo por uno con
    modo. Corre el escaneo en primer plano y espera el resultado, para que el
    timeout del script sea el que manda y la consola vea si termino.

    Un escaneo completo puede tardar horas: el timeout por defecto de este script
    es alto a proposito, pero conviene programarlo como tarea automatizada en
    ventana de mantenimiento en vez de lanzarlo a mano en horario laboral.

.PARAMETER Modo
    rapido (por defecto), completo, o ruta.

.PARAMETER Ruta
    Carpeta o archivo a escanear. Obligatorio si Modo es 'ruta'.

.EXAMPLE
    defender-escaneo.ps1
    defender-escaneo.ps1 -Modo completo
    defender-escaneo.ps1 -Modo ruta -Ruta "D:\Compartido"
#>

[CmdletBinding()]
param(
    [ValidateSet("rapido", "completo", "ruta")]
    [string]$Modo = "rapido",

    [string]$Ruta
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

if (-not (Get-Command Start-MpScan -ErrorAction SilentlyContinue)) {
    Write-Output "Microsoft Defender no esta disponible en este equipo."
    exit 1
}

try {
    $estado = Get-MpComputerStatus -ErrorAction Stop
    if ($estado.AMRunningMode -ne "Normal") {
        Write-Output "AVISO: Defender esta en modo '$($estado.AMRunningMode)'."
        Write-Output "Otro antivirus es el que protege; el escaneo puede no ser representativo."
    }
}
catch {
    Write-Output "No se pudo leer el estado de Defender, se intenta el escaneo igual."
}

if ($Modo -eq "ruta") {
    if (-not $Ruta) {
        Write-Output "El modo 'ruta' exige el parametro -Ruta."
        exit 1
    }
    if (-not (Test-Path -LiteralPath $Ruta)) {
        Write-Output "La ruta indicada no existe: $Ruta"
        exit 1
    }
}

$inicio = Get-Date
Write-Output "Iniciando escaneo '$Modo' a las $inicio..."

try {
    switch ($Modo) {
        "rapido" { Start-MpScan -ScanType QuickScan -ErrorAction Stop }
        "completo" { Start-MpScan -ScanType FullScan -ErrorAction Stop }
        "ruta" { Start-MpScan -ScanType CustomScan -ScanPath $Ruta -ErrorAction Stop }
    }
}
catch {
    Write-Output "El escaneo fallo: $($_.Exception.Message)"
    exit 1
}

$duracion = (Get-Date) - $inicio
Write-Output "Escaneo terminado. Duracion: $([int]$duracion.TotalMinutes) minuto(s)."

# Lo que importa no es que el escaneo terminara, sino que encontro. Se consulta el
# historial acotado a la ventana del escaneo que acabamos de correr.
try {
    $detecciones = @(Get-MpThreatDetection -ErrorAction Stop |
        Where-Object { $_.InitialDetectionTime -ge $inicio })

    Write-Output ""
    if ($detecciones.Count -eq 0) {
        Write-Output "Sin amenazas detectadas durante este escaneo."
    }
    else {
        Write-Output "$($detecciones.Count) amenaza(s) detectada(s) durante este escaneo:"
        foreach ($deteccion in $detecciones) {
            Write-Output ""
            Write-Output "  amenaza ID:  $($deteccion.ThreatID)"
            Write-Output "  detectada:   $($deteccion.InitialDetectionTime)"
            Write-Output "  accion ok:   $($deteccion.ActionSuccess)"
            Write-Output "  recursos:    $($deteccion.Resources -join ', ')"
        }
        exit 1
    }
}
catch {
    Write-Output "No se pudo consultar el historial de amenazas: $($_.Exception.Message)"
}

try {
    $final = Get-MpComputerStatus -ErrorAction Stop
    Write-Output ""
    if ($Modo -eq "completo") {
        Write-Output "Ultimo escaneo completo registrado: $($final.FullScanEndTime)"
    }
    else {
        Write-Output "Ultimo escaneo rapido registrado: $($final.QuickScanEndTime)"
    }
}
catch {
    # Informativo: no cambia el resultado del escaneo.
    Write-Verbose $_.Exception.Message
}

exit 0
