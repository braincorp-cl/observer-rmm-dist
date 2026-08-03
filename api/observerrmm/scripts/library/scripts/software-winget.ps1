<#
.SYNOPSIS
    Instala, desinstala, actualiza o busca software con winget.

.DESCRIPTION
    Reemplaza los scripts de gestión de paquetes del catálogo original. Se eligió
    winget y NO el gestor comunitario que usaba el original: winget viene incluido en
    Windows 10 y 11, lo publica Microsoft y no depende de un repositorio comunitario
    con cuota de uso, que era justo la dependencia externa que se quiere sacar.

    Dos particularidades de winget en un contexto de RMM, que este script resuelve:

      1. Corre como SYSTEM. En esa cuenta winget puede no estar en el PATH aunque esté
         instalado, porque vive en el perfil del usuario. El script lo busca en las
         ubicaciones de máquina (WindowsApps y el paquete del Desktop App Installer).
      2. Exige aceptar acuerdos de forma interactiva la primera vez. Sin los
         modificadores de aceptación, cualquier operación se cuelga esperando una
         tecla que nadie va a apretar.

.PARAMETER Modo
    listar (por defecto), buscar, instalar, desinstalar, actualizar.

.PARAMETER Paquete
    Identificador del paquete, por ejemplo "7zip.7zip". Obligatorio salvo en listar
    y en actualizar-todo.

.PARAMETER Todo
    En modo actualizar, actualiza todos los paquetes con actualización disponible.

.EXAMPLE
    software-winget.ps1
    software-winget.ps1 -Modo buscar -Paquete 7zip
    software-winget.ps1 -Modo instalar -Paquete 7zip.7zip
    software-winget.ps1 -Modo actualizar -Todo
#>

