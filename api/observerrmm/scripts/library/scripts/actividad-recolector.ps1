<#
.SYNOPSIS
    Resume por usuario y por dia lo que registro el muestreador de Observer Actividad
    y lo imprime como JSON para los reportes.

.DESCRIPTION
    Feature 048. Se usa como TAREA PROGRAMADA (por politica), con el nombre exacto
    "Observer Actividad - Recolector": cada corrida de una tarea queda en el historial
    del agente con su stdout completo, y de ahi lo leen las plantillas de reporte
    "Actividad de usuarios - diario" y "Actividad - resumen semanal". Recomendado:
    diaria a las 23:55 y "ejecutar lo antes posible si se perdio" (StartWhenAvailable),
    para que los notebooks apagados a esa hora entreguen al encender.

    Emite todos los dias CERRADOS (anteriores a hoy) que aun no informo, hasta
    -MaxDias, y guarda la marca en %ProgramData%\ObserverActividad\recolector.json.
    Asi no se duplican ni se pierden dias aunque el equipo haya estado apagado.

    Salida (una sola linea JSON):
      {"v":1,"so":"windows","dias":[{"fecha":"AAAA-MM-DD","tz":"-03:00","usuarios":[
        {"usuario":..,"primero":"HH:mm","ultimo":"HH:mm","activo_min":..,"inactivo_min":..,
         "huecos_min":..,"capturas":..,"horas":{"08":{"a":..,"i":..,"p":{"proc":min}}},
         "procs":{"proc":min},"titulos_top":[["titulo",min]]}]}]}

    huecos_min = minutos en que el muestreador estuvo detenido sin que hubiera reinicio
    ni nuevo inicio de sesion: la firma de alguien que lo mato. Una suspension (tapa
    cerrada) no cuenta: el proceso sigue vivo y al despertar no hay evento de inicio.

.PARAMETER Hoy
    Incluye tambien el dia en curso, marcado "parcial": true, sin mover la marca.
    Util para probar o para un reporte a media jornada.

.PARAMETER MaxDias
    Maximo de dias cerrados a emitir en una corrida (1-14). Por defecto 7.

.PARAMETER Reiniciar
    Ignora la marca y vuelve a emitir los ultimos -MaxDias dias cerrados. El reporte
    se queda con la corrida mas reciente de cada dia, asi que no duplica.

.EXAMPLE
    actividad-recolector.ps1
    actividad-recolector.ps1 -Hoy
    actividad-recolector.ps1 -Reiniciar -MaxDias 14
#>

[CmdletBinding()]
param(
    [switch]$Hoy,
    [ValidateRange(1, 14)]
    [int]$MaxDias = 7,
    [switch]$Reiniciar
)

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
}
catch {
    Write-Verbose $_.Exception.Message
}

$ErrorActionPreference = "Continue"

$base = Join-Path $env:ProgramData "ObserverActividad"
$marcaPath = Join-Path $base "recolector.json"
$utf8 = New-Object System.Text.UTF8Encoding $false
$cultura = [Globalization.CultureInfo]::InvariantCulture
$topHora = 5
$topProcs = 25
$topTitulos = 10

function ConvertTo-Epoch([datetime]$fecha) {
    return [int64]([DateTimeOffset]$fecha).ToUnixTimeSeconds()
}

function Get-RaicesDatos {
    $perfiles = @()
    try {
        $perfiles = Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and $_.LocalPath }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
    foreach ($perfil in $perfiles) {
        $raiz = Join-Path $perfil.LocalPath "AppData\Local\ObserverActividad"
        if (Test-Path -LiteralPath $raiz) { $raiz }
    }
}

function Add-Minutos($tabla, $clave, $minutos) {
    if ($tabla.ContainsKey($clave)) { $tabla[$clave] += $minutos } else { $tabla[$clave] = $minutos }
}

function Get-Top($tabla, $n) {
    $salida = [ordered]@{}
    $tabla.GetEnumerator() | Sort-Object -Property @{ Expression = { $_.Value }; Descending = $true }, Name |
        Select-Object -First $n | ForEach-Object { $salida[$_.Name] = [int][Math]::Round($_.Value) }
    return $salida
}

