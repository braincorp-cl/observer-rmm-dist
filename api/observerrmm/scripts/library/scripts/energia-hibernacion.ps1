<#
.SYNOPSIS
    Deshabilita o habilita la hibernacion y el inicio rapido de Windows.

.DESCRIPTION
    Une los dos scripts del catalogo original (deshabilitar hibernacion y deshabilitar
    inicio rapido) porque son el mismo interruptor: el inicio rapido (Fast Startup)
    depende del archivo de hibernacion, asi que apagar la hibernacion se lo lleva
    puesto, y dejarlos desalineados produce configuraciones raras.

    Por que deshabilitarlos, en un contexto de administracion remota: con inicio
    rapido, "apagar" no apaga - Windows hiberna el kernel. El resultado es que los
    parches que exigen reinicio no terminan de aplicarse, el equipo acumula tiempo de
    actividad invisible y los problemas que un reinicio arreglaria sobreviven al
    apagado. Ademas libera del disco un archivo del tamano de la RAM.

    Contrapartida honesta: en portatiles la hibernacion es util de verdad y apagarla
    hace que una bateria agotada pierda la sesion. El script avisa si detecta bateria.

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

    Write-Output "  hibernacion:    $(if ($null -eq $hibernacion) { 'no se pudo leer' } elseif ($hibernacion) { 'habilitada' } else { 'deshabilitada' })"
    Write-Output "  inicio rapido:  $(if ($null -eq $inicioRapido) { 'no definido (equivale a habilitado)' } elseif ($inicioRapido) { 'habilitado' } else { 'deshabilitado' })"
    if ($tamano -gt 0) {
        Write-Output "  hiberfil.sys:   $([Math]::Round($tamano / 1GB, 2)) GB en $($env:SystemDrive)\"
    }
    else {
        Write-Output "  hiberfil.sys:   no existe"
    }
}

# La bateria importa para la recomendacion, no para la accion.
$tieneBateria = $false
try {
    $baterias = @(Get-CimInstance -ClassName Win32_Battery -ErrorAction Stop)
    $tieneBateria = $baterias.Count -gt 0
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output "Equipo con bateria: $tieneBateria"
Show-Estado -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modifico nada."
    exit 0
}

if ($Modo -eq "deshabilitar" -and $tieneBateria) {
    Write-Output ""
    Write-Output "AVISO: este equipo tiene bateria. Sin hibernacion, si la bateria se"
    Write-Output "agota estando suspendido, la sesion se pierde sin guardar."
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

# powercfg /hibernate es la via correcta: crea o borra hiberfil.sys y ajusta el
# registro de forma consistente. Tocar solo el registro deja el archivo en disco.
if ($Modo -eq "deshabilitar") {
    $salida = & powercfg /hibernate off 2>&1
}
else {
    $salida = & powercfg /hibernate on 2>&1
}

if ($LASTEXITCODE -ne 0) {
    Write-Output "  ERROR: powercfg devolvio $LASTEXITCODE"
    Write-Output "  $($salida -join ' ')"
    exit 1
}
Write-Output "  powercfg /hibernate $(if ($Modo -eq 'deshabilitar') { 'off' } else { 'on' }): OK"

# El inicio rapido se ajusta aparte: al rehabilitar la hibernacion, Windows no lo
# vuelve a encender solo, y al apagarla conviene dejar el valor explicito en 0 para
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

# Verificacion por efecto: el estado leido del registro, no el codigo de powercfg.
$hibernacionFinal = Get-EstadoHibernacion
$esperado = $Modo -eq "habilitar"
if ($null -ne $hibernacionFinal -and $hibernacionFinal -ne $esperado) {
    Write-Output ""
    Write-Output "FALLA: la hibernacion quedo en un estado distinto al pedido."
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
Write-Output "Aplicado. El inicio rapido toma efecto en el proximo apagado."
exit 0
