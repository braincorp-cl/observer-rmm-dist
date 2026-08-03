<#
.SYNOPSIS
    Deshabilita o habilita la hibernación y el inicio rápido de Windows.

.DESCRIPTION
    Une los dos scripts del catálogo original (deshabilitar hibernación y deshabilitar
    inicio rápido) porque son el mismo interruptor: el inicio rápido (Fast Startup)
    depende del archivo de hibernación, así que apagar la hibernación se lo lleva
    puesto, y dejarlos desalineados produce configuraciones raras.

    Por qué deshabilitarlos, en un contexto de administración remota: con inicio
    rápido, "apagar" no apaga — Windows hiberna el kernel. El resultado es que los
    parches que exigen reinicio no terminan de aplicarse, el equipo acumula tiempo de
    actividad invisible y los problemas que un reinicio arreglaría sobreviven al
    apagado. Además libera del disco un archivo del tamaño de la RAM.

    Contrapartida honesta: en portátiles la hibernación es útil de verdad y apagarla
    hace que una batería agotada pierda la sesión. El script avisa si detecta batería.

.PARAMETER Modo
    estado (por defecto), deshabilitar, habilitar.

.EXAMPLE
    energia-hibernacion.ps1
    energia-hibernacion.ps1 -Modo deshabilitar
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "deshabilitar", "habilitar")]
    [string]$Modo = "estado"
)

$ErrorActionPreference = "Continue"

$rutaInicioRapido = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power"
$rutaHibernacion = "HKLM:\SYSTEM\CurrentControlSet\Control\Power"

function Get-EstadoHibernacion {
    try {
        $valor = (Get-ItemProperty -Path $rutaHibernacion -Name HibernateEnabled -ErrorAction Stop).HibernateEnabled
        return [int]$valor -eq 1
    }
    catch {
        Write-Verbose $_.Exception.Message
        return $null
    }
}

function Get-EstadoInicioRapido {
    try {
        $valor = (Get-ItemProperty -Path $rutaInicioRapido -Name HiberbootEnabled -ErrorAction Stop).HiberbootEnabled
        return [int]$valor -eq 1
    }
    catch {
        Write-Verbose $_.Exception.Message
        return $null
    }
}

function Get-TamanoHiberfil {
    $ruta = Join-Path ($env:SystemDrive + "\") "hiberfil.sys"
    try {
        # hiberfil.sys es un archivo de sistema oculto: Get-Item necesita -Force.
        $archivo = Get-Item -LiteralPath $ruta -Force -ErrorAction Stop
        return $archivo.Length
    }
    catch {
        return 0
    }
}

function Show-Estado {
    param([string]$Titulo)

    Write-Output ""
    Write-Output "== $Titulo =="

    $hibernacion = Get-EstadoHibernacion
    $inicioRapido = Get-EstadoInicioRapido
    $tamano = Get-TamanoHiberfil

    Write-Output "  hibernación:    $(if ($null -eq $hibernacion) { 'no se pudo leer' } elseif ($hibernacion) { 'habilitada' } else { 'deshabilitada' })"
    Write-Output "  inicio rápido:  $(if ($null -eq $inicioRapido) { 'no definido (equivale a habilitado)' } elseif ($inicioRapido) { 'habilitado' } else { 'deshabilitado' })"
    if ($tamano -gt 0) {
        Write-Output "  hiberfil.sys:   $([Math]::Round($tamano / 1GB, 2)) GB en $($env:SystemDrive)\"
    }
    else {
        Write-Output "  hiberfil.sys:   no existe"
    }
}

# La batería importa para la recomendación, no para la acción.
$tieneBateria = $false
try {
    $baterias = @(Get-CimInstance -ClassName Win32_Battery -ErrorAction Stop)
    $tieneBateria = $baterias.Count -gt 0
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output "Equipo con batería: $tieneBateria"
Show-Estado -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    exit 0
}

if ($Modo -eq "deshabilitar" -and $tieneBateria) {
    Write-Output ""
    Write-Output "AVISO: este equipo tiene batería. Sin hibernación, si la batería se"
    Write-Output "agota estando suspendido, la sesión se pierde sin guardar."
}

$libreAntes = $null
try {
    $unidad = Get-PSDrive -Name ($env:SystemDrive -replace ":", "") -ErrorAction Stop
    $libreAntes = $unidad.Free
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output ""
Write-Output "== Aplicando: $Modo =="

# powercfg /hibernate es la vía correcta: crea o borra hiberfil.sys y ajusta el
# registro de forma consistente. Tocar solo el registro deja el archivo en disco.
if ($Modo -eq "deshabilitar") {
    $salida = & powercfg /hibernate off 2>&1
}
else {
    $salida = & powercfg /hibernate on 2>&1
}

if ($LASTEXITCODE -ne 0) {
    Write-Output "  ERROR: powercfg devolvió $LASTEXITCODE"
    Write-Output "  $($salida -join ' ')"
    exit 1
}
Write-Output "  powercfg /hibernate $(if ($Modo -eq 'deshabilitar') { 'off' } else { 'on' }): OK"

# El inicio rápido se ajusta aparte: al rehabilitar la hibernación, Windows no lo
# vuelve a encender solo, y al apagarla conviene dejar el valor explícito en 0 para
# que no quede indefinido.
$valorInicioRapido = if ($Modo -eq "deshabilitar") { 0 } else { 1 }
try {
    Set-ItemProperty -Path $rutaInicioRapido -Name HiberbootEnabled `
        -Value $valorInicioRapido -Type DWord -ErrorAction Stop
    Write-Output "  HiberbootEnabled = $valorInicioRapido : OK"
}
catch {
    Write-Output "  ERROR al escribir HiberbootEnabled: $($_.Exception.Message)"
    exit 1
}

Show-Estado -Titulo "Estado resultante"

# Verificación por efecto: el estado leído del registro, no el código de powercfg.
$hibernacionFinal = Get-EstadoHibernacion
$esperado = $Modo -eq "habilitar"
if ($null -ne $hibernacionFinal -and $hibernacionFinal -ne $esperado) {
    Write-Output ""
    Write-Output "FALLA: la hibernación quedó en un estado distinto al pedido."
    exit 1
}

if ($null -ne $libreAntes) {
    try {
        $unidad = Get-PSDrive -Name ($env:SystemDrive -replace ":", "") -ErrorAction Stop
        $diferencia = $unidad.Free - $libreAntes
        Write-Output ""
        Write-Output "  espacio liberado en $($env:SystemDrive): $([Math]::Round($diferencia / 1GB, 2)) GB"
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}

Write-Output ""
Write-Output "Aplicado. El inicio rápido toma efecto en el próximo apagado."
exit 0
