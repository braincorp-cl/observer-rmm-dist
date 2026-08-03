<#
.SYNOPSIS
    Estado del Firewall de Windows y del Control de cuentas de usuario (UAC).

.DESCRIPTION
    Solo LEE. Une los dos chequeos de cumplimiento más pedidos en una sola pasada,
    porque casi nunca se audita uno sin el otro.

    Del firewall reporta los tres perfiles (dominio, privado, público) con su
    política de entrada y salida. Del UAC lee el registro, no la interfaz: lo que
    importa es EnableLUA (si el UAC está encendido) y ConsentPromptBehaviorAdmin
    (cómo pide confirmación), y ese segundo valor puesto en 0 deja al UAC
    "encendido" pero elevando en silencio, que es lo mismo que apagado.

    Sale con 1 si algún perfil de firewall está apagado o si el UAC está
    deshabilitado o elevando sin preguntar.

.EXAMPLE
    firewall-uac-estado.ps1
#>

[CmdletBinding()]
param()

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

Write-Output "== Firewall de Windows =="

try {
    $perfiles = @(Get-NetFirewallProfile -ErrorAction Stop)
    foreach ($perfil in $perfiles) {
        Write-Output ""
        Write-Output "  Perfil $($perfil.Name)"
        Write-Output "    habilitado:           $($perfil.Enabled)"
        Write-Output "    entrada por defecto:  $($perfil.DefaultInboundAction)"
        Write-Output "    salida por defecto:   $($perfil.DefaultOutboundAction)"
        Write-Output "    notificaciones:       $($perfil.NotifyOnListen)"
        Write-Output "    registro de bloqueos: $($perfil.LogBlocked)"

        if (-not $perfil.Enabled) {
            [void]$problemas.Add("perfil de firewall '$($perfil.Name)' deshabilitado")
        }
        # Un perfil habilitado pero con entrada permitida por defecto es una puerta
        # abierta con la alarma puesta: conviene marcarlo.
        if ($perfil.DefaultInboundAction -eq "Allow") {
            [void]$problemas.Add("perfil '$($perfil.Name)' permite todo el tráfico de entrada")
        }
    }

    $reglasActivas = @(Get-NetFirewallRule -Enabled True -ErrorAction Stop)
    Write-Output ""
    Write-Output "  reglas habilitadas: $($reglasActivas.Count)"
}
catch {
    Write-Output "  No se pudo consultar el firewall: $($_.Exception.Message)"
    [void]$problemas.Add("el estado del firewall no se pudo determinar")
}

Write-Output ""
Write-Output "== Control de cuentas de usuario (UAC) =="

$rutaUac = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
try {
    $uac = Get-ItemProperty -Path $rutaUac -ErrorAction Stop

    $habilitado = $uac.EnableLUA -eq 1
    Write-Output "  UAC habilitado (EnableLUA):        $habilitado"
    Write-Output "  comportamiento admin:              $($uac.ConsentPromptBehaviorAdmin)"
    Write-Output "  comportamiento usuario estándar:   $($uac.ConsentPromptBehaviorUser)"
    Write-Output "  escritorio seguro:                 $($uac.PromptOnSecureDesktop)"
    Write-Output "  virtualización de escritura:       $($uac.EnableVirtualization)"

    if (-not $habilitado) {
        [void]$problemas.Add("el UAC está deshabilitado (EnableLUA=0)")
    }
    elseif ($uac.ConsentPromptBehaviorAdmin -eq 0) {
        [void]$problemas.Add("el UAC eleva sin preguntar (ConsentPromptBehaviorAdmin=0)")
    }

    switch ($uac.ConsentPromptBehaviorAdmin) {
        0 { Write-Output "  interpretación: eleva sin pedir confirmación" }
        1 { Write-Output "  interpretación: pide credenciales en escritorio seguro" }
        2 { Write-Output "  interpretación: pide consentimiento en escritorio seguro" }
        3 { Write-Output "  interpretación: pide credenciales" }
        4 { Write-Output "  interpretación: pide consentimiento" }
        5 { Write-Output "  interpretación: pide consentimiento para binarios de terceros (por defecto)" }
        default { Write-Output "  interpretación: valor no reconocido" }
    }
}
catch {
    Write-Output "  No se pudo leer la configuración del UAC: $($_.Exception.Message)"
    [void]$problemas.Add("el estado del UAC no se pudo determinar")
}

Write-Output ""
Write-Output "== Resultado =="

if ($problemas.Count -eq 0) {
    Write-Output "  Firewall y UAC en configuración esperada."
    exit 0
}

Write-Output "  $($problemas.Count) observación(es):"
foreach ($problema in $problemas) {
    Write-Output "   - $problema"
}
exit 1
