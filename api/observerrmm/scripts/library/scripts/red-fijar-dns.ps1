<#
.SYNOPSIS
    Fija los servidores DNS de los adaptadores activos, o los devuelve a automatico.

.DESCRIPTION
    El script equivalente del catalogo original clavaba los resolutores de un
    proveedor concreto en el codigo. Aca los servidores son PARAMETRO: cada cliente
    resuelve por donde corresponda, y el mismo script sirve para apuntar a un
    controlador de dominio, a un filtro de contenido contratado o a un resolutor
    publico.

    Omite por defecto los equipos unidos a un dominio: ahi el DNS lo entrega el
    controlador y pisarlo rompe la resolucion de los recursos internos, la
    autenticacion Kerberos y las directivas de grupo. Se puede forzar con -IncluirDominio.

    En modo 'automatico' devuelve el DNS a lo que entregue DHCP.

.PARAMETER Servidores
    Lista de IP separadas por coma, en orden de preferencia. Obligatorio salvo en
    modo 'automatico' o 'estado'.

.PARAMETER Modo
    estado (por defecto), fijar, automatico.

.PARAMETER SoloAdaptador
    Limita la accion a un adaptador por nombre.

.PARAMETER IncluirDominio
    Actua tambien si el equipo esta unido a un dominio.

.EXAMPLE
    red-fijar-dns.ps1
    red-fijar-dns.ps1 -Modo fijar -Servidores "10.20.0.10,10.20.0.11"
    red-fijar-dns.ps1 -Modo automatico
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "fijar", "automatico")]
    [string]$Modo = "estado",

    [string]$Servidores,

    [string]$SoloAdaptador,

    [switch]$IncluirDominio
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

# Codigo operativo de la RFC 2863 que usa ifOperStatus: 1 = la interfaz esta arriba.
$ADAPTADOR_OPERATIVO = 1

function Get-AdaptadorActivo {
    param([string]$Filtro)

    try {
        # ifOperStatus y no Status: Status es el texto que Windows traduce (en un equipo
        # en espanol dice "Activo", no "Up"), mientras que ifOperStatus es el codigo
        # numerico de la RFC 2863, donde 1 = operativo en cualquier idioma.
        $adaptadores = @(Get-NetAdapter -ErrorAction Stop |
            Where-Object { $_.ifOperStatus -eq $ADAPTADOR_OPERATIVO })
    }
    catch {
        Write-Verbose $_.Exception.Message
        return @()
    }
    if ($Filtro) {
        return @($adaptadores | Where-Object { $_.Name -eq $Filtro })
    }
    return $adaptadores
}

function Show-EstadoDnsAdaptador {
    param([string]$Titulo)
    Write-Output ""
    Write-Output "== $Titulo =="
    foreach ($adaptador in (Get-AdaptadorActivo -Filtro $SoloAdaptador)) {
        try {
            $dns = Get-DnsClientServerAddress -InterfaceIndex $adaptador.ifIndex `
                -AddressFamily IPv4 -ErrorAction Stop
            $lista = if ($dns.ServerAddresses) { $dns.ServerAddresses -join ', ' } else { '(automatico o sin DNS)' }
            Write-Output "  $($adaptador.Name): $lista"
        }
        catch {
            Write-Output "  $($adaptador.Name): no se pudo leer ($($_.Exception.Message))"
        }
    }
}

$unidoDominio = $false
try {
    $unidoDominio = (Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop).PartOfDomain
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output "Equipo unido a dominio: $unidoDominio"
Show-EstadoDnsAdaptador -Titulo "DNS actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modifico nada."
    exit 0
}

if ($unidoDominio -and -not $IncluirDominio) {
    Write-Output ""
    Write-Output "El equipo esta unido a un dominio: NO se toca el DNS."
    Write-Output "Pisar el DNS del dominio rompe la resolucion interna, Kerberos y las GPO."
    Write-Output "Si de verdad hace falta, volve a correr con -IncluirDominio."
    exit 0
}

$listaServidores = @()
if ($Modo -eq "fijar") {
    if (-not $Servidores) {
        Write-Output ""
        Write-Output "El modo 'fijar' exige -Servidores, por ejemplo: -Servidores '10.20.0.10,10.20.0.11'"
        exit 1
    }

    foreach ($crudo in $Servidores.Split(",")) {
        $limpio = $crudo.Trim()
        if (-not $limpio) { continue }
        # Validar antes de escribir: una IP mal tipeada deja el equipo sin resolucion
        # y, si es remoto, sin forma de arreglarlo.
        $direccion = [System.Net.IPAddress]::Any
        if (-not [System.Net.IPAddress]::TryParse($limpio, [ref]$direccion)) {
            Write-Output ""
            Write-Output "ABORTADO: '$limpio' no es una direccion IP valida."
            exit 1
        }
        $listaServidores += $limpio
    }

    if ($listaServidores.Count -eq 0) {
        Write-Output "ABORTADO: no se obtuvo ninguna IP valida de -Servidores."
        exit 1
    }

    Write-Output ""
    Write-Output "Se fijaran estos servidores DNS, en orden: $($listaServidores -join ', ')"
}

$adaptadores = Get-AdaptadorActivo -Filtro $SoloAdaptador
if ($adaptadores.Count -eq 0) {
    Write-Output ""
    Write-Output "No hay adaptadores activos sobre los que actuar."
    exit 1
}

$aplicados = 0
$errores = 0

foreach ($adaptador in $adaptadores) {
    Write-Output ""
    Write-Output "  $($adaptador.Name)"
    try {
        if ($Modo -eq "fijar") {
            Set-DnsClientServerAddress -InterfaceIndex $adaptador.ifIndex `
                -ServerAddresses $listaServidores -ErrorAction Stop
        }
        else {
            Set-DnsClientServerAddress -InterfaceIndex $adaptador.ifIndex `
                -ResetServerAddresses -ErrorAction Stop
        }

        # Verificacion por efecto: releer lo que quedo configurado.
        $verificado = Get-DnsClientServerAddress -InterfaceIndex $adaptador.ifIndex `
            -AddressFamily IPv4 -ErrorAction Stop

        if ($Modo -eq "fijar") {
            $faltantes = @($listaServidores | Where-Object { $verificado.ServerAddresses -notcontains $_ })
            if ($faltantes.Count -gt 0) {
                Write-Output "    FALLA: no quedaron aplicados: $($faltantes -join ', ')"
                $errores++
                continue
            }
        }

        Write-Output "    aplicado y verificado."
        $aplicados++
    }
    catch {
        Write-Output "    ERROR: $($_.Exception.Message)"
        $errores++
    }
}

& ipconfig /flushdns | Out-Null
Show-EstadoDnsAdaptador -Titulo "DNS resultante"

Write-Output ""
Write-Output "$aplicados adaptador(es) aplicado(s), $errores con error."

if ($errores -gt 0) { exit 1 }
exit 0
