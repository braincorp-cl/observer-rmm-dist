<#
.SYNOPSIS
    Instala, actualiza, consulta o desinstala el muestreador de Observer Actividad.

.DESCRIPTION
    Feature 048. Observer Actividad mide el uso del equipo por usuario: que proceso
    esta en primer plano, si el usuario esta activo o inactivo, opcionalmente el
    titulo de la ventana y capturas de pantalla periodicas. Es la Fase 1 (scripts):
    el agente no cambia.

    Piezas que deja este script en %ProgramData%\ObserverActividad (solo
    administradores y SYSTEM escriben; los usuarios leen y ejecutan):
      - muestreo.ps1   el muestreador. Corre DENTRO de la sesion del usuario, porque
                       un servicio en la sesion 0 no ve el escritorio.
      - lanzador.vbs   lo arranca sin ventana (powershell -WindowStyle Hidden igual
                       parpadea una consola).
      - config.json    intervalo, flags de titulos y capturas, retencion, aviso.
    Y una tarea programada "ObserverActividad" para el grupo Usuarios (resuelto por
    SID S-1-5-32-545, asi funciona en equipos en espanol y en ingles) con dos
    disparadores: al iniciar sesion y cada 15 minutos. El segundo es el watchdog: si
    alguien mata el muestreador, vuelve en 15 minutos; un mutex por sesion evita
    instancias duplicadas.

    Los datos quedan en el perfil de cada usuario:
      %LOCALAPPDATA%\ObserverActividad\datos\AAAA-MM-DD.tsv
      %LOCALAPPDATA%\ObserverActividad\capturas\AAAA-MM-DD\HHmmss.jpg
    Las capturas NO se suben: se recuperan bajo demanda con la recuperacion de
    archivos (feature 042), que queda en auditoria. El resumen diario lo sube el
    script "Observer Actividad - Recolector" como tarea programada.

    Cumplimiento: la primera vez que el muestreador corre en un perfil muestra un
    aviso que el usuario debe aceptar (texto configurable con -Aviso). La validacion
    legal del uso (consentimiento, reglamento interno) es del cliente.

.PARAMETER Modo
    estado (por defecto), instalar, desinstalar. Instalar sobre una instalacion
    existente actualiza el muestreador y la configuracion.

.PARAMETER Intervalo
    Segundos entre muestras (15-600). Por defecto 60.

.PARAMETER InactivoSeg
    Segundos sin teclado ni mouse a partir de los cuales la muestra cuenta como
    inactiva. Por defecto 120.

.PARAMETER Titulos
    on|off. Registrar el titulo de la ventana activa. Por defecto on.

.PARAMETER Capturas
    on|off. Tomar capturas de pantalla mientras el usuario esta activo. Por defecto on.

.PARAMETER CadaCaptura
    Minutos entre capturas (1-240). Por defecto 10.

.PARAMETER RetencionCapturas
    Dias que se conservan las capturas en el equipo. Por defecto 7.

.PARAMETER RetencionDatos
    Dias que se conservan los TSV en el equipo. Por defecto 35.

.PARAMETER Aviso
    Texto del aviso que ve el usuario la primera vez. Vacio = texto por defecto.

.PARAMETER SinAviso
    No mostrar aviso (solo si el cliente ya lo resolvio por otra via, p. ej. firma
    del anexo al reglamento interno).

.PARAMETER BorrarDatos
    Con -Modo desinstalar: borra tambien los datos y capturas de todos los perfiles.

.EXAMPLE
    actividad-instalar.ps1 -Modo instalar
    actividad-instalar.ps1 -Modo instalar -Capturas off -Titulos off
    actividad-instalar.ps1 -Modo desinstalar -BorrarDatos
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "instalar", "desinstalar")]
    [string]$Modo = "estado",
    [ValidateRange(15, 600)]
    [int]$Intervalo = 60,
    [ValidateRange(30, 3600)]
    [int]$InactivoSeg = 120,
    [ValidateSet("on", "off")]
    [string]$Titulos = "on",
    [ValidateSet("on", "off")]
    [string]$Capturas = "on",
    [ValidateRange(1, 240)]
    [int]$CadaCaptura = 10,
    [ValidateRange(1, 90)]
    [int]$RetencionCapturas = 7,
    [ValidateRange(2, 400)]
    [int]$RetencionDatos = 35,
    [string]$Aviso = "",
    [switch]$SinAviso,
    [switch]$BorrarDatos
)

