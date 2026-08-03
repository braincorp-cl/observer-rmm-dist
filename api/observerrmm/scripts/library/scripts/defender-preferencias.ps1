<#
.SYNOPSIS
    Endurece o restablece las preferencias de Microsoft Defender.

.DESCRIPTION
    Reemplaza los dos scripts separados de "habilitar Defender" y "volver a los
    valores por defecto" por uno con modo, y agrega un modo de solo lectura para
    ver en qué estado está el equipo antes de tocar nada.

    Endurecer activa lo que Microsoft deja opcional: tiempo real, protección en la
    nube, envío de muestras, bloqueo de aplicaciones potencialmente no deseadas
    (PUA) y análisis de scripts y descargas.

    Lo que este script NO toca a propósito: el Acceso controlado a carpetas y las
    reglas de reducción de superficie de ataque (ASR). Ambos rompen software
    legítimo con frecuencia y necesitan una fase de auditoría por cliente antes de
    aplicarse: no son un interruptor.

.PARAMETER Modo
    estado (por defecto, solo lee), endurecer, o restablecer.

.EXAMPLE
    defender-preferencias.ps1
    defender-preferencias.ps1 -Modo endurecer
    defender-preferencias.ps1 -Modo restablecer
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "endurecer", "restablecer")]
    [string]$Modo = "estado"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command Get-MpPreference -ErrorAction SilentlyContinue)) {
    Write-Output "Microsoft Defender no está disponible en este equipo."
    exit 1
}

function Show-Preferencia {
    param([string]$Titulo)

    $preferencias = Get-MpPreference
    Write-Output ""
    Write-Output "== $Titulo =="
    Write-Output "  tiempo real deshabilitado:     $($preferencias.DisableRealtimeMonitoring)"
    Write-Output "  monitoreo de comportamiento:   $(-not $preferencias.DisableBehaviorMonitoring)"
    Write-Output "  análisis de scripts:           $(-not $preferencias.DisableScriptScanning)"
    Write-Output "  análisis de descargas (IOAV):  $(-not $preferencias.DisableIOAVProtection)"
    Write-Output "  protección de red (NIS):       $(-not $preferencias.DisableIntrusionPreventionSystem)"
    Write-Output "  análisis de correo:            $(-not $preferencias.DisableEmailScanning)"
    Write-Output "  análisis de extraíbles:        $(-not $preferencias.DisableRemovableDriveScanning)"
    Write-Output "  bloqueo de PUA:                $($preferencias.PUAProtection)"
    Write-Output "  nivel de protección en nube:   $($preferencias.CloudBlockLevel)"
    Write-Output "  consentimiento MAPS:           $($preferencias.MAPSReporting)"
    Write-Output "  envío de muestras:             $($preferencias.SubmitSamplesConsent)"
    Write-Output "  acción ante severidad alta:    $($preferencias.HighThreatDefaultAction)"

    try {
        $estado = Get-MpComputerStatus
        Write-Output "  modo de ejecución:             $($estado.AMRunningMode)"
        if ($estado.AMRunningMode -ne "Normal") {
            Write-Output ""
            Write-Output "  AVISO: Defender no es el antivirus activo (modo '$($estado.AMRunningMode)')."
            Write-Output "         Cambiar sus preferencias no cambia quién protege el equipo."
        }
    }
    catch {
        # Informativo: el modo de ejecución es contexto, no el objetivo.
        Write-Verbose $_.Exception.Message
    }
}

Show-Preferencia -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    exit 0
}

$errores = 0

function Write-Preferencia {
    param([string]$Descripcion, [hashtable]$Argumentos)
    try {
        Set-MpPreference @Argumentos -ErrorAction Stop
        Write-Output "  OK    $Descripcion"
    }
    catch {
        Write-Output "  ERROR $Descripcion : $($_.Exception.Message)"
        $script:errores++
    }
}

Write-Output ""
if ($Modo -eq "endurecer") {
    Write-Output "== Endureciendo Defender =="
    Write-Preferencia "protección en tiempo real" @{ DisableRealtimeMonitoring = $false }
    Write-Preferencia "monitoreo de comportamiento" @{ DisableBehaviorMonitoring = $false }
    Write-Preferencia "análisis de scripts" @{ DisableScriptScanning = $false }
    Write-Preferencia "análisis de descargas" @{ DisableIOAVProtection = $false }
    Write-Preferencia "protección de red" @{ DisableIntrusionPreventionSystem = $false }
    Write-Preferencia "análisis de unidades extraíbles" @{ DisableRemovableDriveScanning = $false }
    Write-Preferencia "bloqueo de PUA" @{ PUAProtection = "Enabled" }
    Write-Preferencia "protección en la nube (alta)" @{ CloudBlockLevel = "High" }
    Write-Preferencia "consentimiento MAPS avanzado" @{ MAPSReporting = "Advanced" }
    Write-Preferencia "envío automático de muestras seguras" @{ SubmitSamplesConsent = "SendSafeSamples" }
}
else {
    Write-Output "== Restableciendo Defender a los valores por defecto =="
    # Estos son los valores con los que Windows sale de fábrica: no es un "apagar
    # todo", es volver al punto de partida para descartar que el endurecimiento sea
    # la causa de un problema.
    Write-Preferencia "protección en tiempo real (por defecto: activa)" @{ DisableRealtimeMonitoring = $false }
    Write-Preferencia "monitoreo de comportamiento (por defecto: activo)" @{ DisableBehaviorMonitoring = $false }
    Write-Preferencia "análisis de scripts (por defecto: activo)" @{ DisableScriptScanning = $false }
    Write-Preferencia "análisis de descargas (por defecto: activo)" @{ DisableIOAVProtection = $false }
    Write-Preferencia "protección de red (por defecto: activa)" @{ DisableIntrusionPreventionSystem = $false }
    Write-Preferencia "bloqueo de PUA (por defecto: desactivado)" @{ PUAProtection = "Disabled" }
    Write-Preferencia "protección en la nube (por defecto)" @{ CloudBlockLevel = "Default" }
    Write-Preferencia "consentimiento MAPS (por defecto: básico)" @{ MAPSReporting = "Basic" }
    Write-Preferencia "envío de muestras (por defecto: preguntar)" @{ SubmitSamplesConsent = "AlwaysPrompt" }
}

Show-Preferencia -Titulo "Estado resultante"

Write-Output ""
if ($errores -gt 0) {
    Write-Output "Terminó con $errores error(es). Revisá si una directiva de grupo"
    Write-Output "o el inquilino de Intune está fijando estos valores por política:"
    Write-Output "en ese caso el cambio local se ignora o se revierte."
    exit 1
}

Write-Output "Aplicado sin errores."
exit 0
