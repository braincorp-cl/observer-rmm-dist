<#
.SYNOPSIS
    Remedia problemas de red: renueva IP, reinicia la pila TCP/IP o vuelve a DHCP.

.DESCRIPTION
    Reemplaza los tres scripts separados del catálogo original (renovar IP, resetear
    TCP con netsh, poner la NIC en DHCP) por uno con modo, porque son los tres pasos
    del mismo procedimiento y casi nunca se corre uno solo.

    Escala de menor a mayor invasividad:

      renovar  — libera y renueva la concesión DHCP. No corta la sesión salvo unos
                 segundos. Es el primer intento razonable.
      dhcp     — devuelve los adaptadores a DHCP (IP y DNS). Si el equipo tenía IP
                 fija por algo, esto la pierde.
      reset    — reinicia la pila TCP/IP, Winsock y el firewall a valores de fábrica.
                 EXIGE REINICIO del equipo para completarse.

    ADVERTENCIA: cualquiera de los tres puede cortar la conexión del agente. Si el
    equipo está en el otro extremo del país y algo sale mal, no vuelve solo. El modo
    'reset' además deja el equipo a medias hasta que se reinicie.

    Por eso el modo por defecto es 'estado', que solo informa la configuración actual.

.PARAMETER Modo
    estado (por defecto), renovar, dhcp, reset.

.PARAMETER SoloAdaptador
    Limita la acción a un adaptador por nombre (por ejemplo "Ethernet").

.EXAMPLE
    red-remediar-pila.ps1
    red-remediar-pila.ps1 -Modo renovar
    red-remediar-pila.ps1 -Modo dhcp -SoloAdaptador Ethernet
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "renovar", "dhcp", "reset")]
    [string]$Modo = "estado",

    [string]$SoloAdaptador
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

function Get-AdaptadorActivo {
    try {
        $adaptadores = @(Get-NetAdapter -ErrorAction Stop | Where-Object { $_.Status -eq "Up" })
    }
    catch {
        Write-Verbose $_.Exception.Message
        return @()
    }
    if ($SoloAdaptador) {
        return @($adaptadores | Where-Object { $_.Name -eq $SoloAdaptador })
    }
    return $adaptadores
}

function Show-Configuracion {
    param([string]$Titulo)

    Write-Output ""
    Write-Output "== $Titulo =="

    $adaptadores = Get-AdaptadorActivo
    if ($adaptadores.Count -eq 0) {
        Write-Output "  No hay adaptadores activos que coincidan."
        return
    }

    foreach ($adaptador in $adaptadores) {
        Write-Output ""
        Write-Output "  $($adaptador.Name) — $($adaptador.InterfaceDescription)"
        Write-Output "    estado:     $($adaptador.Status) / $($adaptador.LinkSpeed)"

        try {
            $configuracion = Get-NetIPConfiguration -InterfaceIndex $adaptador.ifIndex -ErrorAction Stop
            $direcciones = @($configuracion.IPv4Address | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" })
            Write-Output "    IPv4:       $(if ($direcciones) { $direcciones -join ', ' } else { '(sin dirección)' })"
            Write-Output "    gateway:    $(if ($configuracion.IPv4DefaultGateway) { $configuracion.IPv4DefaultGateway.NextHop } else { '(sin gateway)' })"
            Write-Output "    DNS:        $(if ($configuracion.DNSServer.ServerAddresses) { $configuracion.DNSServer.ServerAddresses -join ', ' } else { '(sin DNS)' })"
        }
        catch {
            Write-Output "    no se pudo leer la configuración IP: $($_.Exception.Message)"
        }

        try {
            $interfaz = Get-NetIPInterface -InterfaceIndex $adaptador.ifIndex -AddressFamily IPv4 -ErrorAction Stop
            Write-Output "    DHCP:       $($interfaz.Dhcp)"
        }
        catch {
            Write-Verbose $_.Exception.Message
        }
    }
}

Show-Configuracion -Titulo "Configuración actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    Write-Output "Modos que actúan: renovar (suave), dhcp (pierde IP fija), reset (exige reinicio)."
    exit 0
}