# Ver energia-hibernacion.ps1: sin esto los acentos de la salida se pierden.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
}
catch {
    Write-Verbose $_.Exception.Message
}

$ErrorActionPreference = "Stop"

$base = Join-Path $env:ProgramData "ObserverActividad"
$nombreTarea = "ObserverActividad"
$utf8 = New-Object System.Text.UTF8Encoding $false

# Texto por defecto del aviso. El archivo debe ser ASCII (ver
# scripts/verificar_biblioteca_scripts.py), asi que los acentos van por codigo.
$a = [char]0x00E1; $e = [char]0x00E9; $i = [char]0x00ED; $o = [char]0x00F3
$avisoDefecto = "Este equipo es de propiedad de su empleador y registra su uso: " +
"qu$e aplicaci$o" + "n est$a en primer plano, el tiempo activo e inactivo" +
"{0}{1}. La informaci$o" + "n se usa para medir la productividad seg$([char]0x00FA)n " +
"la pol$i" + "tica de uso aceptable de su organizaci$o" + "n. Si tiene dudas, " +
"consulte con su jefatura o con el $a" + "rea de TI."

$muestreo = @'
# Observer Actividad - muestreador (feature 048). Lo instala actividad-instalar.ps1.
# Corre en la sesion del usuario. Una linea TSV por muestra:
#   ts <TAB> usuario <TAB> proceso <TAB> activo(0/1) <TAB> intervalo(s) <TAB> titulo
# Un evento de arranque usa proceso "#inicio" y en el titulo "boot=<epoch>;sesion=<epoch>":
# el recolector lo usa para distinguir un reinicio o un inicio de sesion (legitimo) de
# un muestreador que alguien mato a mitad de la sesion (hueco).
$ErrorActionPreference = 'SilentlyContinue'
$creado = $false
$mutex = New-Object System.Threading.Mutex($true, 'Local\ObserverActividadMuestreo', [ref]$creado)
if (-not $creado) { exit 0 }

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class OAct {
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO p);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    public static uint IdleSeconds() {
        LASTINPUTINFO l = new LASTINPUTINFO();
        l.cbSize = (uint)Marshal.SizeOf(l);
        if (!GetLastInputInfo(ref l)) { return 0; }
        return unchecked((uint)Environment.TickCount - l.dwTime) / 1000;
    }
    public static string Title(IntPtr h) {
        StringBuilder sb = new StringBuilder(512);
        GetWindowText(h, sb, 512);
        return sb.ToString();
    }
}
"@
[void][OAct]::SetProcessDPIAware()
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$base = Join-Path $env:ProgramData 'ObserverActividad'
$cfgPath = Join-Path $base 'config.json'
$utf8 = New-Object System.Text.UTF8Encoding $false

function Read-Config {
    $c = $null
    try { $c = [IO.File]::ReadAllText($cfgPath, $utf8) | ConvertFrom-Json } catch { $c = $null }
    if (-not $c) { $c = [pscustomobject]@{ intervalo = 60; inactivo_seg = 120; titulos = $false; capturas = $false } }
    return $c
}

function ConvertTo-Epoch([datetime]$fecha) {
    return [int64]([DateTimeOffset]$fecha).ToUnixTimeSeconds()
}