function Get-ResumenArchivo($archivo, $dirCapturas) {
    # Devuelve un resumen por usuario (normalmente uno por perfil).
    $porUsuario = @{}
    $previo = @{}
    foreach ($linea in [IO.File]::ReadAllLines($archivo, $utf8)) {
        $c = $linea.Split("`t")
        if ($c.Count -lt 5) { continue }
        $ts = [datetime]::MinValue
        if (-not [datetime]::TryParseExact($c[0], "s", $cultura, "None", [ref]$ts)) { continue }
        $u = $c[1]
        if (-not $porUsuario.ContainsKey($u)) {
            $porUsuario[$u] = @{
                primero = $ts; ultimo = $ts; activo = 0.0; inactivo = 0.0; huecos = 0.0
                horas = @{}; procs = @{}; titulos = @{}
            }
        }
        $r = $porUsuario[$u]
        if ($c[2] -eq "#inicio") {
            if ($previo.ContainsKey($u)) {
                $ant = $previo[$u]
                $hueco = ($ts - $ant.ts).TotalSeconds - $ant.i
                if ($hueco -gt 2 * $ant.i) {
                    $boot = 0; $sesion = 0
                    foreach ($par in ([string]$c[5]).Split(";")) {
                        $kv = $par.Split("=")
                        if ($kv.Count -eq 2 -and $kv[0] -eq "boot") { [void][int64]::TryParse($kv[1], [ref]$boot) }
                        if ($kv.Count -eq 2 -and $kv[0] -eq "sesion") { [void][int64]::TryParse($kv[1], [ref]$sesion) }
                    }
                    $antEpoch = ConvertTo-Epoch $ant.ts
                    if ($boot -le $antEpoch -and $sesion -le $antEpoch) {
                        $r.huecos += [Math]::Min($hueco / 60, 240)
                    }
                }
            }
            continue
        }
        $i = 0
        if (-not [int]::TryParse($c[4], [ref]$i) -or $i -le 0) { continue }
        $min = $i / 60.0
        $hh = $ts.ToString("HH", $cultura)
        if (-not $r.horas.ContainsKey($hh)) { $r.horas[$hh] = @{ a = 0.0; i = 0.0; p = @{} } }
        if ($c[3] -eq "1") {
            $r.activo += $min
            $r.horas[$hh].a += $min
            Add-Minutos $r.horas[$hh].p $c[2] $min
            Add-Minutos $r.procs $c[2] $min
            if ($c.Count -ge 6 -and $c[5]) { Add-Minutos $r.titulos $c[5] $min }
        }
        else {
            $r.inactivo += $min
            $r.horas[$hh].i += $min
        }
        if ($ts -lt $r.primero) { $r.primero = $ts }
        if ($ts -gt $r.ultimo) { $r.ultimo = $ts }
        $previo[$u] = @{ ts = $ts; i = $i }
    }

    $capturas = 0
    if (Test-Path -LiteralPath $dirCapturas) {
        $capturas = @(Get-ChildItem -LiteralPath $dirCapturas -File -Filter "*.jpg" -ErrorAction SilentlyContinue).Count
    }

    foreach ($u in $porUsuario.Keys) {
        $r = $porUsuario[$u]
        if ($r.activo + $r.inactivo -le 0) { continue }
        $horas = [ordered]@{}
        foreach ($hh in ($r.horas.Keys | Sort-Object)) {
            $celda = $r.horas[$hh]
            $horas[$hh] = [ordered]@{
                a = [int][Math]::Round($celda.a)
                i = [int][Math]::Round($celda.i)
                p = (Get-Top $celda.p $topHora)
            }
        }
        $titulos = @()
        $r.titulos.GetEnumerator() | Sort-Object -Property @{ Expression = { $_.Value }; Descending = $true } |
            Select-Object -First $topTitulos | ForEach-Object {
                $t = [string]$_.Name
                if ($t.Length -gt 80) { $t = $t.Substring(0, 80) }
                $titulos += , @($t, [int][Math]::Round($_.Value))
            }
        [ordered]@{
            usuario      = $u
            primero      = $r.primero.ToString("HH:mm", $cultura)
            ultimo       = $r.ultimo.ToString("HH:mm", $cultura)
            activo_min   = [int][Math]::Round($r.activo)
            inactivo_min = [int][Math]::Round($r.inactivo)
            huecos_min   = [int][Math]::Round($r.huecos)
            capturas     = $capturas
            horas        = $horas
            procs        = (Get-Top $r.procs $topProcs)
            titulos_top  = $titulos
        }
    }
}

