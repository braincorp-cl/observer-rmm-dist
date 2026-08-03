<#
.SYNOPSIS
    Registra en Microsoft Defender las exclusiones de ObserverRMM y del agente Mesh.

.DESCRIPTION
    Defender puede poner en cuarentena partes del agente o frenar la ejecución de
    scripts, dejando al equipo aparentemente en línea pero sordo a los comandos.
    Este script agrega las exclusiones de carpeta y de proceso que necesita el
    agente, resolviendo las rutas desde el entorno y desde el registro en vez de
    clavarlas: si el agente se instaló con un temporal personalizado (valor
    WinTmpDir de HKLM\SOFTWARE\ObserverRMM), la exclusión sigue a la ruta real.

    Es idempotente: Defender ignora los duplicados, y el script informa lo que ya
    estaba presente. Con -Quitar revierte las mismas exclusiones.

    Rutas y nombres tomados del código del agente (agent/agent.go:85-102).

.PARAMETER Quitar
    Elimina las exclusiones en lugar de agregarlas.

.EXAMPLE
    defender-exclusiones-observerrmm.ps1
    defender-exclusiones-observerrmm.ps1 -Quitar
#>

[CmdletBinding()]
param(
    [switch]$Quitar
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

if (-not (Get-Command Get-MpPreference -ErrorAction SilentlyContinue)) {
    Write-Output "Este equipo no expone Microsoft Defender (Get-MpPreference no existe)."
    Write-Output "Puede ser un Windows Server sin la característica, o un antivirus de terceros."
    exit 1
}

$archivosPrograma = $env:ProgramFiles
if (-not $archivosPrograma) { $archivosPrograma = "C:\Program Files" }

$datosPrograma = $env:ProgramData
if (-not $datosPrograma) { $datosPrograma = "C:\ProgramData" }

$dirAgente = Join-Path $archivosPrograma "ObserverAgent"
$dirMesh = Join-Path $archivosPrograma "Mesh Agent"

# El temporal por defecto es %PROGRAMDATA%\ObserverRMM, pero el instalador admite
# uno propio y lo deja en el registro. Se prefiere el del registro si existe.
$dirTemporal = Join-Path $datosPrograma "ObserverRMM"
try {
    $config = Get-ItemProperty -Path "HKLM:\SOFTWARE\ObserverRMM" -ErrorAction Stop
    if ($config.WinTmpDir) {
        $dirTemporal = $config.WinTmpDir
        Write-Output "Temporal personalizado detectado en el registro: $dirTemporal"
    }
    if ($config.MeshDir) {
        $dirMesh = $config.MeshDir
        Write-Output "Directorio del Mesh personalizado detectado: $dirMesh"
    }
}
catch {
    Write-Output "Sin clave HKLM\SOFTWARE\ObserverRMM: se usan las rutas por defecto."
}

$carpetas = @($dirAgente, $dirMesh, $dirTemporal) | Select-Object -Unique
$procesos = @("observeragent.exe", "MeshAgent.exe")

$preferencias = Get-MpPreference
$carpetasActuales = @($preferencias.ExclusionPath)
$procesosActuales = @($preferencias.ExclusionProcess)

$agregadas = 0
$yaEstaban = 0
$errores = 0

function Test-Excluida {
    param($valor, $lista)
    foreach ($item in $lista) {
        if ($item -and ($item.TrimEnd('\') -ieq $valor.TrimEnd('\'))) { return $true }
    }
    return $false
}

if ($Quitar) {
    Write-Output ""
    Write-Output "Quitando exclusiones de ObserverRMM..."
    foreach ($carpeta in $carpetas) {
        if (Test-Excluida $carpeta $carpetasActuales) {
            try {
                Remove-MpPreference -ExclusionPath $carpeta -ErrorAction Stop
                Write-Output "  quitada carpeta:  $carpeta"
                $agregadas++
            }
            catch {
                Write-Output "  ERROR al quitar $carpeta : $($_.Exception.Message)"
                $errores++
            }
        }
        else {
            Write-Output "  no estaba:        $carpeta"
            $yaEstaban++
        }
    }
    foreach ($proceso in $procesos) {
        if (Test-Excluida $proceso $procesosActuales) {
            try {
                Remove-MpPreference -ExclusionProcess $proceso -ErrorAction Stop
                Write-Output "  quitado proceso:  $proceso"
                $agregadas++
            }
            catch {
                Write-Output "  ERROR al quitar $proceso : $($_.Exception.Message)"
                $errores++
            }
        }
        else {
            Write-Output "  no estaba:        $proceso"
            $yaEstaban++
        }
    }
}
else {
    Write-Output ""
    Write-Output "Agregando exclusiones de ObserverRMM..."
    foreach ($carpeta in $carpetas) {
        if (Test-Excluida $carpeta $carpetasActuales) {
            Write-Output "  ya excluida:      $carpeta"
            $yaEstaban++
            continue
        }
        try {
            Add-MpPreference -ExclusionPath $carpeta -ErrorAction Stop
            Write-Output "  carpeta:          $carpeta"
            $agregadas++
        }
        catch {
            Write-Output "  ERROR en $carpeta : $($_.Exception.Message)"
            $errores++
        }
    }
    foreach ($proceso in $procesos) {
        if (Test-Excluida $proceso $procesosActuales) {
            Write-Output "  ya excluido:      $proceso"
            $yaEstaban++
            continue
        }
        try {
            Add-MpPreference -ExclusionProcess $proceso -ErrorAction Stop
            Write-Output "  proceso:          $proceso"
            $agregadas++
        }
        catch {
            Write-Output "  ERROR en $proceso : $($_.Exception.Message)"
            $errores++
        }
    }
}

Write-Output ""
Write-Output "Resumen: $agregadas aplicada(s), $yaEstaban sin cambio, $errores con error."

if ($errores -gt 0) { exit 1 }
exit 0