function Remove-Antiguos($dirCap, $dirDatos, $cfg) {
    $hoy = (Get-Date).Date
    if ($cfg.retencion_capturas_dias) {
        Get-ChildItem -LiteralPath $dirCap -Directory | ForEach-Object {
            $d = [datetime]::MinValue
            if ([datetime]::TryParseExact($_.Name, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture, 'None', [ref]$d)) {
                if (($hoy - $d).TotalDays -ge [int]$cfg.retencion_capturas_dias) { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
            }
        }
    }
    if ($cfg.retencion_datos_dias) {
        Get-ChildItem -LiteralPath $dirDatos -Filter '*.tsv' -File | ForEach-Object {
            $d = [datetime]::MinValue
            if ([datetime]::TryParseExact($_.BaseName, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture, 'None', [ref]$d)) {
                if (($hoy - $d).TotalDays -ge [int]$cfg.retencion_datos_dias) { Remove-Item -LiteralPath $_.FullName -Force }
            }
        }
    }
}

function Save-Captura($dirCap, $cfg) {
    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
    if ($vs.Width -le 0 -or $vs.Height -le 0) { return }
    $dia = Join-Path $dirCap (Get-Date -Format 'yyyy-MM-dd')
    [void](New-Item -ItemType Directory -Force -Path $dia)
    $archivo = Join-Path $dia ((Get-Date -Format 'HHmmss') + '.jpg')
    $ancho = 1280; if ($cfg.ancho_captura) { $ancho = [int]$cfg.ancho_captura }
    $ancho = [Math]::Min($ancho, $vs.Width)
    $alto = [int]($vs.Height * $ancho / $vs.Width)
    $calidad = 40; if ($cfg.calidad_captura) { $calidad = [int]$cfg.calidad_captura }
    $bmp = $null; $chica = $null; $g = $null
    try {
        $bmp = New-Object System.Drawing.Bitmap $vs.Width, $vs.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($vs.Left, $vs.Top, 0, 0, $bmp.Size)
        $chica = New-Object System.Drawing.Bitmap $bmp, $ancho, $alto
        $enc = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
        $ep = New-Object System.Drawing.Imaging.EncoderParameters 1
        $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), ([long]$calidad)
        $chica.Save($archivo, $enc, $ep)
    }
    catch {
        # Escritorio seguro (UAC, pantalla de bloqueo): no hay nada que capturar.
        Write-Verbose $_.Exception.Message
    }
    finally {
        if ($g) { $g.Dispose() }
        if ($chica) { $chica.Dispose() }
        if ($bmp) { $bmp.Dispose() }
    }
}

$raiz = Join-Path $env:LOCALAPPDATA 'ObserverActividad'
$dirDatos = Join-Path $raiz 'datos'
$dirCap = Join-Path $raiz 'capturas'
[void](New-Item -ItemType Directory -Force -Path $dirDatos)
[void](New-Item -ItemType Directory -Force -Path $dirCap)
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$cfg = Read-Config

# Aviso al usuario: una vez por perfil, hasta que lo acepte.
$marcaAviso = Join-Path $raiz 'aviso-aceptado.txt'
if ($cfg.aviso -and -not (Test-Path -LiteralPath $marcaAviso)) {
    [void][System.Windows.Forms.MessageBox]::Show([string]$cfg.aviso, 'Observer RMM', 'OK', 'Information')
    [IO.File]::WriteAllText($marcaAviso, (Get-Date -Format 's'), $utf8)
}

function Write-Linea($texto) {
    $archivo = Join-Path $dirDatos ((Get-Date -Format 'yyyy-MM-dd') + '.tsv')
    [IO.File]::AppendAllText($archivo, $texto + "`n", $utf8)
}

$boot = 0
try { $boot = ConvertTo-Epoch (Get-CimInstance Win32_OperatingSystem).LastBootUpTime } catch { $boot = 0 }
$sesion = 0
try {
    $miSesion = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    $exp = Get-Process -Name explorer | Where-Object { $_.SessionId -eq $miSesion } | Sort-Object StartTime | Select-Object -First 1
    if ($exp) { $sesion = ConvertTo-Epoch $exp.StartTime }
}
catch { $sesion = 0 }
Write-Linea ((Get-Date -Format 's') + "`t$usuario`t#inicio`t0`t0`tboot=$boot;sesion=$sesion")

