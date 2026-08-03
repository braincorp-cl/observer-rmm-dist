<#
.SYNOPSIS
    Estado de la activación de Windows y, opcionalmente, aplicación de una clave.

.DESCRIPTION
    Une el chequeo de activación y el cambio de clave, que el catálogo original tenía
    separados en dos categorías.

    En modo 'estado' solo LEE: informa la edición, el canal de licencia (OEM, minorista,
    por volumen), el estado de activación y, si es por volumen, contra qué servidor KMS
    se activó y cuándo vence la renovación. Ese último dato es el que importa en un
    parque con licenciamiento por volumen: una máquina que dejó de ver el KMS entra en
    período de gracia y se desactiva sola semanas después, sin que nadie mire.

    Sale con 1 si Windows no está activado.

    ADVERTENCIA para el modo 'clave': la clave se pasa como argumento y queda escrita en
    el historial de la consola. Además, aplicar una clave incorrecta puede dejar el
    equipo desactivado hasta que se aplique la correcta.

.PARAMETER Modo
    estado (por defecto) o clave.

.PARAMETER Clave
    Clave de producto en formato XXXXX-XXXXX-XXXXX-XXXXX-XXXXX. Obligatoria en modo 'clave'.

.EXAMPLE
    windows-activacion.ps1
    windows-activacion.ps1 -Modo clave -Clave "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "clave")]
    [string]$Modo = "estado",

    [string]$Clave
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

# Los estados de licencia de SoftwareLicensingProduct, según la documentación de
# Microsoft. El 1 es el único "activado"; el 5 (notificación) es el que precede a la
# desactivación visible y conviene distinguirlo de "no licenciado".
$ESTADOS = @{
    0 = "sin licencia"
    1 = "activado"
    2 = "período de gracia inicial"
    3 = "período de gracia adicional (token)"
    4 = "gracia por reemplazo de token"
    5 = "notificación (a punto de desactivarse)"
    6 = "gracia extendida"
}

Write-Output "== Sistema =="
try {
    $sistemaOperativo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    Write-Output "  edición:  $($sistemaOperativo.Caption)"
    Write-Output "  versión:  $($sistemaOperativo.Version) (build $($sistemaOperativo.BuildNumber))"
    Write-Output "  arquitec: $($sistemaOperativo.OSArchitecture)"
}
catch {
    Write-Output "  no se pudo leer la información del sistema: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "== Licencia =="

$activado = $false

try {
    # Se filtra por PartialProductKey para descartar las decenas de entradas de
    # productos no instalados, que aparecen todas como "sin licencia" y ensucian todo.
    $productos = @(Get-CimInstance -ClassName SoftwareLicensingProduct -ErrorAction Stop |
        Where-Object { $_.PartialProductKey -and $_.Name -like "*Windows*" })

    if ($productos.Count -eq 0) {
        Write-Output "  No se encontró ningún producto Windows con clave instalada."
    }

    foreach ($producto in $productos) {
        $estado = [int]$producto.LicenseStatus
        $textoEstado = if ($ESTADOS.ContainsKey($estado)) { $ESTADOS[$estado] } else { "desconocido ($estado)" }

        Write-Output ""
        Write-Output "  $($producto.Name)"
        Write-Output "    descripción:      $($producto.Description)"
        Write-Output "    estado:           $textoEstado"
        Write-Output "    clave parcial:    $($producto.PartialProductKey)"

        if ($producto.LicenseFamily) {
            Write-Output "    familia:          $($producto.LicenseFamily)"
        }

        if ($estado -eq 1) { $activado = $true }

        # Datos de KMS: solo existen si el canal es por volumen.
        if ($producto.KeyManagementServiceMachine) {
            Write-Output "    servidor KMS:     $($producto.KeyManagementServiceMachine):$($producto.KeyManagementServicePort)"
        }
        if ($producto.VLActivationInterval) {
            Write-Output "    intervalo activ.: $($producto.VLActivationInterval) min"
        }
        if ($producto.VLRenewalInterval) {
            Write-Output "    intervalo renov.: $($producto.VLRenewalInterval) min"
        }
        if ($null -ne $producto.GracePeriodRemaining -and $producto.GracePeriodRemaining -gt 0) {
            $dias = [Math]::Round($producto.GracePeriodRemaining / 1440, 1)
            Write-Output "    gracia restante:  $dias día(s)"
            if ($dias -lt 15) {
                Write-Output "    AVISO: quedan menos de 15 días de gracia. Si no vuelve a ver"
                Write-Output "           el KMS, Windows se va a desactivar."
            }
        }
    }
}
catch {
    Write-Output "  No se pudo consultar la licencia: $($_.Exception.Message)"
}

# El canal (OEM/minorista/volumen) sale del servicio de licencias y no del producto.
Write-Output ""
Write-Output "== Canal y servicio de licencias =="
try {
    $servicio = Get-CimInstance -ClassName SoftwareLicensingService -ErrorAction Stop
    if ($servicio.OA3xOriginalProductKeyDescription) {
        Write-Output "  clave en firmware: $($servicio.OA3xOriginalProductKeyDescription)"
    }
    if ($servicio.OA3xOriginalProductKey) {
        Write-Output "  clave OEM en BIOS: presente (recuperable desde el firmware)"
    }
    else {
        Write-Output "  clave OEM en BIOS: ausente"
    }
    Write-Output "  versión del servicio: $($servicio.Version)"
}
catch {
    Write-Output "  No se pudo consultar el servicio de licencias: $($_.Exception.Message)"
}

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "== Resultado =="
    if ($activado) {
        Write-Output "  Windows está activado."
        exit 0
    }
    Write-Output "  Windows NO está activado."
    exit 1
}

