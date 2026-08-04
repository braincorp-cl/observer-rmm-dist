<#
.SYNOPSIS
    Lista, busca y desinstala software instalado, con desinstalacion silenciosa.

.DESCRIPTION
    El mejor script del catalogo original, reescrito. Resuelve el problema real de
    desinstalar en remoto: sin nadie frente al equipo, un desinstalador que abre un
    dialogo se queda colgado hasta que el timeout lo mate, dejando el software a medio
    quitar.

    Busca en las tres fuentes que hay que mirar, porque ninguna sola las tiene todas:

      1. Registro de 64 bits (Uninstall).
      2. Registro de 32 bits (WOW6432Node), donde vive todo el software de 32 bits.
      3. Registro por usuario (HKCU) de cada perfil, donde aparece lo que se instalo
         "solo para mi" y que no se ve como administrador.

    Para desinstalar arma la orden en este orden de preferencia: la cadena silenciosa
    que declara el propio producto (QuietUninstallString), o si no la hay, la normal
    con los modificadores silenciosos que corresponden al tipo de instalador (MSI o
    InnoSetup/NSIS detectados por la forma de la cadena).

    Deliberadamente NO usa la clase Win32_Product de WMI, que es la via mas citada:
    enumerarla dispara una reconfiguracion de cada paquete MSI del equipo, es lentisima
    y puede reparar software sin que nadie lo haya pedido.

.PARAMETER Modo
    listar (por defecto), buscar, desinstalar.

.PARAMETER Nombre
    Texto a buscar en el nombre del producto. Obligatorio en buscar y desinstalar.

.PARAMETER Exacto
    Exige coincidencia exacta del nombre en vez de subcadena. Recomendado al desinstalar.

.PARAMETER TiempoEsperaSegundos
    Espera maxima por desinstalador. Por defecto 600.

.EXAMPLE
    software-desinstalador.ps1
    software-desinstalador.ps1 -Modo buscar -Nombre "7-Zip"
    software-desinstalador.ps1 -Modo desinstalar -Nombre "7-Zip 22.01 (x64)" -Exacto
#>