$vuelta = 0
$ultimaCaptura = [datetime]::MinValue
$ultimaLimpieza = [datetime]::MinValue
while ($true) {
    $inicioVuelta = Get-Date
    if ($vuelta % 10 -eq 0) { $cfg = Read-Config }
    $vuelta++
    $intervalo = [Math]::Max(15, [int]$cfg.intervalo)

    $h = [OAct]::GetForegroundWindow()
    $procId = [uint32]0
    $proceso = '(escritorio)'
    if ($h -ne [IntPtr]::Zero) {
        [void][OAct]::GetWindowThreadProcessId($h, [ref]$procId)
        if ($procId -gt 0) {
            $p = Get-Process -Id $procId
            if ($p) { $proceso = $p.ProcessName.ToLowerInvariant() + '.exe' }
        }
    }
    $idle = [OAct]::IdleSeconds()
    $activo = 0
    if ($idle -lt [int]$cfg.inactivo_seg -and $proceso -ne 'lockapp.exe' -and $proceso -ne '(escritorio)') { $activo = 1 }

    $titulo = ''
    if ($cfg.titulos -and $h -ne [IntPtr]::Zero) {
        $titulo = ([OAct]::Title($h)) -replace "[`t`r`n]", ' '
        if ($titulo.Length -gt 200) { $titulo = $titulo.Substring(0, 200) }
    }
    Write-Linea ($inicioVuelta.ToString('s') + "`t$usuario`t$proceso`t$activo`t$intervalo`t$titulo")

    if ($cfg.capturas -and $activo -eq 1) {
        $cada = 10; if ($cfg.cada_captura_min) { $cada = [int]$cfg.cada_captura_min }
        if (($inicioVuelta - $ultimaCaptura).TotalMinutes -ge $cada) {
            Save-Captura $dirCap $cfg
            $ultimaCaptura = $inicioVuelta
        }
    }
    if (($inicioVuelta - $ultimaLimpieza).TotalHours -ge 1) {
        Remove-Antiguos $dirCap $dirDatos $cfg
        $ultimaLimpieza = $inicioVuelta
    }

    $resto = $intervalo - ((Get-Date) - $inicioVuelta).TotalSeconds
    if ($resto -gt 0) { Start-Sleep -Milliseconds ([int]($resto * 1000)) }
}
'@

