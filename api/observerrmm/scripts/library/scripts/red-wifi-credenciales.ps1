<#
.SYNOPSIS
    Lista los perfiles WiFi guardados y, opcionalmente, sus contrasenas.

.DESCRIPTION
    Solo LEE. Resuelve el caso concreto de tener que reconectar un equipo a una red
    cuya clave nadie recuerda, o de documentar las redes de un sitio antes de
    recambiar el equipamiento.

    ADVERTENCIA de seguridad: con -MostrarClaves las contrasenas quedan escritas en la
    salida del script, que se guarda en el historial de la consola y viaja por NATS.
    Cualquiera con acceso a ese historial obtiene acceso a las redes WiFi del cliente.
    Por eso el modo por defecto NO las muestra: solo lista que redes hay guardadas.

    Las redes de empresa (WPA2/3-Enterprise, con usuario y certificado) no tienen una
    clave que extraer y aparecen como tales: no es un fallo del script.

.PARAMETER MostrarClaves
    Incluye las contrasenas en texto claro. Ver la advertencia.

.PARAMETER Perfil
    Limita el reporte a un perfil por nombre (SSID).

.EXAMPLE
    red-wifi-credenciales.ps1
    red-wifi-credenciales.ps1 -MostrarClaves
    red-wifi-credenciales.ps1 -MostrarClaves -Perfil "Oficina"
#>

[CmdletBinding()]
param(
    [switch]$MostrarClaves,

    [string]$Perfil
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

# netsh es la unica via para esto: no hay cmdlet de PowerShell que devuelva la clave
# de un perfil WiFi. Su salida esta localizada, asi que se parsea por la estructura
# (lo que hay despues de los dos puntos) y no por el texto de la etiqueta, que cambia
# segun el idioma del Windows.
function Get-ValorNetsh {
    param([string[]]$Lineas, [string[]]$Patrones)
    foreach ($linea in $Lineas) {
        foreach ($patron in $Patrones) {
            if ($linea -match $patron) {
                $partes = $linea.Split(":", 2)
                if ($partes.Count -eq 2) { return $partes[1].Trim() }
            }
        }
    }
    return ""
}

$salidaPerfiles = & netsh wlan show profiles 2>$null
if ($LASTEXITCODE -ne 0 -or -not $salidaPerfiles) {
    Write-Output "No se pudo consultar los perfiles WiFi."
    Write-Output "Es lo esperable en un equipo sin adaptador inalambrico, o si el"
    Write-Output "servicio WLAN AutoConfig esta detenido."
    exit 1
}

# El nombre del perfil es lo que sigue a los dos puntos en las lineas de "todos los
# perfiles de usuario". Se filtra por la presencia de ": " para no depender del idioma.
$nombres = New-Object System.Collections.ArrayList
foreach ($linea in $salidaPerfiles) {
    if ($linea -match "^\s{4,}.*:\s*.+$") {
        $valor = $linea.Split(":", 2)[1].Trim()
        if ($valor -and -not $nombres.Contains($valor)) {
            [void]$nombres.Add($valor)
        }
    }
}

if ($Perfil) {
    $nombres = @($nombres | Where-Object { $_ -eq $Perfil })
    if ($nombres.Count -eq 0) {
        Write-Output "No hay un perfil guardado llamado '$Perfil'."
        exit 1
    }
}

if ($nombres.Count -eq 0) {
    Write-Output "No hay perfiles WiFi guardados en este equipo."
    exit 0
}

Write-Output "$($nombres.Count) perfil(es) WiFi guardado(s)."
if (-not $MostrarClaves) {
    Write-Output "Las contrasenas NO se muestran. Usa -MostrarClaves si de verdad hace falta."
}

$conClave = 0
$empresariales = 0

foreach ($nombre in $nombres) {
    Write-Output ""
    Write-Output "$nombre"

    # El nombre va entre comillas: sin eso, un SSID con espacios se parte en varios
    # argumentos y netsh no encuentra el perfil.
    if ($MostrarClaves) {
        $detalle = & netsh wlan show profile name="$nombre" key=clear 2>$null
    }
    else {
        $detalle = & netsh wlan show profile name="$nombre" 2>$null
    }

    if (-not $detalle) {
        Write-Output "  no se pudo leer el detalle de este perfil."
        continue
    }

    $autenticacion = Get-ValorNetsh -Lineas $detalle -Patrones @("Authentication", "Autenticaci")
    $cifrado = Get-ValorNetsh -Lineas $detalle -Patrones @("Cipher", "Cifrado")
    $conexion = Get-ValorNetsh -Lineas $detalle -Patrones @("Connection mode", "Modo de conexi")

    if ($autenticacion) { Write-Output "  autenticacion:   $autenticacion" }
    if ($cifrado) { Write-Output "  cifrado:         $cifrado" }
    if ($conexion) { Write-Output "  conexion:        $conexion" }

    if ($autenticacion -match "WPA.*Enterprise|802\.1X") {
        Write-Output "  clave:           (red empresarial: usa credenciales, no clave compartida)"
        $empresariales++
        continue
    }

    if ($MostrarClaves) {
        $clave = Get-ValorNetsh -Lineas $detalle -Patrones @("Key Content", "Contenido de la clave")
        if ($clave) {
            Write-Output "  clave:           $clave"
            $conClave++
        }
        else {
            Write-Output "  clave:           (sin clave guardada, o red abierta)"
        }
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $($nombres.Count) perfil(es), $empresariales empresarial(es)."

if ($MostrarClaves) {
    Write-Output "  $conClave clave(s) mostrada(s) en texto claro."
    Write-Output ""
    Write-Output "  Este resultado quedo guardado en el historial de la consola."
    Write-Output "  Borralo cuando termines de usarlo."
}

exit 0
