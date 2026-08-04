<#
.SYNOPSIS
    Salud de los discos y volumenes, con reparacion opcional.

.DESCRIPTION
    Une el chequeo de disco y la lectura de errores del registro de eventos, que el
    catalogo original tenia como dos scripts, porque son las dos mitades del mismo
    diagnostico: el estado que reporta el disco ahora y los errores que ya registro.

    Tres fuentes, de menos a mas invasiva:

      estado    - SMART/estado de los discos fisicos, salud de los volumenes y
                  errores recientes de disco en el registro de eventos. No toca nada.
      verificar - corre chkdsk en modo SOLO LECTURA. No repara, no bloquea el
                  volumen, no exige reinicio. Puede tardar en discos grandes.
      reparar   - chkdsk /F. EXIGE bloquear el volumen: en la unidad del sistema eso
                  significa que la reparacion queda AGENDADA PARA EL PROXIMO REINICIO,
                  y ese reinicio puede tardar mucho con el equipo inutilizable.

    Por eso 'reparar' no reinicia por su cuenta ni programa un reinicio: solo agenda
    el chkdsk y lo informa, para que el reinicio sea una decision con ventana.

.PARAMETER Modo
    estado (por defecto), verificar, reparar.

.PARAMETER Unidad
    Unidad sobre la que actuar, por ejemplo "C:". Obligatorio en verificar y reparar.

.PARAMETER Dias
    Ventana en dias para los eventos de disco. Por defecto 7.

.EXAMPLE
    disco-salud-reparacion.ps1
    disco-salud-reparacion.ps1 -Modo verificar -Unidad C:
    disco-salud-reparacion.ps1 -Modo reparar -Unidad D:
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "verificar", "reparar")]
    [string]$Modo = "estado",

    [string]$Unidad,

    [int]$Dias = 7
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

$problemas = New-Object System.Collections.ArrayList

