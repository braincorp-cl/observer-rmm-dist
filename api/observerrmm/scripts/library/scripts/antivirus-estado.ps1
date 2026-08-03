<#
.SYNOPSIS
    Estado consolidado del antivirus: qué producto protege el equipo y si está sano.

.DESCRIPTION
    Solo LEE. Responde de una sola pasada lo que antes pedía dos scripts: qué
    antivirus están registrados en el Centro de seguridad de Windows, y —si el que
    manda es Defender— si su protección está activa, sus firmas al día y si hubo
    amenazas recientes.

    El estado de cada producto sale de SecurityCenter2, donde `productState` es un
    entero cuyo byte del medio indica si la protección está encendida y el byte
    bajo si las firmas están vencidas. Decodificarlo es la única forma de saber si
    un antivirus de terceros está realmente protegiendo o solo instalado.

    Sale con 1 si ningún producto tiene la protección activa, o si las firmas están
    vencidas, para que sirva como check.

.PARAMETER DiasAmenazas
    Ventana en días para el reporte de amenazas de Defender. Por defecto 1.

.EXAMPLE
    antivirus-estado.ps1
    antivirus-estado.ps1 -DiasAmenazas 7
#>

[CmdletBinding()]
param(
    [int]$DiasAmenazas = 1
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

$problemas = New-Object System.Collections.ArrayList

function Add-Problema {
    param([string]$Texto)
    [void]$problemas.Add($Texto)
}

Write-Output "== Productos registrados en el Centro de seguridad =="

$productos = @()
try {
    $productos = @(Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop)
}
catch {
    Write-Output "  No se pudo consultar SecurityCenter2: $($_.Exception.Message)"
    Write-Output "  Windows Server no expone este namespace: se evalúa solo Defender."
}

$algunoActivo = $false

foreach ($producto in $productos) {
    $estado = $producto.productState

    # productState es una máscara de 3 bytes. El byte del medio (0x00FF00) indica
    # el estado del escaneo en tiempo real: 0x10 y 0x11 = activo. El byte bajo
    # (0x0000FF) indica las firmas: 0x00 = al día, 0x10 = vencidas.
    $bytesProteccion = ($estado -band 0x0000FF00) -shr 8
    $bytesFirmas = $estado -band 0x000000FF

    $proteccionActiva = ($bytesProteccion -eq 0x10) -or ($bytesProteccion -eq 0x11)
    $firmasAlDia = $bytesFirmas -eq 0x00

    if ($proteccionActiva) { $algunoActivo = $true }

    Write-Output ""
    Write-Output "  $($producto.displayName)"
    Write-Output "    protección en tiempo real: $(if ($proteccionActiva) { 'ACTIVA' } else { 'INACTIVA' })"
    Write-Output "    firmas:                    $(if ($firmasAlDia) { 'al día' } else { 'VENCIDAS' })"
    Write-Output "    productState:              $estado (0x$($estado.ToString('X6')))"
    if ($producto.pathToSignedProductExe) {
        Write-Output "    ejecutable:                $($producto.pathToSignedProductExe)"
    }

    if (-not $firmasAlDia) {
        Add-Problema "firmas vencidas en $($producto.displayName)"
    }
}

if ($productos.Count -eq 0) {
    Write-Output "  (ninguno reportado)"
}

Write-Output ""
Write-Output "== Microsoft Defender =="

$defenderPresente = $null -ne (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue)

if (-not $defenderPresente) {
    Write-Output "  Defender no está disponible en este equipo (sin Get-MpComputerStatus)."
}
else {
    try {
        $estadoDefender = Get-MpComputerStatus -ErrorAction Stop

        Write-Output "  antimalware habilitado:    $($estadoDefender.AMServiceEnabled)"
        Write-Output "  tiempo real:               $($estadoDefender.RealTimeProtectionEnabled)"
        Write-Output "  protección de red:         $($estadoDefender.NISEnabled)"
        Write-Output "  modo pasivo:               $($estadoDefender.AMRunningMode)"
        Write-Output "  versión de firmas:         $($estadoDefender.AntivirusSignatureVersion)"
        Write-Output "  edad de las firmas:        $($estadoDefender.AntivirusSignatureAge) día(s)"
        Write-Output "  último escaneo rápido:     $($estadoDefender.QuickScanEndTime)"
        Write-Output "  último escaneo completo:   $($estadoDefender.FullScanEndTime)"

        # AMRunningMode distingue "Normal" de "Passive"/"EDR Block Mode": en pasivo
        # Defender NO protege, solo observa, y eso es invisible si uno mira nada
        # más que RealTimeProtectionEnabled.
        if ($estadoDefender.AMRunningMode -eq "Normal") {
            if ($estadoDefender.RealTimeProtectionEnabled) { $algunoActivo = $true }
            else { Add-Problema "Defender es el activo pero su tiempo real está apagado" }
        }
        else {
            Write-Output "  AVISO: Defender está en modo '$($estadoDefender.AMRunningMode)',"
            Write-Output "         lo que significa que otro antivirus es el que protege."
        }

        if ($estadoDefender.AntivirusSignatureAge -gt 7) {
            Add-Problema "firmas de Defender con $($estadoDefender.AntivirusSignatureAge) días"
        }
    }
    catch {
        Write-Output "  No se pudo leer el estado de Defender: $($_.Exception.Message)"
    }

    Write-Output ""
    Write-Output "== Amenazas de Defender (últimos $DiasAmenazas día[s]) =="
    try {
        $desde = (Get-Date).AddDays(-1 * [Math]::Abs($DiasAmenazas))
        $amenazas = @(Get-MpThreatDetection -ErrorAction Stop |
            Where-Object { $_.InitialDetectionTime -ge $desde })

        if ($amenazas.Count -eq 0) {
            Write-Output "  Sin detecciones en la ventana consultada."
        }
        else {
            foreach ($amenaza in ($amenazas | Sort-Object InitialDetectionTime -Descending)) {
                Write-Output ""
                Write-Output "  detectada:  $($amenaza.InitialDetectionTime)"
                Write-Output "  amenaza ID: $($amenaza.ThreatID)"
                Write-Output "  acción:     $($amenaza.ActionSuccess)"
                Write-Output "  recursos:   $($amenaza.Resources -join ', ')"
            }
            Add-Problema "$($amenazas.Count) detección(es) en los últimos $DiasAmenazas día(s)"
        }
    }
    catch {
        Write-Output "  No se pudo consultar el historial de amenazas: $($_.Exception.Message)"
    }
}

Write-Output ""
Write-Output "== Resultado =="

if (-not $algunoActivo) {
    Add-Problema "ningún antivirus con protección en tiempo real activa"
}

if ($problemas.Count -eq 0) {
    Write-Output "  Equipo protegido, sin observaciones."
    exit 0
}

Write-Output "  $($problemas.Count) observación(es):"
foreach ($problema in $problemas) {
    Write-Output "   - $problema"
}
exit 1