[CmdletBinding()]
param(
    [ValidateSet("listar", "buscar", "desinstalar")]
    [string]$Modo = "listar",

    [string]$Nombre,

    [switch]$Exacto,

    [int]$TiempoEsperaSegundos = 600
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

function Get-SoftwareInstalado {
    $rutas = @(
        @{ Ruta = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"; Ambito = "equipo (64)" },
        @{ Ruta = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"; Ambito = "equipo (32)" }
    )

    # Los perfiles de usuario: se montan sus colmenas solo si no estan ya cargadas.
    # Sin esto se pierde todo lo instalado "solo para este usuario".
    try {
        foreach ($colmena in (Get-ChildItem "Registry::HKEY_USERS" -ErrorAction Stop)) {
            $sid = Split-Path $colmena.Name -Leaf
            # Se descartan las cuentas de servicio y las colmenas de clases.
            if ($sid -match "_Classes$") { continue }
            if ($sid -match "^S-1-5-(18|19|20)$") { continue }
            $rutas += @{
                Ruta   = "Registry::HKEY_USERS\$sid\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
                Ambito = "usuario $sid"
            }
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }

    $productos = New-Object System.Collections.ArrayList

    foreach ($entrada in $rutas) {
        try {
            $claves = @(Get-ItemProperty -Path $entrada.Ruta -ErrorAction SilentlyContinue)
        }
        catch {
            continue
        }

        foreach ($clave in $claves) {
            if (-not $clave.DisplayName) { continue }
            # SystemComponent=1 marca lo que Windows oculta del panel de control:
            # runtimes, parches y componentes. Mostrarlos llena la lista de ruido.
            if ($clave.SystemComponent -eq 1) { continue }
            # Las actualizaciones de un producto no son productos.
            if ($clave.ParentKeyName -or $clave.ParentDisplayName) { continue }

            [void]$productos.Add([pscustomobject]@{
                    Nombre       = $clave.DisplayName
                    Version      = $clave.DisplayVersion
                    Editor       = $clave.Publisher
                    Fecha        = $clave.InstallDate
                    Tamano       = $clave.EstimatedSize
                    Ambito       = $entrada.Ambito
                    Desinstalar  = $clave.UninstallString
                    Silencioso   = $clave.QuietUninstallString
                    ClaveRegistro = $clave.PSChildName
                })
        }
    }

    return $productos | Sort-Object Nombre -Unique
}

function Get-OrdenSilenciosa {
    param([pscustomobject]$Producto)

    # 1) Si el producto declara su propia cadena silenciosa, es la fuente autoritativa.
    if ($Producto.Silencioso) {
        return @{ Cadena = $Producto.Silencioso; Origen = "QuietUninstallString del producto" }
    }

    if (-not $Producto.Desinstalar) {
        return $null
    }

    $cadena = $Producto.Desinstalar

    # 2) MSI: se normaliza a msiexec /x <guid> /qn con reinicio suprimido.
    if ($cadena -match "msiexec" -and $cadena -match "(\{[0-9A-Fa-f\-]{36}\})") {
        $guid = $Matches[1]
        return @{
            Cadena = "msiexec.exe /x $guid /qn /norestart REBOOT=ReallySuppress"
            Origen = "MSI normalizado"
        }
    }

    # 3) InnoSetup: su desinstalador es unins###.exe y acepta /SILENT /NORESTART.
    if ($cadena -match "unins\d*\.exe") {
        return @{
            Cadena = "$cadena /VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
            Origen = "InnoSetup"
        }
    }

    # 4) NSIS: acepta /S. Es el caso menos fiable porque /S no es universal.
    if ($cadena -match "[Uu]ninstall.*\.exe") {
        return @{ Cadena = "$cadena /S"; Origen = "NSIS (probable, /S no es universal)" }
    }

    return @{ Cadena = $cadena; Origen = "cadena original SIN modificador silencioso" }
}

$productos = @(Get-SoftwareInstalado)

if ($Modo -eq "listar") {
    Write-Output "$($productos.Count) producto(s) instalado(s)."
    foreach ($producto in $productos) {
        Write-Output ""
        Write-Output "$($producto.Nombre)"
        Write-Output "  version: $($producto.Version)"
        Write-Output "  editor:  $($producto.Editor)"
        Write-Output "  ambito:  $($producto.Ambito)"
        if ($producto.Tamano) {
            Write-Output "  tamano:  $([Math]::Round($producto.Tamano / 1024, 1)) MB"
        }
        Write-Output "  silencioso disponible: $(if ($producto.Silencioso) { 'si' } else { 'no declarado' })"
    }
    exit 0
}

if (-not $Nombre) {
    Write-Output "El modo '$Modo' exige el parametro -Nombre."
    exit 1
}

if ($Exacto) {
    $coincidencias = @($productos | Where-Object { $_.Nombre -eq $Nombre })
}
else {
    $coincidencias = @($productos | Where-Object { $_.Nombre -like "*$Nombre*" })
}

Write-Output "Busqueda: '$Nombre'$(if ($Exacto) { ' (exacta)' })"
Write-Output "$($coincidencias.Count) coincidencia(s)."

foreach ($producto in $coincidencias) {
    Write-Output ""
    Write-Output "$($producto.Nombre)"
    Write-Output "  version:      $($producto.Version)"
    Write-Output "  editor:       $($producto.Editor)"
    Write-Output "  ambito:       $($producto.Ambito)"
    Write-Output "  cadena orig.: $($producto.Desinstalar)"
    $orden = Get-OrdenSilenciosa -Producto $producto
    if ($orden) {
        Write-Output "  orden a usar: $($orden.Cadena)"
        Write-Output "  origen:       $($orden.Origen)"
    }
    else {
        Write-Output "  orden a usar: NINGUNA (el producto no declara desinstalador)"
    }
}

if ($Modo -eq "buscar") {
    Write-Output ""
    Write-Output "Modo 'buscar': no se desinstalo nada."
    if ($coincidencias.Count -eq 0) { exit 1 }
    exit 0
}

if ($coincidencias.Count -eq 0) {
    Write-Output ""
    Write-Output "Nada que desinstalar."
    exit 1
}

# Freno: desinstalar varias cosas por una busqueda amplia es la forma de vaciar un
# equipo por accidente. Con mas de una coincidencia se exige precision.
if ($coincidencias.Count -gt 1 -and -not $Exacto) {
    Write-Output ""
    Write-Output "ABORTADO: la busqueda '$Nombre' coincide con $($coincidencias.Count) productos."
    Write-Output "Afina el nombre, o usa -Exacto con el nombre completo de arriba."
    exit 1
}

$desinstalados = 0
$errores = 0

foreach ($producto in $coincidencias) {
    Write-Output ""
    Write-Output "== Desinstalando: $($producto.Nombre) =="

    $orden = Get-OrdenSilenciosa -Producto $producto
    if (-not $orden) {
        Write-Output "  ERROR: el producto no declara ninguna forma de desinstalarse."
        $errores++
        continue
    }

    if ($orden.Origen -like "*SIN modificador*") {
        Write-Output "  AVISO: no se pudo determinar un modificador silencioso. El"
        Write-Output "  desinstalador puede abrir un dialogo y quedarse esperando hasta"
        Write-Output "  agotar la espera de $TiempoEsperaSegundos s."
    }

    Write-Output "  orden: $($orden.Cadena)"

    try {
        # Se parte la cadena en ejecutable y argumentos: Start-Process necesita el
        # ejecutable aparte, y las rutas con espacios vienen entre comillas.
        $cadena = $orden.Cadena.Trim()
        if ($cadena.StartsWith('"')) {
            $cierre = $cadena.IndexOf('"', 1)
            $ejecutable = $cadena.Substring(1, $cierre - 1)
            $argumentos = $cadena.Substring($cierre + 1).Trim()
        }
        else {
            $partes = $cadena.Split(" ", 2)
            $ejecutable = $partes[0]
            $argumentos = if ($partes.Count -gt 1) { $partes[1] } else { "" }
        }

        $parametros = @{
            FilePath    = $ejecutable
            Wait        = $true
            PassThru    = $true
            NoNewWindow = $true
            ErrorAction = "Stop"
        }
        if ($argumentos) { $parametros["ArgumentList"] = $argumentos }

        $proceso = Start-Process @parametros
        $codigo = $proceso.ExitCode
        Write-Output "  el desinstalador devolvio codigo $codigo"

        # 3010 y 1641 significan "hecho, hace falta reiniciar": son exitos, no fallas.
        if ($codigo -eq 0) {
            Write-Output "  desinstalacion completada."
        }
        elseif ($codigo -eq 3010 -or $codigo -eq 1641) {
            Write-Output "  desinstalacion completada, PENDIENTE DE REINICIO."
        }
        else {
            Write-Output "  codigo no exitoso."
            $errores++
            continue
        }
    }
    catch {
        Write-Output "  ERROR al ejecutar el desinstalador: $($_.Exception.Message)"
        $errores++
        continue
    }

    # Verificacion por efecto: volver a enumerar y confirmar que ya no aparece. El
    # codigo de salida del desinstalador no alcanza: hay instaladores que devuelven 0
    # sin haber quitado nada.
    Start-Sleep -Seconds 3
    $restantes = @(Get-SoftwareInstalado | Where-Object { $_.Nombre -eq $producto.Nombre })
    if ($restantes.Count -gt 0) {
        Write-Output "  FALLA: '$($producto.Nombre)' sigue apareciendo como instalado."
        Write-Output "  Puede quedar pendiente de reinicio, o el desinstalador fallo en silencio."
        $errores++
    }
    else {
        Write-Output "  verificado: ya no aparece en el registro."
        $desinstalados++
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $desinstalados desinstalado(s) y verificado(s), $errores con problema."

if ($errores -gt 0) { exit 1 }
exit 0