if (-not $Clave) {
    Write-Output ""
    Write-Output "El modo 'clave' exige el parámetro -Clave."
    exit 1
}

$claveLimpia = $Clave.Trim().ToUpper()
if ($claveLimpia -notmatch "^[A-Z0-9]{5}(-[A-Z0-9]{5}){4}$") {
    Write-Output ""
    Write-Output "ABORTADO: la clave no tiene el formato XXXXX-XXXXX-XXXXX-XXXXX-XXXXX."
    exit 1
}

Write-Output ""
Write-Output "== Aplicando la clave de producto =="
Write-Output "  Se aplicará una clave que termina en $($claveLimpia.Substring($claveLimpia.Length - 5))"

# slmgr es un script de Windows Script Host: se invoca por cscript para poder leer su
# salida. El equivalente por WMI (InstallProductKey) no devuelve un mensaje legible.
$rutaSlmgr = Join-Path $env:SystemRoot "System32\slmgr.vbs"
if (-not (Test-Path $rutaSlmgr)) {
    Write-Output "  No se encontró slmgr.vbs: no se puede aplicar la clave."
    exit 1
}

$salida = & cscript.exe //Nologo $rutaSlmgr /ipk $claveLimpia 2>&1
Write-Output "  $($salida -join ' ')"

if ($LASTEXITCODE -ne 0) {
    Write-Output ""
    Write-Output "  La instalación de la clave falló (código $LASTEXITCODE)."
    exit 1
}

Write-Output ""
Write-Output "  Intentando activar contra el servidor de activación..."
$salidaActivacion = & cscript.exe //Nologo $rutaSlmgr /ato 2>&1
Write-Output "  $($salidaActivacion -join ' ')"

# Verificación por efecto: releer el estado de licencia, no confiar en el código de
# salida de slmgr, que devuelve 0 incluso cuando la activación no se completó.
Start-Sleep -Seconds 3
$activadoFinal = $false
try {
    $productos = @(Get-CimInstance -ClassName SoftwareLicensingProduct -ErrorAction Stop |
        Where-Object { $_.PartialProductKey -and $_.Name -like "*Windows*" })
    foreach ($producto in $productos) {
        if ([int]$producto.LicenseStatus -eq 1) { $activadoFinal = $true }
    }
}
catch {
    Write-Output "  No se pudo releer el estado de licencia."
}

Write-Output ""
Write-Output "== Resultado =="
if ($activadoFinal) {
    Write-Output "  Windows quedó ACTIVADO."
    exit 0
}
Write-Output "  La clave se instaló pero Windows sigue SIN activar."
Write-Output "  Suele ser falta de salida a internet o al KMS, no un problema de la clave."
exit 1