Write-Output "== Discos fisicos =="
try {
    foreach ($disco in (Get-PhysicalDisk -ErrorAction Stop | Sort-Object DeviceId)) {
        Write-Output ""
        Write-Output "  $($disco.FriendlyName)"
        Write-Output "    tipo:            $($disco.MediaType) / $($disco.BusType)"
        Write-Output "    tamano:          $([Math]::Round($disco.Size / 1GB, 1)) GB"
        Write-Output "    salud:           $($disco.HealthStatus)"
        Write-Output "    estado:          $($disco.OperationalStatus)"
        if ($null -ne $disco.Usage) {
            Write-Output "    uso:             $($disco.Usage)"
        }

        if ($disco.HealthStatus -ne "Healthy") {
            [void]$problemas.Add("disco '$($disco.FriendlyName)' con salud $($disco.HealthStatus)")
        }

        # El contador de reasignaciones y las horas de uso viven en otra clase y son
        # la senal temprana real de un disco que se esta muriendo, antes de que
        # HealthStatus cambie.
        try {
            $confiabilidad = Get-StorageReliabilityCounter -PhysicalDisk $disco -ErrorAction Stop
            if ($null -ne $confiabilidad.Wear) {
                Write-Output "    desgaste:        $($confiabilidad.Wear)%"
            }
            if ($null -ne $confiabilidad.Temperature) {
                Write-Output "    temperatura:     $($confiabilidad.Temperature) C"
            }
            if ($null -ne $confiabilidad.PowerOnHours) {
                Write-Output "    horas encendido: $($confiabilidad.PowerOnHours)"
            }
            if ($confiabilidad.ReadErrorsUncorrected -gt 0 -or $confiabilidad.WriteErrorsUncorrected -gt 0) {
                Write-Output "    errores NO corregidos: lectura $($confiabilidad.ReadErrorsUncorrected), escritura $($confiabilidad.WriteErrorsUncorrected)"
                [void]$problemas.Add("disco '$($disco.FriendlyName)' con errores no corregidos")
            }
        }
        catch {
            Write-Verbose $_.Exception.Message
        }
    }
}
catch {
    Write-Output "  No se pudo consultar los discos fisicos: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "== Volumenes =="
try {
    foreach ($volumen in (Get-Volume -ErrorAction Stop | Where-Object { $_.DriveLetter })) {
        $totalGb = [Math]::Round($volumen.Size / 1GB, 1)
        $libreGb = [Math]::Round($volumen.SizeRemaining / 1GB, 1)
        $porcentajeLibre = if ($volumen.Size -gt 0) { [Math]::Round(100 * $volumen.SizeRemaining / $volumen.Size, 1) } else { 0 }

        Write-Output ""
        Write-Output "  $($volumen.DriveLetter): $($volumen.FileSystemLabel)"
        Write-Output "    sistema de archivos: $($volumen.FileSystem)"
        Write-Output "    tamano:              $totalGb GB"
        Write-Output "    libre:               $libreGb GB ($porcentajeLibre%)"
        Write-Output "    salud:               $($volumen.HealthStatus)"

        if ($volumen.HealthStatus -ne "Healthy") {
            [void]$problemas.Add("volumen $($volumen.DriveLetter): con salud $($volumen.HealthStatus)")
        }
    }
}
catch {
    Write-Output "  No se pudo consultar los volumenes: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "== Errores de disco en el registro de eventos (ultimos $Dias dia[s]) =="

# Los proveedores que importan: 'disk' y 'Ntfs' reportan errores de medio y de sistema
# de archivos; 'volmgr' reporta fallas de volumen. Un error aca suele preceder por
# semanas a la falla que el usuario nota.
try {
    $desde = (Get-Date).AddDays(-1 * [Math]::Abs($Dias))
    $filtro = @{
        LogName      = "System"
        ProviderName = @("disk", "Ntfs", "volmgr", "Disk")
        Level        = @(1, 2, 3)
        StartTime    = $desde
    }
    $eventos = @(Get-WinEvent -FilterHashtable $filtro -ErrorAction Stop)
}
catch {
    $eventos = @()
    if ($_.Exception.Message -notmatch "No events were found|No se encontraron eventos") {
        Write-Output "  No se pudieron consultar los eventos: $($_.Exception.Message)"
    }
}

if ($eventos.Count -eq 0) {
    Write-Output "  Sin errores ni advertencias de disco en la ventana consultada."
}
else {
    $agrupados = $eventos | Group-Object Id | Sort-Object Count -Descending
    foreach ($grupo in $agrupados) {
        $ejemplo = $grupo.Group | Sort-Object TimeCreated -Descending | Select-Object -First 1
        Write-Output ""
        Write-Output "  evento $($grupo.Name) - $($grupo.Count) vez/veces, ultimo: $($ejemplo.TimeCreated)"
        $mensaje = $ejemplo.Message
        if ($mensaje) {
            $primera = ($mensaje -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
            Write-Output "    $primera"
        }
    }
    [void]$problemas.Add("$($eventos.Count) evento(s) de error de disco en $Dias dia(s)")
}

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "== Resultado =="
    if ($problemas.Count -eq 0) {
        Write-Output "  Sin problemas de disco detectados."
        exit 0
    }
    Write-Output "  $($problemas.Count) observacion(es):"
    foreach ($problema in $problemas) { Write-Output "   - $problema" }
    exit 1
}

if (-not $Unidad) {
    Write-Output ""
    Write-Output "El modo '$Modo' exige el parametro -Unidad, por ejemplo -Unidad C:"
    exit 1
}

$letra = $Unidad.TrimEnd(":", "\")
if ($letra.Length -ne 1) {
    Write-Output ""
    Write-Output "La unidad debe ser una sola letra, por ejemplo 'C:' o 'C'."
    exit 1
}

if (-not (Test-Path "${letra}:\")) {
    Write-Output ""
    Write-Output "La unidad ${letra}: no existe o no esta accesible."
    exit 1
}

$esSistema = ($env:SystemDrive -replace ":", "") -ieq $letra

Write-Output ""
if ($Modo -eq "verificar") {
    Write-Output "== chkdsk en modo solo lectura sobre ${letra}: =="
    Write-Output "  No repara nada y no bloquea el volumen. Puede tardar."
    $salida = & chkdsk "${letra}:"
}
else {
    Write-Output "== chkdsk /F sobre ${letra}: =="
    if ($esSistema) {
        Write-Output "  Es la unidad del sistema: no se puede bloquear en caliente, asi"
        Write-Output "  que la reparacion se AGENDA para el proximo reinicio."
    }
    # El "S" responde a la pregunta de agendar para el proximo arranque. En una
    # unidad que no es la del sistema, chkdsk la bloquea y repara en el momento.
    $salida = "S" | & chkdsk "${letra}:" /F
}

$codigo = $LASTEXITCODE

Write-Output ""
foreach ($linea in $salida) {
    if ($linea -and $linea.Trim()) { Write-Output "  $linea" }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  chkdsk devolvio codigo $codigo."

# Codigos documentados de chkdsk: 0 sin problemas, 1 encontro y corrigio,
# 2 hizo limpieza o hace falta correr con /F, 3 no pudo verificar.
switch ($codigo) {
    0 { Write-Output "  Sin errores en el sistema de archivos." }
    1 { Write-Output "  Encontro errores y los corrigio." }
    2 { Write-Output "  Hay trabajo pendiente: hace falta correr con -Modo reparar." }
    3 { Write-Output "  No pudo verificar el volumen." }
    default { Write-Output "  Codigo no documentado." }
}

if ($Modo -eq "reparar" -and $esSistema) {
    Write-Output ""
    Write-Output "  PENDIENTE: la reparacion corre en el proximo arranque y puede dejar"
    Write-Output "  el equipo inutilizable un buen rato. Coordina una ventana antes de"
    Write-Output "  reiniciar; este script no reinicia por su cuenta."
}

if ($codigo -gt 1) { exit 1 }
exit 0