# --- Que dias emitir -------------------------------------------------------
$hoyFecha = (Get-Date).Date
$ultimo = [datetime]::MinValue
if (-not $Reiniciar -and (Test-Path -LiteralPath $marcaPath)) {
    try {
        $marca = [IO.File]::ReadAllText($marcaPath, $utf8) | ConvertFrom-Json
        [void][datetime]::TryParseExact([string]$marca.ultimo, "yyyy-MM-dd", $cultura, "None", [ref]$ultimo)
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}
$dias = @()
for ($k = $MaxDias; $k -ge 1; $k--) {
    $d = $hoyFecha.AddDays(-$k)
    if ($d -gt $ultimo) { $dias += $d }
}
if ($Hoy) { $dias += $hoyFecha }

$raices = @(Get-RaicesDatos)
$offset = [TimeZoneInfo]::Local.GetUtcOffset((Get-Date))
$signo = "+"; if ($offset -lt [TimeSpan]::Zero) { $signo = "-" }
$tz = "{0}{1:hh\:mm}" -f $signo, $offset

$salidaDias = @()
foreach ($d in $dias) {
    $fecha = $d.ToString("yyyy-MM-dd", $cultura)
    $usuarios = @()
    foreach ($raiz in $raices) {
        $archivo = Join-Path $raiz ("datos\" + $fecha + ".tsv")
        if (-not (Test-Path -LiteralPath $archivo)) { continue }
        try {
            $usuarios += @(Get-ResumenArchivo $archivo (Join-Path $raiz ("capturas\" + $fecha)))
        }
        catch {
            Write-Verbose ("No se pudo leer " + $archivo + ": " + $_.Exception.Message)
        }
    }
    if ($usuarios.Count -eq 0) { continue }
    $dia = [ordered]@{ fecha = $fecha; tz = $tz; usuarios = $usuarios }
    if ($d -eq $hoyFecha) { $dia["parcial"] = $true }
    $salidaDias += $dia
}

$documento = [ordered]@{
    v       = 1
    so      = "windows"
    equipo  = $env:COMPUTERNAME
    dias    = $salidaDias
}
$json = $documento | ConvertTo-Json -Depth 10 -Compress

# El stdout de una tarea va entero a la base: si se pasa de ~60 KB se recortan los
# titulos y el detalle por hora antes que perder dias.
if ($json.Length -gt 60000) {
    foreach ($dia in $salidaDias) {
        foreach ($u in $dia.usuarios) {
            $u.titulos_top = @()
            foreach ($hh in @($u.horas.Keys)) { $u.horas[$hh].p = [ordered]@{} }
        }
    }
    $json = $documento | ConvertTo-Json -Depth 10 -Compress
}
Write-Output $json

# La marca avanza solo hasta ayer y solo si se emitieron (o revisaron) dias cerrados.
$cerrados = @($dias | Where-Object { $_ -lt $hoyFecha })
if ($cerrados.Count -gt 0 -and (Test-Path -LiteralPath $base)) {
    $nueva = [ordered]@{ ultimo = $hoyFecha.AddDays(-1).ToString("yyyy-MM-dd", $cultura); corrida = (Get-Date).ToString("s") }
    try {
        [IO.File]::WriteAllText($marcaPath, ($nueva | ConvertTo-Json -Compress), $utf8)
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}
