<#
.SYNOPSIS
    Censa -y opcionalmente borra- el directorio legacy que deja la migracion del
    agente 386 de 32 bits.

.DESCRIPTION
    Por defecto SOLO LEE. Sin -Aplicar no borra nada.

    El agente 386 roto vivia en "C:\Program Files (x86)\ObserverAgent" y ahi
    descargaba su Python y su Mesh Agent. Desde v2.15.3 el agente resuelve su
    directorio por el ejecutable en curso y pasa a "C:\Program Files\ObserverAgent",
    pero NO migra ni borra el anterior: quedan unos 81 MB en disco que el
    desinstalador no toca y que no tienen entrada en Agregar o quitar programas.

    Este script responde dos preguntas distintas segun como se lo corra:

      sin -Aplicar  -> CENSO. Cuantas maquinas de la flota arrastran el
                       directorio legacy, y cuales pueden limpiarse sin riesgo.
                       Codigo de salida 1 = esta maquina tiene residuo.

      con -Aplicar  -> LIMPIEZA de UNA maquina, y solo si las cinco guardas
                       pasan. Nunca reescribe tareas programadas.

    LAS CINCO GUARDAS, y por que existe cada una:

      1. El directorio vivo se lee del registro (ImagePath del servicio), no de
         la salida de sc.exe: las etiquetas de sc.exe estan traducidas y la flota
         mezcla Windows en espanol y en ingles.
      2. Las rutas se comparan en forma larga y canonica. "C:\PROGRA~1\ObserverAgent"
         y "C:\Program Files\ObserverAgent" son el mismo directorio escrito de dos
         formas, y confundirlas significa borrar el directorio VIVO.
      3. El candidato tiene que parecer una instalacion del agente. No se borra un
         directorio cualquiera que coincida de nombre.
      4. Ningun proceso puede estar corriendo desde el candidato.
      5. Ninguna tarea programada puede apuntar al candidato. Las tareas tipo rmm
         se crean con ruta RELATIVA y WorkingDirectory fijado al ProgramDir del
         momento (agent/tasks_windows.go), y NO se reescriben solas en el update:
         borrar el directorio las mata a todas con 0x80070002, en silencio.

    Si la guarda 5 falla, el script se DETIENE y no borra. La forma correcta de
    destrabarlo es volver a empujar las tareas desde la consola -eso las recrea
    contra el directorio nuevo por el camino del propio producto- y recien
    entonces volver a correr este script. Este script no toca tareas a proposito.

.PARAMETER Aplicar
    Borra el directorio legacy si las cinco guardas pasan. Sin este parametro el
    script solo informa.

.EXAMPLE
    agente-386-ruta-legacy.ps1
    Censo. No modifica nada.

.EXAMPLE
    agente-386-ruta-legacy.ps1 -Aplicar
    Limpia esta maquina si es seguro hacerlo.

.NOTES
    Compatible con PowerShell 2.0 (Windows 7), porque la poblacion 386 incluye
    Win7. Por eso no se usan Get-ScheduledTask, [pscustomobject] ni -File.

    Codigos de salida:
      0 - sin residuo, o residuo borrado con exito
      1 - hay residuo (censo), o quedo sin borrar por decision del operador
      2 - hay residuo pero una guarda lo bloquea; requiere accion previa
#>

[CmdletBinding()]
param(
    [switch] $Aplicar
)

# El agente pasa el stdout por strings.ToValidUTF8(s, "") (agent/utils.go:401), que
# BORRA toda secuencia UTF-8 invalida. Windows PowerShell escribe en la pagina de
# codigos OEM, donde un acento es un byte que no es UTF-8 valido.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
}
catch {
    Write-Verbose $_.Exception.Message
}

$ErrorActionPreference = "Continue"

$SVC = "observeragent"
$DIRNAME = "ObserverAgent"

# ---------------------------------------------------------------------------
# Guarda 2 - forma larga de una ruta. Sin esto, C:\PROGRA~1\ObserverAgent y
# C:\Program Files\ObserverAgent se ven distintas y el script borraria el
# directorio vivo creyendo que es el legacy.
# ---------------------------------------------------------------------------
$sigLongPath = @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ObsPath {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern uint GetLongPathNameW(string lpszShortPath, StringBuilder lpszLongPath, uint cchBuffer);
    public static string Long(string p) {
        StringBuilder sb = new StringBuilder(4096);
        uint n = GetLongPathNameW(p, sb, 4096);
        if (n == 0 || n > 4096) { return p; }
        return sb.ToString();
    }
}
"@
try {
    Add-Type -TypeDefinition $sigLongPath -ErrorAction Stop
    $canUseLong = $true
}
catch {
    $canUseLong = $false
}

