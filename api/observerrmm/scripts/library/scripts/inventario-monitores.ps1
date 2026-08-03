<#
.SYNOPSIS
    Lista los monitores conectados con fabricante, modelo, serie y año.

.DESCRIPTION
    Solo LEE. El inventario de hardware del agente no recoge monitores, así que
    este es el único camino para saber qué pantalla tiene un equipo sin ir a verlo.

    Los datos salen del EDID que expone WMI en el namespace root\wmi
    (WmiMonitorID), donde fabricante, modelo y serie vienen como arreglos de
    códigos UInt16 terminados en cero: hay que decodificarlos a texto.

    Los monitores apagados o desconectados no aparecen: WMI solo reporta los
    activos. Un equipo sin pantalla (servidor, VM) devuelve lista vacía, que no es
    un error.

.EXAMPLE
    inventario-monitores.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Convert-EdidTexto {
    param([UInt16[]]$Codigos)
    if (-not $Codigos) { return "" }
    # El EDID rellena con ceros a la derecha; se cortan antes de convertir.
    $utiles = $Codigos | Where-Object { $_ -ne 0 }
    if (-not $utiles) { return "" }
    return (-join ($utiles | ForEach-Object { [char]$_ })).Trim()
}

try {
    $monitores = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction Stop)
}
catch {
    Write-Output "No se pudo consultar WmiMonitorID: $($_.Exception.Message)"
    Write-Output "Es normal en algunos servidores y VM sin driver de video real."
    exit 1
}

if ($monitores.Count -eq 0) {
    Write-Output "No se detectaron monitores activos."
    Write-Output "Los monitores apagados o desconectados no se reportan por WMI."
    exit 0
}

# Las resoluciones vienen de otra clase; se indexan por InstanceName para poder
# cruzarlas sin asumir que ambas listas vengan en el mismo orden.
$resoluciones = @{}
try {
    foreach ($modo in Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorListedSupportedSourceModes -ErrorAction Stop) {
        $preferido = $modo.MonitorSourceModes | Select-Object -First 1
        if ($preferido) {
            $resoluciones[$modo.InstanceName] = "$($preferido.HorizontalActivePixels)x$($preferido.VerticalActivePixels)"
        }
    }
}
catch {
    # Opcional: si falla, se informa el monitor sin resolución.
    Write-Verbose $_.Exception.Message
}

$indice = 0
foreach ($monitor in $monitores) {
    $indice++
    $fabricante = Convert-EdidTexto $monitor.ManufacturerName
    $modelo = Convert-EdidTexto $monitor.UserFriendlyName
    $serie = Convert-EdidTexto $monitor.SerialNumberID

    if (-not $modelo) { $modelo = "(sin nombre en el EDID)" }
    if (-not $serie) { $serie = "(sin serie en el EDID)" }

    Write-Output ""
    Write-Output "Monitor $indice"
    Write-Output "  fabricante:      $fabricante"
    Write-Output "  modelo:          $modelo"
    Write-Output "  número de serie: $serie"
    Write-Output "  año de fabric.:  $($monitor.YearOfManufacture)"
    Write-Output "  semana:          $($monitor.WeekOfManufacture)"
    if ($resoluciones.ContainsKey($monitor.InstanceName)) {
        Write-Output "  resolución nativa: $($resoluciones[$monitor.InstanceName])"
    }
    Write-Output "  activo:          $(if ($monitor.Active) { 'sí' } else { 'no' })"
}

Write-Output ""
Write-Output "Total: $($monitores.Count) monitor(es) detectado(s)."
exit 0
