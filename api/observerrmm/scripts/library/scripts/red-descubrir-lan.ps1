<#
.SYNOPSIS
    Descubre equipos activos en la red local del equipo.

.DESCRIPTION
    Solo LEE. Sirve para responder "que hay en esa red" desde un equipo que ya esta
    dentro, sin llevar un escaner al sitio ni instalar nada.

    Combina dos fuentes que se complementan:

      1. La tabla ARP/vecinos del propio equipo (Get-NetNeighbor), que ya conoce a
         todo lo que le hablo recientemente, incluso a lo que no responde ping.
      2. Un barrido de ping en paralelo sobre la subred, para encontrar lo que esta
         encendido pero todavia no aparecio en la tabla.

    Solo barre subredes /24 o mas chicas. Una /16 son 65.534 direcciones: el barrido
    tardaria horas y saturaria el enlace, asi que el script se niega y lo dice, en vez
    de quedarse colgado hasta que el timeout lo mate.

    Traduce el prefijo del fabricante (OUI) solo cuando puede: no incluye una base de
    datos de fabricantes, porque eso seria otro dato externo que mantener.

.PARAMETER Subred
    Subred a barrer en formato "10.20.0.0/24". Por defecto, la del adaptador activo.

.PARAMETER SinPing
    Solo reporta la tabla de vecinos, sin barrer.

.PARAMETER TiempoEsperaMs
    Espera por host del ping. Por defecto 400 ms.

.EXAMPLE
    red-descubrir-lan.ps1
    red-descubrir-lan.ps1 -SinPing
    red-descubrir-lan.ps1 -Subred 192.168.1.0/24
#>

[CmdletBinding()]
param(
    [string]$Subred,

    [switch]$SinPing,

    [int]$TiempoEsperaMs = 400
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

function Get-SubredLocal {
    try {
        $configuraciones = @(Get-NetIPConfiguration -ErrorAction Stop |
            Where-Object { $_.IPv4Address -and $_.IPv4DefaultGateway })
    }
    catch {
        Write-Verbose $_.Exception.Message
        return $null
    }
    foreach ($configuracion in $configuraciones) {
        $direccion = $configuracion.IPv4Address | Select-Object -First 1
        if ($direccion) {
            return @{
                IP       = $direccion.IPAddress
                Prefijo  = $direccion.PrefixLength
                Adaptador = $configuracion.InterfaceAlias
            }
        }
    }
    return $null
}

function Get-RangoDesdeCidr {
    param([string]$Cidr)

    $partes = $Cidr.Split("/")
    if ($partes.Count -ne 2) { return $null }

    $direccion = [System.Net.IPAddress]::Any
    if (-not [System.Net.IPAddress]::TryParse($partes[0], [ref]$direccion)) { return $null }

    $prefijo = 0
    if (-not [int]::TryParse($partes[1], [ref]$prefijo)) { return $null }
    if ($prefijo -lt 22 -or $prefijo -gt 30) { return $null }

    $bytes = $direccion.GetAddressBytes()
    [Array]::Reverse($bytes)
    $base = [BitConverter]::ToUInt32($bytes, 0)

    $cantidadHosts = [Math]::Pow(2, 32 - $prefijo) - 2
    $mascara = [uint32]([Math]::Pow(2, 32) - [Math]::Pow(2, 32 - $prefijo))
    $red = $base -band $mascara

    return @{
        Red      = $red
        Cantidad = [int]$cantidadHosts
        Prefijo  = $prefijo
    }
}

function Convert-UInt32AIp {
    param([uint32]$Valor)
    $bytes = [BitConverter]::GetBytes($Valor)
    [Array]::Reverse($bytes)
    return ([System.Net.IPAddress]$bytes).ToString()
}

Write-Output "== Configuracion local =="
$local = Get-SubredLocal
if ($local) {
    Write-Output "  adaptador: $($local.Adaptador)"
    Write-Output "  IP:        $($local.IP)/$($local.Prefijo)"
}
else {
    Write-Output "  No se pudo determinar la red local (sin gateway?)."
}

Write-Output ""
Write-Output "== Tabla de vecinos (ARP) =="

$vecinos = @{}
try {
    $entradas = @(Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.State -ne "Unreachable" -and $_.LinkLayerAddress })
    foreach ($entrada in $entradas) {
        # Se descartan las multicast y broadcast: no son equipos.
        if ($entrada.LinkLayerAddress -eq "ff-ff-ff-ff-ff-ff") { continue }
        if ($entrada.IPAddress -like "224.*" -or $entrada.IPAddress -like "239.*") { continue }
        $vecinos[$entrada.IPAddress] = $entrada.LinkLayerAddress
    }
}
catch {
    Write-Output "  No se pudo leer la tabla de vecinos: $($_.Exception.Message)"
}

