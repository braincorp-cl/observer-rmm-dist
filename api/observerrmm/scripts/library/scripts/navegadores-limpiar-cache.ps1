<#
.SYNOPSIS
    Limpia la caché de los navegadores en todos los perfiles de usuario.

.DESCRIPTION
    Une los dos scripts del catálogo original (Chrome y Firefox) y agrega Edge, que
    hoy es el navegador que viene con Windows y faltaba.

    Borra SOLO caché: archivos que el navegador vuelve a descargar. NO toca el
    historial, los marcadores, las contraseñas guardadas, las cookies ni las sesiones
    abiertas. Es la diferencia entre "arreglame la página que carga mal" y "me borraste
    todas mis contraseñas", y es la razón de que las rutas estén enumeradas una por una
    en vez de borrar la carpeta de perfil entera.

    Recorre TODOS los perfiles de usuario del equipo, no solo el que corre el script:
    el agente corre como SYSTEM y su caché no le interesa a nadie.

    Un navegador abierto mantiene sus archivos de caché bloqueados: lo que no se pueda
    borrar se informa. El script no cierra navegadores por su cuenta — eso le haría
    perder trabajo al usuario sin avisarle.

.PARAMETER Modo
    simular (por defecto) o aplicar.

.PARAMETER Navegador
    todos (por defecto), chrome, edge, firefox.

.EXAMPLE
    navegadores-limpiar-cache.ps1
    navegadores-limpiar-cache.ps1 -Modo aplicar
    navegadores-limpiar-cache.ps1 -Modo aplicar -Navegador chrome
#>

[CmdletBinding()]
param(
    [ValidateSet("simular", "aplicar")]
    [string]$Modo = "simular",

    [ValidateSet("todos", "chrome", "edge", "firefox")]
    [string]$Navegador = "todos"
)

$ErrorActionPreference = "Continue"

$aplicar = $Modo -eq "aplicar"

# Rutas de caché relativas al perfil del usuario. Cada entrada es SOLO caché: nada de
# esto contiene datos que el usuario pueda echar de menos.
$RUTAS_CHROME = @(
    "AppData\Local\Google\Chrome\User Data\Default\Cache",
    "AppData\Local\Google\Chrome\User Data\Default\Code Cache",
    "AppData\Local\Google\Chrome\User Data\Default\GPUCache",
    "AppData\Local\Google\Chrome\User Data\Default\Service Worker\CacheStorage",
    "AppData\Local\Google\Chrome\User Data\ShaderCache",
    "AppData\Local\Google\Chrome\User Data\GrShaderCache"
)

$RUTAS_EDGE = @(
    "AppData\Local\Microsoft\Edge\User Data\Default\Cache",
    "AppData\Local\Microsoft\Edge\User Data\Default\Code Cache",
    "AppData\Local\Microsoft\Edge\User Data\Default\GPUCache",
    "AppData\Local\Microsoft\Edge\User Data\Default\Service Worker\CacheStorage",
    "AppData\Local\Microsoft\Edge\User Data\ShaderCache",
    "AppData\Local\Microsoft\Edge\User Data\GrShaderCache"
)

# Firefox usa un nombre de perfil aleatorio, así que su caché se resuelve por comodín
# en tiempo de ejecución en vez de enumerarse.
$RAIZ_FIREFOX = "AppData\Local\Mozilla\Firefox\Profiles"

$PROCESOS = @{
    chrome  = @("chrome")
    edge    = @("msedge")
    firefox = @("firefox")
}

