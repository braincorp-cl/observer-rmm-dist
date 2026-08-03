<#
.SYNOPSIS
    Habilita, deshabilita o consulta el acceso a dispositivos de almacenamiento USB.

.DESCRIPTION
    Reemplaza los dos scripts separados de habilitar y deshabilitar por uno con
    modo, más un modo de consulta.

    Actúa sobre el arranque del driver USBSTOR en el registro: 3 = habilitado,
    4 = deshabilitado. Eso bloquea pendrives y discos externos **sin** afectar
    teclados, mouse, impresoras ni cámaras USB, que usan otros drivers. Es la
    diferencia con deshabilitar el controlador USB completo, que dejaría el equipo
    sin teclado.

    Importante: el cambio afecta a los dispositivos que se conecten después. Un
    pendrive ya montado sigue accesible hasta que se desconecte o se reinicie el
    equipo; el script lo avisa si detecta uno conectado.

.PARAMETER Modo
    estado (por defecto), habilitar, o deshabilitar.

.EXAMPLE
    usb-almacenamiento.ps1
    usb-almacenamiento.ps1 -Modo deshabilitar
    usb-almacenamiento.ps1 -Modo habilitar
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "habilitar", "deshabilitar")]
    [string]$Modo = "estado"
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

$rutaUsbStor = "HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR"
$VALOR_HABILITADO = 3
$VALOR_DESHABILITADO = 4

if (-not (Test-Path $rutaUsbStor)) {
    Write-Output "No existe la clave del driver USBSTOR en este equipo."
    Write-Output "Puede ser una imagen sin soporte de almacenamiento USB."
    exit 1
}

function Get-EstadoUsb {
    try {
        $valor = (Get-ItemProperty -Path $rutaUsbStor -Name Start -ErrorAction Stop).Start
        return [int]$valor
    }
    catch {
        return $null
    }
}

function Show-DispositivoConectado {
    try {
        $discos = @(Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction Stop |
            Where-Object { $_.InterfaceType -eq "USB" })
        if ($discos.Count -gt 0) {
            Write-Output ""
            Write-Output "  Dispositivos de almacenamiento USB conectados ahora mismo:"
            foreach ($disco in $discos) {
                $tamano = if ($disco.Size) { "$([Math]::Round($disco.Size / 1GB, 1)) GB" } else { "tamaño desconocido" }
                Write-Output "   - $($disco.Model) ($tamano)"
            }
            return $discos.Count
        }
    }
    catch {
        # Informativo: la lista de conectados es un extra del reporte.
        Write-Verbose $_.Exception.Message
    }
    return 0
}

$actual = Get-EstadoUsb
if ($null -eq $actual) {
    Write-Output "No se pudo leer el valor Start de USBSTOR."
    exit 1
}

$textoActual = switch ($actual) {
    $VALOR_HABILITADO { "HABILITADO" }
    $VALOR_DESHABILITADO { "DESHABILITADO" }
    default { "valor inesperado ($actual)" }
}

Write-Output "Almacenamiento USB: $textoActual (USBSTOR Start=$actual)"
$conectados = Show-DispositivoConectado

if ($Modo -eq "estado") {
    exit 0
}

$deseado = if ($Modo -eq "habilitar") { $VALOR_HABILITADO } else { $VALOR_DESHABILITADO }

if ($actual -eq $deseado) {
    Write-Output ""
    Write-Output "Nada que hacer: ya estaba $textoActual."
    exit 0
}

Write-Output ""
Write-Output "Aplicando: $Modo (Start $actual -> $deseado)"

try {
    Set-ItemProperty -Path $rutaUsbStor -Name Start -Value $deseado -Type DWord -ErrorAction Stop
}
catch {
    Write-Output "No se pudo escribir el registro: $($_.Exception.Message)"
    exit 1
}

# Verificación por efecto: releer el valor en vez de confiar en que el Set no lanzó.
$verificado = Get-EstadoUsb
if ($verificado -ne $deseado) {
    Write-Output "FALLA: se escribió pero el valor quedó en $verificado."
    Write-Output "Puede haber una directiva de grupo revirtiéndolo."
    exit 1
}

Write-Output "Aplicado y verificado: USBSTOR Start=$verificado."

if ($Modo -eq "deshabilitar" -and $conectados -gt 0) {
    Write-Output ""
    Write-Output "AVISO: hay $conectados dispositivo(s) USB ya montado(s). Siguen"
    Write-Output "accesibles hasta que se desconecten o se reinicie el equipo."
}

exit 0