function Get-RutaCanonica([string] $p) {
    if ([string]::IsNullOrEmpty($p)) { return "" }
    $r = $p.Trim().Trim('"')
    try { $r = [IO.Path]::GetFullPath($r) } catch { }
    if ($canUseLong) {
        try { $r = [ObsPath]::Long($r) } catch { }
    }
    return $r.TrimEnd('\')
}

function Test-MismaRuta([string] $a, [string] $b) {
    $ca = Get-RutaCanonica $a
    $cb = Get-RutaCanonica $b
    if ($ca -eq "" -or $cb -eq "") { return $false }
    return ([string]::Compare($ca, $cb, $true) -eq 0)
}

function Test-BajoRuta([string] $hijo, [string] $padre) {
    $ch = Get-RutaCanonica $hijo
    $cp = Get-RutaCanonica $padre
    if ($ch -eq "" -or $cp -eq "") { return $false }
    if ([string]::Compare($ch, $cp, $true) -eq 0) { return $true }
    return $ch.ToLower().StartsWith(($cp.ToLower() + "\"))
}

function Format-Tamano([long] $b) {
    # Un residuo de 5 KB no debe imprimirse como "0 MB": el censo se lee de un
    # vistazo y un cero ahi se confunde con "no hay nada".
    if ($b -ge 1MB) { return ("{0} MB" -f [math]::Round($b / 1MB, 1)) }
    if ($b -ge 1KB) { return ("{0} KB" -f [math]::Round($b / 1KB, 1)) }
    return ("$b bytes")
}

# ---------------------------------------------------------------------------
# Guarda 1 - el directorio VIVO sale del registro, no de sc.exe.
# ---------------------------------------------------------------------------
function Get-DirectorioVivo() {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$SVC"
    if (-not (Test-Path $key)) { return "" }
    $img = $null
    try { $img = (Get-ItemProperty -Path $key -Name ImagePath -ErrorAction Stop).ImagePath } catch { return "" }
    if ([string]::IsNullOrEmpty($img)) { return "" }

    # ImagePath viene como:  "C:\...\observeragent.exe" -m svc   (con o sin comillas)
    $exe = ""
    if ($img.StartsWith('"')) {
        $fin = $img.IndexOf('"', 1)
        if ($fin -gt 1) { $exe = $img.Substring(1, $fin - 1) }
    }
    else {
        $idx = $img.ToLower().IndexOf(".exe")
        if ($idx -gt 0) { $exe = $img.Substring(0, $idx + 4) }
    }
    if ([string]::IsNullOrEmpty($exe)) { return "" }
    return (Get-RutaCanonica ([IO.Path]::GetDirectoryName($exe)))
}

# ---------------------------------------------------------------------------
# Guarda 5 - tareas programadas que apuntan al candidato. Solo LEE (COM
# Schedule.Service, disponible desde Windows 7; Get-ScheduledTask no lo esta).
# ---------------------------------------------------------------------------
function Get-TareasQueApuntan([string] $dir) {
    $hits = @()
    $svc = $null
    try {
        $svc = New-Object -ComObject "Schedule.Service"
        $svc.Connect()
    }
    catch {
        return $null   # null = no se pudo determinar; el llamador lo trata como bloqueo
    }

    $pendientes = New-Object System.Collections.ArrayList
    [void]$pendientes.Add($svc.GetFolder("\"))
    while ($pendientes.Count -gt 0) {
        $f = $pendientes[0]
        $pendientes.RemoveAt(0)
        try {
            foreach ($sub in $f.GetFolders(0)) { [void]$pendientes.Add($sub) }
        }
        catch { }
        try {
            foreach ($t in $f.GetTasks(1)) {
                $def = $null
                try { $def = $t.Definition } catch { continue }
                foreach ($a in $def.Actions) {
                    $p = ""
                    $w = ""
                    try { $p = [string]$a.Path } catch { }
                    try { $w = [string]$a.WorkingDirectory } catch { }
                    $apunta = $false
                    if ($w -ne "" -and (Test-BajoRuta $w $dir)) { $apunta = $true }
                    if ($p -ne "" -and $p.Contains("\") -and (Test-BajoRuta $p $dir)) { $apunta = $true }
                    if ($apunta) {
                        $o = New-Object PSObject
                        $o | Add-Member NoteProperty Tarea $t.Path
                        $o | Add-Member NoteProperty Ejecuta $p
                        $o | Add-Member NoteProperty Workdir $w
                        $hits += $o
                        break
                    }
                }
            }
        }
        catch { }
    }
    # La coma es obligatoria: una funcion de PowerShell que devuelve @() entrega
    # $null, y sin esto la guarda 5 bloquearia SIEMPRE en el caso normal (cero
    # tareas apuntando al legacy), que es justo el caso que debe dejar pasar.
    return , $hits
}

# ===========================================================================
"=== AGENTE 386 - RUTA LEGACY ==============================================="
"  modo: $(if ($Aplicar) { 'APLICAR (borra si es seguro)' } else { 'CENSO (solo lectura)' })"
"  equipo: $env:COMPUTERNAME"

$vivo = Get-DirectorioVivo
if ($vivo -eq "") {
    "  !! No se pudo leer el ImagePath del servicio '$SVC'."
    "  !! Sin el directorio vivo no hay con que comparar. No se toca nada."
    exit 2
}
"  directorio VIVO (del registro): $vivo"

# Candidatos: el mismo nombre bajo las dos vistas de Program Files.
$candidatos = @()
foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
    if ([string]::IsNullOrEmpty($base)) { continue }
    $c = Get-RutaCanonica (Join-Path $base $DIRNAME)
    if ($c -eq "") { continue }
    if (Test-MismaRuta $c $vivo) { continue }     # guarda 2
    if ($candidatos -notcontains $c) { $candidatos += $c }
}

$legacy = ""
foreach ($c in $candidatos) {
    if (Test-Path -LiteralPath $c) { $legacy = $c; break }
}

if ($legacy -eq "") {
    "  directorio legacy: NO HAY"
    ""
    "  RESULTADO: sin residuo. Nada que hacer."
    exit 0
}

"  directorio LEGACY encontrado: $legacy"

# Tamano y conteo. -Recurse -Force sin -File, que es PS3+.
$archivos = @(Get-ChildItem -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { -not $_.PSIsContainer })
$bytes = 0
foreach ($f in $archivos) { $bytes += $f.Length }
"  contenido: $($archivos.Count) archivos, $bytes bytes ($(Format-Tamano $bytes))"
"  raiz:"
foreach ($e in (Get-ChildItem -LiteralPath $legacy -Force -ErrorAction SilentlyContinue)) {
    if ($e.PSIsContainer) { "    $($e.Name)  <dir>" } else { "    $($e.Name)  $($e.Length)b" }
}

""
"=== GUARDAS ================================================================"

# Guarda 3 - que parezca una instalacion del agente.
$g3 = $false
foreach ($marca in @("observeragent.exe", "meshagent.exe", "python", "bin")) {
    if (Test-Path -LiteralPath (Join-Path $legacy $marca)) { $g3 = $true; break }
}
"  3. parece instalacion del agente : $g3"

# Guarda 4 - ningun proceso corriendo desde ahi.
$procs = @()
foreach ($p in (Get-Process -ErrorAction SilentlyContinue)) {
    $ruta = ""
    try { $ruta = $p.Path } catch { $ruta = "" }
    if ($ruta -ne "" -and (Test-BajoRuta $ruta $legacy)) { $procs += $p }
}
$g4 = ($procs.Count -eq 0)
"  4. sin procesos vivos desde ahi  : $g4"
foreach ($p in $procs) { "       !! $($p.ProcessName)  $($p.Path)" }

# Guarda 5 - ninguna tarea programada apuntando ahi.
$tareas = Get-TareasQueApuntan $legacy
# $null a la izquierda a proposito: con el array a la izquierda, -eq compara
# elemento a elemento y no responde lo que se le esta preguntando.
if ($null -eq $tareas) {
    $g5 = $false
    "  5. sin tareas apuntando ahi      : INDETERMINADO (no se pudo consultar el planificador)"
}
else {
    $g5 = ($tareas.Count -eq 0)
    "  5. sin tareas apuntando ahi      : $g5"
    foreach ($t in $tareas) { "       !! $($t.Tarea)  ejecuta='$($t.Ejecuta)'  workdir='$($t.Workdir)'" }
}

$seguro = ($g3 -and $g4 -and $g5)
""
if (-not $Aplicar) {
    "=== RESULTADO DEL CENSO ===================================================="
    "  residuo: SI  ($(Format-Tamano $bytes) en $legacy)"
    "  se puede limpiar sin riesgo: $seguro"
    if (-not $seguro -and -not $g5 -and $null -ne $tareas -and $tareas.Count -gt 0) {
        "  para destrabarlo: volver a empujar las tareas programadas desde la consola"
        "  (eso las recrea contra el directorio nuevo) y recien entonces aplicar."
    }
    "  para limpiar esta maquina: correr de nuevo con -Aplicar"
    exit 1
}

"=== APLICAR ================================================================"
if (-not $seguro) {
    "  !! Alguna guarda no paso. NO SE BORRA NADA."
    if (-not $g3) { "  !! El directorio no parece una instalacion del agente." }
    if (-not $g4) { "  !! Hay procesos vivos desde ahi: detenerlos primero." }
    if (-not $g5) {
        "  !! Hay tareas programadas apuntando ahi, o no se pudo consultar el planificador."
        "  !! Borrar ahora las mataria con 0x80070002, en silencio."
        "  !! Volver a empujar las tareas desde la consola y reintentar."
    }
    exit 2
}

"  las cinco guardas pasaron; borrando $legacy"
Remove-Item -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue

# El exit 0 del Remove-Item no prueba el efecto: se verifica el estado observable.
if (Test-Path -LiteralPath $legacy) {
    $quedan = @(Get-ChildItem -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { -not $_.PSIsContainer })
    "  !! NO se borro del todo: quedan $($quedan.Count) archivos en $legacy"
    exit 2
}

"  borrado verificado: $legacy ya no existe"
""
"=== CONTROL POSTERIOR - el agente sigue sano ==============================="
$s = Get-Service -Name $SVC -ErrorAction SilentlyContinue
"  servicio $SVC : $(if ($s) { $s.Status } else { 'NO EXISTE' })"
"  directorio vivo intacto : $(Test-Path -LiteralPath $vivo)"
""
"  RESULTADO: limpiado. $(Format-Tamano $bytes) recuperados."
exit 0
