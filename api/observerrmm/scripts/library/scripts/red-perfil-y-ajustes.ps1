<#
.SYNOPSIS
    Ajusta el perfil de red (privado/público) y el estado de IPv6.

.DESCRIPTION
    Junta los dos ajustes de red que se piden juntos y que el catálogo original tenía
    separados: pasar la red a privada y deshabilitar IPv6.

    El perfil importa porque en red "pública" Windows endurece el firewall y bloquea
    el descubrimiento: una impresora o un recurso compartido que "dejó de verse" a
    veces es sólo esto. Solo se cambian las redes NO administradas por dominio: el
    perfil DomainAuthenticated lo fija el controlador y no es modificable localmente.

    Sobre IPv6: deshabilitarlo suele proponerse como remedio genérico y casi nunca lo
    es. Se ofrece porque hay software viejo que lo necesita, pero conviene medir
    antes. Se actúa por adaptador (no con el parche global de registro, que Microsoft
    desaconseja y que puede dejar servicios que dependen de IPv6 sin funcionar).

.PARAMETER Modo
    estado (por defecto), privada, publica, ipv6-off, ipv6-on.

.PARAMETER SoloAdaptador
    Limita el cambio de IPv6 a un adaptador por nombre.

.EXAMPLE
    red-perfil-y-ajustes.ps1
    red-perfil-y-ajustes.ps1 -Modo privada
    red-perfil-y-ajustes.ps1 -Modo ipv6-off -SoloAdaptador Ethernet
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "privada", "publica", "ipv6-off", "ipv6-on")]
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

function Show-Estado {
    param([string]$Titulo)

    Write-Output ""
    Write-Output "== $Titulo =="

    Write-Output ""
    Write-Output "  Perfiles de conexión:"
    try {
        foreach ($perfil in (Get-NetConnectionProfile -ErrorAction Stop)) {
            Write-Output "    $($perfil.Name) (adaptador: $($perfil.InterfaceAlias))"
            Write-Output "      categoría:            $($perfil.NetworkCategory)"
            Write-Output "      conectividad IPv4:    $($perfil.IPv4Connectivity)"
            Write-Output "      conectividad IPv6:    $($perfil.IPv6Connectivity)"
        }
    }
    catch {
        Write-Output "    no se pudo leer: $($_.Exception.Message)"
    }

    Write-Output ""
    Write-Output "  IPv6 por adaptador:"
    try {
        $enlaces = @(Get-NetAdapterBinding -ComponentID ms_tcpip6 -ErrorAction Stop)
        foreach ($enlace in $enlaces) {
            Write-Output "    $($enlace.Name): $(if ($enlace.Enabled) { 'habilitado' } else { 'deshabilitado' })"
        }
    }
    catch {
        Write-Output "    no se pudo leer: $($_.Exception.Message)"
    }
}

Show-Estado -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    exit 0
}

$errores = 0
$aplicados = 0

if ($Modo -eq "privada" -or $Modo -eq "publica") {
    $categoria = if ($Modo -eq "privada") { "Private" } else { "Public" }

    Write-Output ""
    Write-Output "== Cambiando el perfil de red a $categoria =="

    try {
        $perfiles = @(Get-NetConnectionProfile -ErrorAction Stop)
    }
    catch {
        Write-Output "  No se pudieron enumerar los perfiles: $($_.Exception.Message)"
        exit 1
    }

    foreach ($perfil in $perfiles) {
        Write-Output ""
        Write-Output "  $($perfil.Name) — $($perfil.InterfaceAlias)"

        if ($perfil.NetworkCategory -eq "DomainAuthenticated") {
            Write-Output "    se omite: perfil autenticado por dominio, lo fija el controlador."
            continue
        }
        if ($perfil.NetworkCategory -eq $categoria) {
            Write-Output "    ya estaba en $categoria."
            continue
        }

        try {
            Set-NetConnectionProfile -InterfaceIndex $perfil.InterfaceIndex `
                -NetworkCategory $categoria -ErrorAction Stop

            $verificado = Get-NetConnectionProfile -InterfaceIndex $perfil.InterfaceIndex -ErrorAction Stop
            if ($verificado.NetworkCategory -ne $categoria) {
                Write-Output "    FALLA: quedó en $($verificado.NetworkCategory)."
                $errores++
            }
            else {
                Write-Output "    cambiado a $categoria y verificado."
                $aplicados++
            }
        }
        catch {
            Write-Output "    ERROR: $($_.Exception.Message)"
            $errores++
        }
    }
}
else {
    $habilitar = $Modo -eq "ipv6-on"

    Write-Output ""
    Write-Output "== $(if ($habilitar) { 'Habilitando' } else { 'Deshabilitando' }) IPv6 por adaptador =="

    if (-not $habilitar) {
        Write-Output "  Recordá que deshabilitar IPv6 rara vez es la causa real de un problema."
    }

    try {
        $enlaces = @(Get-NetAdapterBinding -ComponentID ms_tcpip6 -ErrorAction Stop)
    }
    catch {
        Write-Output "  No se pudieron enumerar los enlaces: $($_.Exception.Message)"
        exit 1
    }

    if ($SoloAdaptador) {
        $enlaces = @($enlaces | Where-Object { $_.Name -eq $SoloAdaptador })
        if ($enlaces.Count -eq 0) {
            Write-Output "  No se encontró el adaptador '$SoloAdaptador'."
            exit 1
        }
    }

    foreach ($enlace in $enlaces) {
        Write-Output ""
        Write-Output "  $($enlace.Name)"

        if ($enlace.Enabled -eq $habilitar) {
            Write-Output "    ya estaba $(if ($habilitar) { 'habilitado' } else { 'deshabilitado' })."
            continue
        }

        try {
            if ($habilitar) {
                Enable-NetAdapterBinding -Name $enlace.Name -ComponentID ms_tcpip6 -ErrorAction Stop
            }
            else {
                Disable-NetAdapterBinding -Name $enlace.Name -ComponentID ms_tcpip6 -ErrorAction Stop
            }

            $verificado = Get-NetAdapterBinding -Name $enlace.Name -ComponentID ms_tcpip6 -ErrorAction Stop
            if ($verificado.Enabled -ne $habilitar) {
                Write-Output "    FALLA: quedó en Enabled=$($verificado.Enabled)."
                $errores++
            }
            else {
                Write-Output "    aplicado y verificado."
                $aplicados++
            }
        }
        catch {
            Write-Output "    ERROR: $($_.Exception.Message)"
            $errores++
        }
    }
}

Show-Estado -Titulo "Estado resultante"

Write-Output ""
Write-Output "$aplicados cambio(s) aplicado(s), $errores con error."

if ($errores -gt 0) { exit 1 }
exit 0