function Get-TamanoCarpeta {
    param([string]$Ruta)
    $bytes = 0
    $archivos = 0
    try {
        foreach ($archivo in (Get-ChildItem -Path $Ruta -Recurse -File -Force -ErrorAction SilentlyContinue)) {
            $bytes += $archivo.Length
            $archivos++
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
    return @{ Bytes = $bytes; Archivos = $archivos }
}

function Clear-Cache {
    param([string]$Ruta)

    $medida = Get-TamanoCarpeta -Ruta $Ruta
    if (-not $aplicar) {
        return @{ Bytes = $medida.Bytes; Archivos = $medida.Archivos; Bloqueados = 0 }
    }

    $bloqueados = 0
    # Se borra el CONTENIDO, no la carpeta: el navegador espera que exista y la
    # recrearía igual, pero borrarla puede dejarlo sin permisos correctos.
    try {
        foreach ($item in (Get-ChildItem -Path $Ruta -Force -ErrorAction Stop)) {
            try {
                Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
            }
            catch {
                $bloqueados++
                Write-Verbose "$($item.FullName): $($_.Exception.Message)"
            }
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }

    $despues = Get-TamanoCarpeta -Ruta $Ruta
    return @{
        Bytes      = [Math]::Max(0, $medida.Bytes - $despues.Bytes)
        Archivos   = [Math]::Max(0, $medida.Archivos - $despues.Archivos)
        Bloqueados = $bloqueados
    }
}

Write-Output "Limpieza de caché de navegadores"
Write-Output "  modo:      $(if ($aplicar) { 'APLICAR (borra de verdad)' } else { 'SIMULAR' })"
Write-Output "  navegador: $Navegador"

# Navegadores abiertos: se avisa, no se cierran.
Write-Output ""
Write-Output "== Navegadores en ejecución =="
$abiertos = @()
foreach ($clave in $PROCESOS.Keys) {
    if ($Navegador -ne "todos" -and $Navegador -ne $clave) { continue }
    foreach ($nombreProceso in $PROCESOS[$clave]) {
        $procesos = @(Get-Process -Name $nombreProceso -ErrorAction SilentlyContinue)
        if ($procesos.Count -gt 0) {
            Write-Output "  $clave : $($procesos.Count) proceso(s) — su caché está bloqueada"
            $abiertos += $clave
        }
    }
}
if ($abiertos.Count -eq 0) {
    Write-Output "  ninguno abierto."
}

$perfiles = @()
$raizPerfiles = Join-Path ($env:SystemDrive + "\") "Users"
try {
    $perfiles = @(Get-ChildItem -Path $raizPerfiles -Directory -ErrorAction Stop |
        Where-Object { $_.Name -notin @("Public", "Default", "Default User", "All Users") })
}
catch {
    Write-Output ""
    Write-Output "No se pudo enumerar los perfiles en $raizPerfiles : $($_.Exception.Message)"
    exit 1
}

$totalBytes = 0
$totalArchivos = 0
$totalBloqueados = 0

foreach ($perfil in $perfiles) {
    $objetivos = New-Object System.Collections.ArrayList

    if ($Navegador -eq "todos" -or $Navegador -eq "chrome") {
        foreach ($relativa in $RUTAS_CHROME) {
            [void]$objetivos.Add(@{ Etiqueta = "Chrome"; Ruta = Join-Path $perfil.FullName $relativa })
        }
    }
    if ($Navegador -eq "todos" -or $Navegador -eq "edge") {
        foreach ($relativa in $RUTAS_EDGE) {
            [void]$objetivos.Add(@{ Etiqueta = "Edge"; Ruta = Join-Path $perfil.FullName $relativa })
        }
    }
    if ($Navegador -eq "todos" -or $Navegador -eq "firefox") {
        $raiz = Join-Path $perfil.FullName $RAIZ_FIREFOX
        if (Test-Path $raiz) {
            try {
                foreach ($perfilFirefox in (Get-ChildItem -Path $raiz -Directory -ErrorAction Stop)) {
                    [void]$objetivos.Add(@{
                            Etiqueta = "Firefox"
                            Ruta     = Join-Path $perfilFirefox.FullName "cache2"
                        })
                }
            }
            catch {
                Write-Verbose $_.Exception.Message
            }
        }
    }

    $bytesPerfil = 0
    $lineas = New-Object System.Collections.ArrayList

    foreach ($objetivo in $objetivos) {
        if (-not (Test-Path $objetivo.Ruta)) { continue }
        $resultado = Clear-Cache -Ruta $objetivo.Ruta
        if ($resultado.Bytes -eq 0 -and $resultado.Archivos -eq 0) { continue }

        $bytesPerfil += $resultado.Bytes
        $totalBytes += $resultado.Bytes
        $totalArchivos += $resultado.Archivos
        $totalBloqueados += $resultado.Bloqueados

        $texto = "    $($objetivo.Etiqueta): $([Math]::Round($resultado.Bytes / 1MB, 1)) MB"
        if ($resultado.Bloqueados -gt 0) {
            $texto += " ($($resultado.Bloqueados) bloqueado[s])"
        }
        [void]$lineas.Add($texto)
    }

    if ($bytesPerfil -gt 0) {
        Write-Output ""
        Write-Output "  perfil $($perfil.Name): $([Math]::Round($bytesPerfil / 1MB, 1)) MB"
        foreach ($linea in $lineas) { Write-Output $linea }
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  perfiles revisados: $($perfiles.Count)"
Write-Output "  total $(if ($aplicar) { 'liberado' } else { 'que se liberaría' }): $([Math]::Round($totalBytes / 1MB, 1)) MB en $totalArchivos archivo(s)"

if ($totalBloqueados -gt 0) {
    Write-Output "  archivos bloqueados: $totalBloqueados"
    Write-Output ""
    Write-Output "  Los bloqueados son de un navegador abierto. Volvé a correrlo cuando"
    Write-Output "  el usuario lo cierre; este script no lo cierra para no hacerle"
    Write-Output "  perder pestañas ni formularios a medio llenar."
}

if (-not $aplicar) {
    Write-Output ""
    Write-Output "  No se borró nada. Volvé a correr con -Modo aplicar."
}

Write-Output ""
Write-Output "LIBERADO_MB=$([Math]::Round($totalBytes / 1MB, 1))"
exit 0