[CmdletBinding()]
param(
    [ValidateSet("listar", "buscar", "instalar", "desinstalar", "actualizar")]
    [string]$Modo = "listar",

    [string]$Paquete,

    [switch]$Todo
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

function Get-RutaWinget {
    # 1) En el PATH, si la cuenta lo tiene.
    $enPath = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($enPath) { return $enPath.Source }

    # 2) El alias de ejecución de máquina.
    $alias = Join-Path $env:ProgramFiles "WindowsApps\winget.exe"
    if (Test-Path $alias) { return $alias }

    # 3) El binario real dentro del paquete del Desktop App Installer. Corriendo como
    # SYSTEM esta es la única vía en la mayoría de los equipos.
    try {
        $candidatos = @(Get-ChildItem -Path (Join-Path $env:ProgramFiles "WindowsApps") `
                -Filter "Microsoft.DesktopAppInstaller_*" -Directory -ErrorAction Stop |
            Sort-Object Name -Descending)
        foreach ($candidato in $candidatos) {
            $binario = Join-Path $candidato.FullName "winget.exe"
            if (Test-Path $binario) { return $binario }
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }

    return $null
}

$winget = Get-RutaWinget
if (-not $winget) {
    Write-Output "No se encontró winget en este equipo."
    Write-Output ""
    Write-Output "Causas habituales:"
    Write-Output "  - Windows Server: no trae el Desktop App Installer de fábrica."
    Write-Output "  - Windows 10 anterior a 1809, o una imagen sin la Microsoft Store."
    Write-Output "  - El paquete existe pero no es accesible desde la cuenta SYSTEM."
    exit 1
}

Write-Output "winget: $winget"
try {
    $version = & $winget --version 2>&1
    Write-Output "versión: $($version -join ' ')"
}
catch {
    Write-Output "AVISO: no se pudo obtener la versión de winget."
}

# Sin estos modificadores winget espera confirmación interactiva y el script se cuelga
# hasta agotar el timeout.
$comunes = @(
    "--accept-source-agreements",
    "--disable-interactivity"
)

Write-Output ""

switch ($Modo) {
    "listar" {
        Write-Output "== Paquetes con actualización disponible =="
        $salida = & $winget upgrade @comunes 2>&1
        foreach ($linea in $salida) { Write-Output $linea }
        exit 0
    }

    "buscar" {
        if (-not $Paquete) {
            Write-Output "El modo 'buscar' exige el parámetro -Paquete."
            exit 1
        }
        Write-Output "== Buscando '$Paquete' =="
        $salida = & $winget search $Paquete @comunes 2>&1
        foreach ($linea in $salida) { Write-Output $linea }
        if ($LASTEXITCODE -ne 0) {
            Write-Output ""
            Write-Output "winget devolvió código $LASTEXITCODE"
            exit 1
        }
        exit 0
    }

    "instalar" {
        if (-not $Paquete) {
            Write-Output "El modo 'instalar' exige el parámetro -Paquete."
            exit 1
        }
        Write-Output "== Instalando '$Paquete' =="
        # --exact evita instalar un paquete parecido por una coincidencia difusa, que
        # es el riesgo real de instalar por nombre en vez de por identificador.
        # --scope machine lo instala para todos los usuarios, no solo para SYSTEM.
        $salida = & $winget install --id $Paquete --exact --silent --scope machine `
            --accept-package-agreements @comunes 2>&1
        foreach ($linea in $salida) { Write-Output $linea }
        $codigo = $LASTEXITCODE

        Write-Output ""
        if ($codigo -eq 0) {
            Write-Output "Instalación reportada como exitosa. Verificando..."
            $verificacion = & $winget list --id $Paquete --exact @comunes 2>&1
            $encontrado = ($verificacion -join " ") -match [regex]::Escape($Paquete)
            if ($encontrado) {
                Write-Output "verificado: '$Paquete' aparece como instalado."
                exit 0
            }
            Write-Output "FALLA: winget devolvió 0 pero el paquete no aparece instalado."
            exit 1
        }

        # -1978335189 es "no hay actualizaciones aplicables" / ya instalado.
        if ($codigo -eq -1978335189) {
            Write-Output "El paquete ya estaba instalado y al día."
            exit 0
        }
        Write-Output "La instalación falló (código $codigo)."
        exit 1
    }

    "desinstalar" {
        if (-not $Paquete) {
            Write-Output "El modo 'desinstalar' exige el parámetro -Paquete."
            exit 1
        }
        Write-Output "== Desinstalando '$Paquete' =="
        $salida = & $winget uninstall --id $Paquete --exact --silent @comunes 2>&1
        foreach ($linea in $salida) { Write-Output $linea }
        $codigo = $LASTEXITCODE

        Write-Output ""
        if ($codigo -ne 0) {
            Write-Output "La desinstalación falló (código $codigo)."
            exit 1
        }

        Start-Sleep -Seconds 3
        $verificacion = & $winget list --id $Paquete --exact @comunes 2>&1
        if (($verificacion -join " ") -match [regex]::Escape($Paquete)) {
            Write-Output "FALLA: el paquete sigue apareciendo instalado."
            exit 1
        }
        Write-Output "verificado: '$Paquete' ya no aparece instalado."
        exit 0
    }

    "actualizar" {
        if ($Todo) {
            Write-Output "== Actualizando todos los paquetes =="
            Write-Output "  Puede tardar mucho y descargar bastante: conviene en ventana"
            Write-Output "  de mantenimiento, no en horario de trabajo."
            $salida = & $winget upgrade --all --silent --accept-package-agreements `
                @comunes 2>&1
        }
        else {
            if (-not $Paquete) {
                Write-Output "El modo 'actualizar' exige -Paquete, o el modificador -Todo."
                exit 1
            }
            Write-Output "== Actualizando '$Paquete' =="
            $salida = & $winget upgrade --id $Paquete --exact --silent `
                --accept-package-agreements @comunes 2>&1
        }

        foreach ($linea in $salida) { Write-Output $linea }
        $codigo = $LASTEXITCODE

        Write-Output ""
        if ($codigo -eq 0) {
            Write-Output "Actualización completada."
            exit 0
        }
        if ($codigo -eq -1978335189) {
            Write-Output "No había nada que actualizar."
            exit 0
        }
        Write-Output "La actualización terminó con código $codigo."
        Write-Output "Con --all es habitual: un paquete que falla no detiene al resto,"
        Write-Output "pero el código refleja que hubo al menos uno con problema."
        exit 1
    }
}