foreach ($ip in ($vecinos.Keys | Sort-Object { [System.Version]($_ -replace '^(\d+)\.(\d+)\.(\d+)\.(\d+)$', '$1.$2.$3.$4') })) {
    Write-Output "  $ip  $($vecinos[$ip])"
}
Write-Output "  total: $($vecinos.Count) vecino(s) conocido(s)."

if ($SinPing) {
    Write-Output ""
    Write-Output "Modo -SinPing: no se barrio la subred."
    exit 0
}

if (-not $Subred) {
    if (-not $local) {
        Write-Output ""
        Write-Output "No hay red local detectada y no se paso -Subred: no se puede barrer."
        exit 1
    }
    $Subred = "$($local.IP)/$($local.Prefijo)"
}

$rango = Get-RangoDesdeCidr $Subred
if ($null -eq $rango) {
    Write-Output ""
    Write-Output "No se puede barrer '$Subred'."
    Write-Output "Se aceptan prefijos entre /22 (1.022 hosts) y /30. Una red mas grande"
    Write-Output "tardaria horas y saturaria el enlace; una mas chica no tiene hosts."
    exit 1
}

Write-Output ""
Write-Output "== Barrido de ping ($Subred, $($rango.Cantidad) direcciones) =="
Write-Output "  espera por host: $TiempoEsperaMs ms"

$inicio = Get-Date
$tareas = New-Object System.Collections.ArrayList

# Los pings se lanzan en paralelo con SendPingAsync: hacerlos en serie sobre una /24
# con 400 ms de espera tardaria mas de un minuto y medio solo en los que no responden.
for ($desplazamiento = 1; $desplazamiento -le $rango.Cantidad; $desplazamiento++) {
    $ip = Convert-UInt32AIp ([uint32]($rango.Red + $desplazamiento))
    $ping = New-Object System.Net.NetworkInformation.Ping
    [void]$tareas.Add(@{
        IP    = $ip
        Ping  = $ping
        Tarea = $ping.SendPingAsync($ip, $TiempoEsperaMs)
    })
}

$activos = New-Object System.Collections.ArrayList
foreach ($item in $tareas) {
    try {
        $resultado = $item.Tarea.GetAwaiter().GetResult()
        if ($resultado.Status -eq "Success") {
            [void]$activos.Add(@{
                IP     = $item.IP
                Tiempo = $resultado.RoundtripTime
            })
        }
    }
    catch {
        Write-Verbose "$($item.IP): $($_.Exception.Message)"
    }
    finally {
        $item.Ping.Dispose()
    }
}

$duracion = (Get-Date) - $inicio

# Tras el barrido la tabla ARP tiene entradas nuevas: se relee para poder mostrar la
# MAC de lo que acaba de responder.
$vecinosFinales = @{}
try {
    foreach ($entrada in (Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop)) {
        if ($entrada.LinkLayerAddress) {
            $vecinosFinales[$entrada.IPAddress] = $entrada.LinkLayerAddress
        }
    }
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output ""
foreach ($activo in ($activos | Sort-Object { [int]($_.IP.Split(".")[3]) })) {
    $mac = if ($vecinosFinales.ContainsKey($activo.IP)) { $vecinosFinales[$activo.IP] } else { "(sin MAC en la tabla)" }
    $nombre = ""
    try {
        $nombre = [System.Net.Dns]::GetHostEntry($activo.IP).HostName
    }
    catch {
        Write-Verbose "sin PTR para $($activo.IP)"
    }
    $sufijo = if ($nombre) { "  $nombre" } else { "" }
    Write-Output "  $($activo.IP)  $mac  $($activo.Tiempo) ms$sufijo"
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $($activos.Count) host(s) respondieron de $($rango.Cantidad) probados."
Write-Output "  duracion: $([int]$duracion.TotalSeconds) s"
Write-Output ""
Write-Output "  Un host que no responde puede estar filtrando ICMP: la ausencia aca no"
Write-Output "  prueba que este apagado. Cruzalo con la tabla de vecinos de arriba."
exit 0
