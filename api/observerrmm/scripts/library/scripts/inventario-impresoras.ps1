<#
.SYNOPSIS
    Lista las impresoras instaladas con su puerto, driver y estado de comparticion.

.DESCRIPTION
    Solo LEE. Responde las tres preguntas que aparecen en cada ticket de impresion:
    que impresoras tiene el equipo, por donde salen (IP, USB, cola compartida) y
    cual es la predeterminada.

    Marca aparte las colas redirigidas y las virtuales de Windows (PDF, XPS, Fax),
    que suelen ser ruido cuando se busca la impresora fisica real.

.PARAMETER SoloFisicas
    Omite las impresoras virtuales de Windows y las colas redirigidas.

.EXAMPLE
    inventario-impresoras.ps1
    inventario-impresoras.ps1 -SoloFisicas
#>

[CmdletBinding()]
param(
    [switch]$SoloFisicas
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

$virtuales = @(
    "Microsoft Print to PDF",
    "Microsoft XPS Document Writer",
    "Fax",
    "OneNote",
    "Send To OneNote"
)

try {
    $impresoras = @(Get-Printer -ErrorAction Stop)
}
catch {
    Write-Output "No se pudo consultar las impresoras: $($_.Exception.Message)"
    exit 1
}

if ($impresoras.Count -eq 0) {
    Write-Output "No hay impresoras instaladas en este equipo."
    exit 0
}

# Los puertos se piden una vez y se indexan: pedirlos por impresora multiplica
# las consultas WMI sin necesidad.
$puertos = @{}
try {
    foreach ($puerto in Get-PrinterPort -ErrorAction Stop) {
        $puertos[$puerto.Name] = $puerto
    }
}
catch {
    # Sin detalle de puertos igual se informa el nombre que trae la impresora.
    Write-Verbose $_.Exception.Message
}

$mostradas = 0
$omitidas = 0

foreach ($impresora in ($impresoras | Sort-Object Name)) {
    $esVirtual = $virtuales -contains $impresora.Name
    $esRedirigida = $impresora.Name -like "*redirected*"

    if ($SoloFisicas -and ($esVirtual -or $esRedirigida)) {
        $omitidas++
        continue
    }

    $mostradas++
    $etiqueta = ""
    if ($esVirtual) { $etiqueta = "  [virtual de Windows]" }
    if ($esRedirigida) { $etiqueta = "  [cola redirigida de sesion remota]" }

    Write-Output ""
    Write-Output "$($impresora.Name)$etiqueta"
    Write-Output "  driver:          $($impresora.DriverName)"
    Write-Output "  puerto:          $($impresora.PortName)"

    if ($puertos.ContainsKey($impresora.PortName)) {
        $puerto = $puertos[$impresora.PortName]
        if ($puerto.PrinterHostAddress) {
            Write-Output "  direccion:       $($puerto.PrinterHostAddress)"
        }
        if ($puerto.Description) {
            Write-Output "  tipo de puerto:  $($puerto.Description)"
        }
    }

    Write-Output "  compartida:      $(if ($impresora.Shared) { "si (como '$($impresora.ShareName)')" } else { 'no' })"
    Write-Output "  estado:          $($impresora.PrinterStatus)"
    Write-Output "  tipo:            $($impresora.Type)"

    if ($impresora.Location) {
        Write-Output "  ubicacion:       $($impresora.Location)"
    }
}

# La predeterminada no esta en Get-Printer: hay que ir a la clase vieja de WMI.
try {
    $predeterminada = Get-CimInstance -ClassName Win32_Printer -ErrorAction Stop |
        Where-Object { $_.Default -eq $true } |
        Select-Object -First 1
    Write-Output ""
    if ($predeterminada) {
        Write-Output "Predeterminada: $($predeterminada.Name)"
    }
    else {
        Write-Output "Predeterminada: ninguna marcada."
    }
}
catch {
    Write-Output ""
    Write-Output "Predeterminada: no se pudo determinar."
}

Write-Output "Total: $mostradas mostrada(s), $omitidas omitida(s)."
exit 0
