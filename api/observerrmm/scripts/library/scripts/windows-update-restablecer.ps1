<#
.SYNOPSIS
    Restablece Windows Update, o devuelve su control a Microsoft.

.DESCRIPTION
    Une los dos scripts del catalogo original, que resuelven los dos problemas
    distintos de Windows Update en un parque administrado:

      reparar   - Windows Update dejo de funcionar. Detiene los servicios, renombra las
                  carpetas de cache (SoftwareDistribution y catroot2), vuelve a
                  registrar los componentes y los arranca de nuevo. Windows reconstruye
                  la cache en el proximo chequeo. Es el procedimiento clasico y es
                  seguro: no borra, RENOMBRA, asi que se puede volver atras.

      devolver  - el agente RMM deja marcada la clave de registro que deshabilita las
                  actualizaciones automaticas, para poder gestionarlas el. Si el equipo
                  sale del parque, o se decide que Windows vuelva a actualizarse solo,
                  hay que quitar esa marca; si no, el equipo se queda sin parches y
                  nada avisa.

    En modo 'estado' informa que esta gobernando las actualizaciones: la politica del
    agente, una directiva de grupo del dominio, o nada.

.PARAMETER Modo
    estado (por defecto), reparar, devolver.

.EXAMPLE
    windows-update-restablecer.ps1
    windows-update-restablecer.ps1 -Modo reparar
    windows-update-restablecer.ps1 -Modo devolver
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "reparar", "devolver")]
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

# El estado "en ejecucion" como valor del enum de .NET y no como la cadena "Running":
# el enum no se traduce, el texto que Windows muestra si. Comparar contra el enum
# sigue valiendo si manana el objeto viene de Win32_Service en vez de Get-Service.
$EN_EJECUCION = [System.ServiceProcess.ServiceControllerStatus]::Running
$rutaPolitica = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
$rutaPoliticaWu = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
$servicios = @("wuauserv", "bits", "cryptsvc", "msiserver")

function Show-EstadoWu {
    param([string]$Titulo)

    Write-Output ""
    Write-Output "== $Titulo =="

    Write-Output ""
    Write-Output "  Servicios:"
    foreach ($nombre in $servicios) {
        try {
            $servicio = Get-Service -Name $nombre -ErrorAction Stop
            Write-Output "    $nombre : $($servicio.Status) / inicio $($servicio.StartType)"
        }
        catch {
            Write-Output "    $nombre : no existe en este equipo"
        }
    }

    Write-Output ""
    Write-Output "  Politica de actualizaciones automaticas:"
    if (Test-Path $rutaPolitica) {
        try {
            $politica = Get-ItemProperty -Path $rutaPolitica -ErrorAction Stop
            if ($null -ne $politica.NoAutoUpdate) {
                $texto = if ([int]$politica.NoAutoUpdate -eq 1) { "DESHABILITADAS (NoAutoUpdate=1)" } else { "habilitadas (NoAutoUpdate=0)" }
                Write-Output "    $texto"
            }
            else {
                Write-Output "    la clave existe pero no define NoAutoUpdate"
            }
            if ($null -ne $politica.AUOptions) {
                Write-Output "    AUOptions = $($politica.AUOptions)"
            }
        }
        catch {
            Write-Output "    no se pudo leer: $($_.Exception.Message)"
        }
    }
    else {
        Write-Output "    sin politica local: Windows decide (comportamiento por defecto)"
    }

    # Un WSUS configurado explica por que el equipo no ve las actualizaciones de
    # Microsoft, y no hay que tocarlo desde aca.
    if (Test-Path $rutaPoliticaWu) {
        try {
            $wu = Get-ItemProperty -Path $rutaPoliticaWu -ErrorAction Stop
            if ($wu.WUServer) {
                Write-Output ""
                Write-Output "  WSUS configurado: $($wu.WUServer)"
                Write-Output "  (lo gobierna el dominio: este script no lo modifica)"
            }
        }
        catch {
            Write-Verbose $_.Exception.Message
        }
    }

    Write-Output ""
    Write-Output "  Cache de actualizaciones:"
    $rutaCache = Join-Path $env:SystemRoot "SoftwareDistribution"
    if (Test-Path $rutaCache) {
        try {
            $bytes = 0
            foreach ($archivo in (Get-ChildItem -Path $rutaCache -Recurse -File -ErrorAction SilentlyContinue)) {
                $bytes += $archivo.Length
            }
            Write-Output "    SoftwareDistribution: $([Math]::Round($bytes / 1MB, 1)) MB"
        }
        catch {
            Write-Output "    SoftwareDistribution: presente (no se pudo medir)"
        }
    }
    else {
        Write-Output "    SoftwareDistribution: no existe (se recrea al buscar actualizaciones)"
    }
}

Show-EstadoWu -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modifico nada."
    exit 0
}

$errores = 0