$adaptadores = Get-AdaptadorActivo
if ($adaptadores.Count -eq 0 -and $Modo -ne "reset") {
    Write-Output ""
    Write-Output "No hay adaptadores activos sobre los que actuar."
    exit 1
}

$errores = 0

switch ($Modo) {
    "renovar" {
        Write-Output ""
        Write-Output "== Liberando y renovando la concesión DHCP =="
        # ipconfig actúa sobre todos los adaptadores: no acepta filtrar por nombre,
        # así que -SoloAdaptador no aplica en este modo y conviene decirlo.
        if ($SoloAdaptador) {
            Write-Output "  AVISO: ipconfig /release y /renew actúan sobre TODOS los"
            Write-Output "         adaptadores; -SoloAdaptador se ignora en este modo."
        }
        & ipconfig /release | Out-Null
        Start-Sleep -Seconds 2
        $salida = & ipconfig /renew
        if ($LASTEXITCODE -ne 0) {
            Write-Output "  ipconfig /renew devolvió código $LASTEXITCODE"
            $errores++
        }
        else {
            Write-Output "  concesión renovada."
        }
        Write-Verbose ($salida -join "`n")

        Write-Output "  vaciando la caché de DNS..."
        & ipconfig /flushdns | Out-Null
    }

    "dhcp" {
        Write-Output ""
        Write-Output "== Devolviendo adaptadores a DHCP =="
        foreach ($adaptador in $adaptadores) {
            Write-Output ""
            Write-Output "  $($adaptador.Name)"
            try {
                $interfaz = Get-NetIPInterface -InterfaceIndex $adaptador.ifIndex -AddressFamily IPv4 -ErrorAction Stop
                if ($interfaz.Dhcp -eq "Enabled") {
                    Write-Output "    ya estaba en DHCP: no se toca la IP."
                }
                else {
                    # El gateway hay que quitarlo aparte: si queda una ruta estática,
                    # el adaptador toma IP por DHCP pero sigue enrutando por la vieja.
                    Remove-NetRoute -InterfaceIndex $adaptador.ifIndex -DestinationPrefix "0.0.0.0/0" `
                        -Confirm:$false -ErrorAction SilentlyContinue
                    Set-NetIPInterface -InterfaceIndex $adaptador.ifIndex -Dhcp Enabled -ErrorAction Stop
                    Write-Output "    IP devuelta a DHCP."
                }

                Set-DnsClientServerAddress -InterfaceIndex $adaptador.ifIndex -ResetServerAddresses -ErrorAction Stop
                Write-Output "    DNS devuelto a automático."
            }
            catch {
                Write-Output "    ERROR: $($_.Exception.Message)"
                $errores++
            }
        }

        & ipconfig /renew | Out-Null
    }

    "reset" {
        Write-Output ""
        Write-Output "== Reiniciando la pila de red a valores de fábrica =="
        Write-Output "  Esto NO se completa hasta que el equipo se reinicie."

        $comandos = @(
            @("int ip reset", "pila TCP/IP"),
            @("winsock reset", "catálogo Winsock"),
            @("advfirewall reset", "firewall de Windows"),
            @("int ipv4 reset", "IPv4"),
            @("int ipv6 reset", "IPv6")
        )

        foreach ($par in $comandos) {
            $argumentos = $par[0]
            $descripcion = $par[1]
            $salida = & netsh $argumentos.Split(" ")
            if ($LASTEXITCODE -eq 0) {
                Write-Output "  OK    $descripcion"
            }
            else {
                Write-Output "  ERROR $descripcion (netsh devolvió $LASTEXITCODE)"
                Write-Verbose ($salida -join "`n")
                $errores++
            }
        }

        & ipconfig /flushdns | Out-Null
        Write-Output ""
        Write-Output "  PENDIENTE: reiniciá el equipo para que el reset tome efecto."
    }
}

Show-Configuracion -Titulo "Configuración resultante"

Write-Output ""
if ($errores -gt 0) {
    Write-Output "Terminó con $errores error(es)."
    exit 1
}
Write-Output "Terminó sin errores."
exit 0