$lanzador = @'
' Observer Actividad - arranca el muestreador sin ventana (feature 048).
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%ProgramData%") & "\ObserverActividad\muestreo.ps1"
sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & base & """", 0, False
'@

function Get-TareaXml {
    $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
    $vbs = Join-Path $base "lanzador.vbs"
    $inicio = (Get-Date).ToString("yyyy-MM-ddT00:00:00")
    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Observer Actividad: muestreo de uso del equipo (Observer RMM, feature 048).</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
    <TimeTrigger>
      <Repetition><Interval>PT15M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>$inicio</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Usuarios">
      <GroupId>S-1-5-32-545</GroupId>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>Parallel</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Usuarios">
    <Exec>
      <Command>$wscript</Command>
      <Arguments>//B //Nologo "$vbs"</Arguments>
    </Exec>
  </Actions>
</Task>
"@
}

function Get-PerfilesDatos {
    $perfiles = @()
    try {
        $perfiles = Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and $_.LocalPath }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
    foreach ($perfil in $perfiles) {
        $raiz = Join-Path $perfil.LocalPath "AppData\Local\ObserverActividad"
        if (Test-Path -LiteralPath $raiz) {
            [pscustomobject]@{ Perfil = $perfil.LocalPath; Raiz = $raiz }
        }
    }
}

function Show-Estado {
    Write-Output "== Observer Actividad: estado =="
    $cfgPath = Join-Path $base "config.json"
    if (-not (Test-Path -LiteralPath $cfgPath)) {
        Write-Output "No instalado (no existe $cfgPath)."
        return
    }
    Write-Output ("Configuracion: " + [IO.File]::ReadAllText($cfgPath, $utf8))
    $tarea = Get-ScheduledTask -TaskName $nombreTarea -ErrorAction SilentlyContinue
    if ($tarea) {
        Write-Output ("Tarea programada: " + $tarea.State)
    }
    else {
        Write-Output "Tarea programada: NO EXISTE"
    }
    $vivos = @(Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" | Where-Object { $_.CommandLine -like "*ObserverActividad\muestreo.ps1*" })
    Write-Output ("Muestreadores en ejecucion: " + $vivos.Count)
    foreach ($d in Get-PerfilesDatos) {
        $ultimo = Get-ChildItem -LiteralPath (Join-Path $d.Raiz "datos") -Filter "*.tsv" -File -ErrorAction SilentlyContinue |
            Sort-Object Name | Select-Object -Last 1
        $nCap = @(Get-ChildItem -LiteralPath (Join-Path $d.Raiz "capturas") -Recurse -File -Filter "*.jpg" -ErrorAction SilentlyContinue).Count
        if ($ultimo) {
            Write-Output ("{0}: ultimo archivo {1} ({2} KB, modificado {3:s}); capturas guardadas: {4}" -f
                $d.Perfil, $ultimo.Name, [int]($ultimo.Length / 1KB), $ultimo.LastWriteTime, $nCap)
        }
        else {
            Write-Output ("{0}: sin datos todavia; capturas guardadas: {1}" -f $d.Perfil, $nCap)
        }
    }
}

switch ($Modo) {
    "estado" {
        Show-Estado
    }
    "instalar" {
        [void](New-Item -ItemType Directory -Force -Path $base)
        # Usuarios: solo lectura y ejecucion. Sin esto, la herencia de ProgramData les
        # deja crear archivos en la carpeta y podrian reemplazar el muestreador.
        & icacls.exe $base /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-32-545:(OI)(CI)RX" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "icacls fallo con codigo $LASTEXITCODE" }

        $detalle = @()
        if ($Titulos -eq "on") { $detalle += ", el t$i" + "tulo de la ventana activa" }
        if ($Capturas -eq "on") { $detalle += " y capturas de pantalla peri$o" + "dicas" }
        $textoAviso = $Aviso
        if (-not $textoAviso) { $textoAviso = $avisoDefecto -f ($detalle -join ""), "" }
        if ($SinAviso) { $textoAviso = "" }

        $cfg = [ordered]@{
            version                 = 1
            intervalo               = $Intervalo
            inactivo_seg            = $InactivoSeg
            titulos                 = ($Titulos -eq "on")
            capturas                = ($Capturas -eq "on")
            cada_captura_min        = $CadaCaptura
            ancho_captura           = 1280
            calidad_captura         = 40
            retencion_capturas_dias = $RetencionCapturas
            retencion_datos_dias    = $RetencionDatos
            aviso                   = $textoAviso
        }
        [IO.File]::WriteAllText((Join-Path $base "config.json"), ($cfg | ConvertTo-Json), $utf8)
        # El muestreador con BOM: es lo que hace que PowerShell 5.1 lo lea como UTF-8.
        [IO.File]::WriteAllText((Join-Path $base "muestreo.ps1"), $muestreo, (New-Object System.Text.UTF8Encoding $true))
        [IO.File]::WriteAllText((Join-Path $base "lanzador.vbs"), $lanzador, [System.Text.Encoding]::ASCII)

        Register-ScheduledTask -TaskName $nombreTarea -Xml (Get-TareaXml) -Force | Out-Null
        # Arranca ya en las sesiones abiertas; si no, el watchdog lo hace en <= 15 min.
        try { Start-ScheduledTask -TaskName $nombreTarea } catch { Write-Verbose $_.Exception.Message }
        Write-Output "Observer Actividad instalado/actualizado."
        Show-Estado
    }
    "desinstalar" {
        Unregister-ScheduledTask -TaskName $nombreTarea -Confirm:$false -ErrorAction SilentlyContinue
        Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
            Where-Object { $_.CommandLine -like "*ObserverActividad\muestreo.ps1*" } |
            ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }
        if (Test-Path -LiteralPath $base) { Remove-Item -LiteralPath $base -Recurse -Force }
        if ($BorrarDatos) {
            foreach ($d in Get-PerfilesDatos) {
                Remove-Item -LiteralPath $d.Raiz -Recurse -Force
                Write-Output ("Datos borrados: " + $d.Raiz)
            }
        }
        else {
            Write-Output "Datos de los perfiles conservados (usar -BorrarDatos para borrarlos)."
        }
        Write-Output "Observer Actividad desinstalado."
    }
}