if ($Modo -eq "devolver") {
    Write-Output ""
    Write-Output "== Devolviendo el control de las actualizaciones a Windows =="

    if (-not (Test-Path $rutaPolitica)) {
        Write-Output "  No hay politica local: Windows ya gobierna sus actualizaciones."
        exit 0
    }

    try {
        # Se pone NoAutoUpdate=0 en vez de borrar la clave: borrarla deja el equipo en
        # el estado por defecto, pero si una GPO la vuelve a escribir el resultado es
        # impredecible. Un 0 explicito es inequivoco.
        Set-ItemProperty -Path $rutaPolitica -Name NoAutoUpdate -Value 0 -Type DWord -ErrorAction Stop
        Write-Output "  NoAutoUpdate = 0 : OK"

        $verificado = (Get-ItemProperty -Path $rutaPolitica -Name NoAutoUpdate -ErrorAction Stop).NoAutoUpdate
        if ([int]$verificado -ne 0) {
            Write-Output "  FALLA: quedo en $verificado. Puede haber una GPO pisandolo."
            $errores++
        }
    }
    catch {
        Write-Output "  ERROR: $($_.Exception.Message)"
        $errores++
    }

    try {
        Start-Service -Name wuauserv -ErrorAction Stop
        Write-Output "  servicio wuauserv arrancado."
    }
    catch {
        Write-Output "  AVISO: no se pudo arrancar wuauserv: $($_.Exception.Message)"
    }

    Show-EstadoWu -Titulo "Estado resultante"
    Write-Output ""
    if ($errores -gt 0) { exit 1 }
    Write-Output "Windows vuelve a gestionar sus actualizaciones."
    Write-Output "AVISO: desde ahora el equipo puede reiniciarse por su cuenta para"
    Write-Output "aplicar parches, fuera de las ventanas del RMM."
    exit 0
}

Write-Output ""
Write-Output "== Reparando Windows Update =="

Write-Output ""
Write-Output "  Deteniendo servicios..."
foreach ($nombre in $servicios) {
    try {
        $servicio = Get-Service -Name $nombre -ErrorAction Stop
        if ($servicio.Status -eq $EN_EJECUCION) {
            Stop-Service -Name $nombre -Force -ErrorAction Stop
            Write-Output "    detenido: $nombre"
        }
        else {
            Write-Output "    ya estaba detenido: $nombre"
        }
    }
    catch {
        Write-Output "    ERROR al detener $nombre : $($_.Exception.Message)"
        $errores++
    }
}

# Renombrar en vez de borrar: si algo sale mal, la cache vieja sigue ahi. El sufijo
# lleva la fecha para no chocar con un intento anterior.
$sufijo = Get-Date -Format "yyyyMMddHHmmss"
Write-Output ""
Write-Output "  Renombrando carpetas de cache (no se borran)..."
foreach ($carpeta in @("SoftwareDistribution", "System32\catroot2")) {
    $ruta = Join-Path $env:SystemRoot $carpeta
    if (-not (Test-Path $ruta)) {
        Write-Output "    no existe, se omite: $carpeta"
        continue
    }
    $destino = "$ruta.old.$sufijo"
    try {
        Rename-Item -Path $ruta -NewName (Split-Path $destino -Leaf) -ErrorAction Stop
        Write-Output "    renombrada: $carpeta -> $(Split-Path $destino -Leaf)"
    }
    catch {
        Write-Output "    ERROR al renombrar $carpeta : $($_.Exception.Message)"
        Write-Output "    (suele ser que un servicio sigue usandola)"
        $errores++
    }
}

Write-Output ""
Write-Output "  Arrancando servicios..."
foreach ($nombre in $servicios) {
    try {
        Start-Service -Name $nombre -ErrorAction Stop
        Write-Output "    arrancado: $nombre"
    }
    catch {
        Write-Output "    ERROR al arrancar $nombre : $($_.Exception.Message)"
        $errores++
    }
}

# Verificacion por efecto: los servicios tienen que quedar corriendo.
Write-Output ""
Write-Output "  Verificando..."
foreach ($nombre in @("wuauserv", "bits")) {
    try {
        $estado = (Get-Service -Name $nombre -ErrorAction Stop).Status
        if ($estado -ne $EN_EJECUCION) {
            Write-Output "    FALLA: $nombre quedo en estado $estado"
            $errores++
        }
        else {
            Write-Output "    OK: $nombre corriendo"
        }
    }
    catch {
        Write-Output "    no se pudo verificar $nombre"
        $errores++
    }
}

Show-EstadoWu -Titulo "Estado resultante"

Write-Output ""
Write-Output "== Resultado =="
if ($errores -gt 0) {
    Write-Output "  Termino con $errores error(es)."
    Write-Output "  Si fallo el renombrado, reinicia el equipo y volve a correrlo:"
    Write-Output "  tras el arranque las carpetas suelen estar liberadas."
    exit 1
}

Write-Output "  Windows Update restablecido."
Write-Output "  La cache se reconstruye en el proximo chequeo de actualizaciones, que"
Write-Output "  por eso va a tardar mas de lo normal."
Write-Output "  Las carpetas viejas quedaron con sufijo .old.$sufijo - borralas cuando"
Write-Output "  confirmes que las actualizaciones funcionan."
exit 0
