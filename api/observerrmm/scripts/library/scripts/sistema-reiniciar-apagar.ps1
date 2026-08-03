<#
.SYNOPSIS
    Reinicia o apaga el equipo con espera, aviso al usuario y cancelación.

.DESCRIPTION
    Reemplaza los dos scripts duplicados del catálogo original, que estaban en
    categorías distintas y hacían lo mismo.

    Tres cosas que el original no hacía y que importan cuando la orden viene de un
    RMM y no de alguien sentado frente al equipo:

      1. Programa la acción con espera en vez de ejecutarla al instante, así el script
         alcanza a devolver su resultado a la consola antes de que el equipo se vaya.
         Sin eso, el agente muere con el sistema y la ejecución queda como fallida
         aunque haya funcionado.
      2. Avisa al usuario logueado, con un mensaje que aparece en su escritorio.
      3. Permite cancelar una acción ya programada (-Modo cancelar), que es lo que se
         necesita cuando se programó de más o el usuario pide un rato más.

    Antes de actuar informa quién está usando el equipo y cuánto lleva encendido, para
    decidir con datos en vez de a ciegas.

.PARAMETER Modo
    estado (por defecto), reiniciar, apagar, cancelar.

.PARAMETER EsperaSegundos
    Espera antes de actuar. Por defecto 120. Mínimo 30, para que el script alcance a
    responder y el usuario a leer el aviso.

.PARAMETER Mensaje
    Texto que se le muestra al usuario logueado.

.PARAMETER Forzar
    Cierra las aplicaciones sin esperar a que guarden. Puede perder trabajo sin guardar.

.EXAMPLE
    sistema-reiniciar-apagar.ps1
    sistema-reiniciar-apagar.ps1 -Modo reiniciar -EsperaSegundos 300
    sistema-reiniciar-apagar.ps1 -Modo cancelar
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "reiniciar", "apagar", "cancelar")]
    [string]$Modo = "estado",

    [ValidateRange(30, 86400)]
    [int]$EsperaSegundos = 120,

    [string]$Mensaje = "",

    [switch]$Forzar
)

$ErrorActionPreference = "Continue"

Write-Output "== Estado del equipo =="
Write-Output "  equipo: $env:COMPUTERNAME"

try {
    $sistemaOperativo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $arranque = $sistemaOperativo.LastBootUpTime
    $encendido = (Get-Date) - $arranque
    Write-Output "  último arranque: $arranque"
    Write-Output "  encendido hace:  $([int]$encendido.TotalDays) día(s), $($encendido.Hours) hora(s)"
}
catch {
    Write-Output "  no se pudo leer el tiempo de actividad: $($_.Exception.Message)"
}

# Saber si hay alguien trabajando cambia la decisión: no es lo mismo reiniciar un
# servidor sin sesiones que la estación de alguien a media tarea.
$sesiones = @()
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    if ($sistema.UserName) {
        Write-Output "  usuario en consola: $($sistema.UserName)"
        $sesiones += $sistema.UserName
    }
    else {
        Write-Output "  usuario en consola: (ninguno)"
    }
}
catch {
    Write-Output "  no se pudo determinar el usuario en consola."
}

# quser cubre las sesiones remotas, que Win32_ComputerSystem no reporta.
try {
    $salidaQuser = & quser 2>$null
    if ($LASTEXITCODE -eq 0 -and $salidaQuser -and $salidaQuser.Count -gt 1) {
        Write-Output ""
        Write-Output "  Sesiones activas:"
        foreach ($linea in ($salidaQuser | Select-Object -Skip 1)) {
            Write-Output "    $($linea.Trim())"
        }
    }
}
catch {
    Write-Verbose "quser no disponible"
}

# Un apagado ya programado tiene que verse: programar dos veces falla y confunde.
$shutdownProgramado = $false
try {
    $procesos = @(Get-Process -Name "shutdown" -ErrorAction SilentlyContinue)
    if ($procesos.Count -gt 0) { $shutdownProgramado = $true }
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output ""
Write-Output "  apagado/reinicio ya programado: $(if ($shutdownProgramado) { 'sí (posiblemente)' } else { 'no detectado' })"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se programó nada."
    Write-Output "Modos: reiniciar, apagar, cancelar."
    exit 0
}

if ($Modo -eq "cancelar") {
    Write-Output ""
    Write-Output "== Cancelando apagado o reinicio programado =="
    $salida = & shutdown /a 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  Cancelado."
        exit 0
    }
    # 1116 = no hay ningún apagado en curso. No es un error real: es la respuesta
    # "no había nada que cancelar", y tratarla como falla genera ruido.
    if ($LASTEXITCODE -eq 1116) {
        Write-Output "  No había ningún apagado ni reinicio programado."
        exit 0
    }
    Write-Output "  shutdown /a devolvió $LASTEXITCODE : $($salida -join ' ')"
    exit 1
}

$accion = if ($Modo -eq "reiniciar") { "reinicio" } else { "apagado" }

if (-not $Mensaje) {
    $minutos = [Math]::Round($EsperaSegundos / 60, 1)
    $Mensaje = "Soporte programó un $accion de este equipo en $minutos minuto(s). Guardá tu trabajo."
}

Write-Output ""
Write-Output "== Programando $accion en $EsperaSegundos segundo(s) =="
Write-Output "  mensaje al usuario: $Mensaje"
if ($Forzar) {
    Write-Output "  MODO FORZADO: las aplicaciones se cierran sin esperar. Puede perderse"
    Write-Output "  trabajo sin guardar."
}

$argumentos = New-Object System.Collections.ArrayList
if ($Modo -eq "reiniciar") { [void]$argumentos.Add("/r") } else { [void]$argumentos.Add("/s") }
[void]$argumentos.Add("/t")
[void]$argumentos.Add("$EsperaSegundos")
[void]$argumentos.Add("/c")
# El mensaje de shutdown admite hasta 512 caracteres; se recorta antes para que el
# comando no falle por eso.
[void]$argumentos.Add($Mensaje.Substring(0, [Math]::Min(500, $Mensaje.Length)))
if ($Forzar) { [void]$argumentos.Add("/f") }
# /d indica el motivo: 4 = planificado, 1 = mantenimiento de la aplicación. Queda
# registrado en el visor de eventos y evita el diálogo de "motivo inesperado".
[void]$argumentos.Add("/d")
[void]$argumentos.Add("p:4:1")

$salida = & shutdown @argumentos 2>&1
$codigo = $LASTEXITCODE

if ($codigo -ne 0) {
    Write-Output ""
    Write-Output "  ERROR: shutdown devolvió $codigo"
    Write-Output "  $($salida -join ' ')"
    if ($codigo -eq 1190) {
        Write-Output "  El código 1190 significa que ya había un apagado programado."
        Write-Output "  Cancelalo primero con -Modo cancelar."
    }
    exit 1
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $accion programado para: $((Get-Date).AddSeconds($EsperaSegundos))"
Write-Output "  Se puede cancelar con: -Modo cancelar"
Write-Output ""
Write-Output "  El agente se va a desconectar cuando el equipo actúe. Eso NO es una"
Write-Output "  falla: el equipo aparecerá caído hasta que vuelva a registrarse."
exit 0
