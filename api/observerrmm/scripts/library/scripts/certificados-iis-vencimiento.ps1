<#
.SYNOPSIS
    Revisa el vencimiento de los certificados usados por los sitios de IIS.

.DESCRIPTION
    Solo LEE. Un certificado vencido en un servidor web se descubre por el reclamo del
    cliente, no por el panel: nada avisa antes. Este script existe para que el aviso
    llegue con semanas de anticipación, como check programado.

    Recorre los enlaces HTTPS de cada sitio de IIS, resuelve el certificado que cada
    uno usa por su huella en el almacén del equipo, y reporta a cuántos días vence.

    Es más útil que revisar el almacén de certificados completo, porque el almacén está
    lleno de certificados que a nadie le importan (raíces, intermedios, viejos): acá
    solo aparecen los que un sitio está sirviendo de verdad.

    Sale con 1 si algún certificado en uso vence dentro de la ventana, o ya venció.

.PARAMETER Dias
    Ventana de alerta en días. Por defecto 30.

.EXAMPLE
    certificados-iis-vencimiento.ps1
    certificados-iis-vencimiento.ps1 -Dias 60
#>

[CmdletBinding()]
param(
    [int]$Dias = 30
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

# El módulo WebAdministration es parte del rol de IIS: si no está, el equipo no es un
# servidor web y no hay nada que revisar.
if (-not (Get-Module -ListAvailable -Name WebAdministration)) {
    Write-Output "Este equipo no tiene el rol de IIS instalado (falta WebAdministration)."
    Write-Output "No es un problema: simplemente no hay certificados de IIS que revisar."
    exit 0
}

try {
    Import-Module WebAdministration -ErrorAction Stop
}
catch {
    Write-Output "No se pudo cargar WebAdministration: $($_.Exception.Message)"
    exit 1
}

try {
    $sitios = @(Get-ChildItem -Path "IIS:\Sites" -ErrorAction Stop)
}
catch {
    Write-Output "No se pudieron enumerar los sitios de IIS: $($_.Exception.Message)"
    exit 1
}

if ($sitios.Count -eq 0) {
    Write-Output "IIS está instalado pero no hay sitios configurados."
    exit 0
}

$problemas = New-Object System.Collections.ArrayList
$revisados = 0
$ahora = Get-Date

# Los certificados se cachean por huella: un mismo certificado suele estar en varios
# enlaces y no tiene sentido buscarlo en el almacén una vez por enlace.
$cache = @{}

function Get-CertificadoPorHuella {
    param([string]$Huella)

    if ($cache.ContainsKey($Huella)) { return $cache[$Huella] }

    $encontrado = $null
    # Los certificados de IIS pueden estar en el almacén personal del equipo o en el
    # almacén WebHosting, que es el que usa el hospedaje con muchos sitios.
    foreach ($almacen in @("My", "WebHosting")) {
        $ruta = "Cert:\LocalMachine\$almacen\$Huella"
        try {
            if (Test-Path $ruta) {
                $encontrado = Get-Item $ruta -ErrorAction Stop
                break
            }
        }
        catch {
            Write-Verbose $_.Exception.Message
        }
    }

    $cache[$Huella] = $encontrado
    return $encontrado
}

foreach ($sitio in $sitios) {
    $enlacesHttps = @($sitio.Bindings.Collection | Where-Object { $_.protocol -eq "https" })

    if ($enlacesHttps.Count -eq 0) {
        Write-Output ""
        Write-Output "$($sitio.Name): sin enlaces HTTPS (estado $($sitio.State))"
        continue
    }

    Write-Output ""
    Write-Output "== $($sitio.Name) (estado $($sitio.State)) =="

    foreach ($enlace in $enlacesHttps) {
        Write-Output ""
        Write-Output "  enlace: $($enlace.bindingInformation)"

        $huella = $enlace.certificateHash
        if (-not $huella) {
            Write-Output "    sin certificado asociado a este enlace."
            [void]$problemas.Add("$($sitio.Name): enlace HTTPS sin certificado")
            continue
        }

        if ($huella -is [byte[]]) {
            $huella = ($huella | ForEach-Object { $_.ToString("X2") }) -join ""
        }

        $certificado = Get-CertificadoPorHuella -Huella $huella
        if (-not $certificado) {
            Write-Output "    huella $huella : NO se encontró el certificado en el almacén."
            Write-Output "    El enlace apunta a un certificado que ya no existe: el sitio"
            Write-Output "    no puede servir HTTPS."
            [void]$problemas.Add("$($sitio.Name): certificado $huella ausente del almacén")
            continue
        }

        $revisados++
        $restantes = [int]($certificado.NotAfter - $ahora).TotalDays

        Write-Output "    asunto:      $($certificado.Subject)"
        Write-Output "    emisor:      $($certificado.Issuer)"
        Write-Output "    válido hasta: $($certificado.NotAfter)"
        Write-Output "    días restantes: $restantes"
        if ($certificado.DnsNameList) {
            Write-Output "    nombres:     $(($certificado.DnsNameList | ForEach-Object { $_.Unicode }) -join ', ')"
        }

        if ($restantes -lt 0) {
            Write-Output "    ESTADO: VENCIDO hace $([Math]::Abs($restantes)) día(s)"
            [void]$problemas.Add("$($sitio.Name): certificado VENCIDO hace $([Math]::Abs($restantes)) día(s)")
        }
        elseif ($restantes -le $Dias) {
            Write-Output "    ESTADO: vence dentro de la ventana de $Dias día(s)"
            [void]$problemas.Add("$($sitio.Name): vence en $restantes día(s)")
        }
        else {
            Write-Output "    ESTADO: vigente"
        }

        # Una clave privada ausente hace que el certificado esté "vigente" y el sitio
        # igual no funcione: es un fallo silencioso clásico tras restaurar un backup.
        if (-not $certificado.HasPrivateKey) {
            Write-Output "    AVISO: el certificado NO tiene clave privada asociada."
            [void]$problemas.Add("$($sitio.Name): certificado sin clave privada")
        }
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $($sitios.Count) sitio(s), $revisados certificado(s) en uso revisado(s)."

if ($problemas.Count -eq 0) {
    Write-Output "  Sin certificados vencidos ni por vencer en $Dias día(s)."
    exit 0
}

Write-Output "  $($problemas.Count) observación(es):"
foreach ($problema in $problemas) {
    Write-Output "   - $problema"
}
exit 1
