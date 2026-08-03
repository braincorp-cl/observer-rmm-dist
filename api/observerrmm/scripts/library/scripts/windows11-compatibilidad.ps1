<#
.SYNOPSIS
    Evalúa si el equipo cumple los requisitos de Windows 11, y opcionalmente bloquea la actualización.

.DESCRIPTION
    Une los dos scripts del catálogo original (verificar compatibilidad y bloquear la
    actualización) porque son las dos caras de la misma decisión: primero se mide, y
    según el resultado se decide si el equipo se actualiza o se congela.

    Revisa los requisitos que de verdad frenan la actualización: TPM 2.0, Arranque
    seguro, modo de particionado del disco de sistema (UEFI/GPT), memoria, espacio libre
    y familia del procesador. No pretende reemplazar a la herramienta oficial de
    Microsoft, que además consulta la lista de CPU soportadas: un equipo puede cumplir
    todo lo de acá y aun así quedar fuera por su modelo de procesador.

    El bloqueo se hace por versión objetivo (TargetReleaseVersion), que es el mecanismo
    soportado por Microsoft, y NO con los ajustes que solo posponen la actualización unos
    días. Es reversible.

.PARAMETER Modo
    verificar (por defecto), bloquear, desbloquear.

.PARAMETER VersionObjetivo
    Versión en la que congelar el equipo al bloquear. Por defecto "22H2".

.EXAMPLE
    windows11-compatibilidad.ps1
    windows11-compatibilidad.ps1 -Modo bloquear
    windows11-compatibilidad.ps1 -Modo desbloquear
#>

[CmdletBinding()]
param(
    [ValidateSet("verificar", "bloquear", "desbloquear")]
    [string]$Modo = "verificar",

    [string]$VersionObjetivo = "22H2"
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

$rutaPoliticaWu = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"

$incumplidos = New-Object System.Collections.ArrayList

Write-Output "== Sistema actual =="
$esWin11 = $false
try {
    $sistemaOperativo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    Write-Output "  edición: $($sistemaOperativo.Caption)"
    Write-Output "  versión: $($sistemaOperativo.Version) (build $($sistemaOperativo.BuildNumber))"
    # Windows 11 se distingue por el número de compilación, no por el nombre: su
    # Version sigue siendo 10.0.
    $esWin11 = [int]$sistemaOperativo.BuildNumber -ge 22000
    Write-Output "  ¿ya es Windows 11?: $esWin11"
}
catch {
    Write-Output "  no se pudo leer la información del sistema: $($_.Exception.Message)"
}

try {
    $release = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction Stop).DisplayVersion
    if ($release) { Write-Output "  release: $release" }
}
catch {
    Write-Verbose $_.Exception.Message
}

if (-not $esWin11) {
    Write-Output ""
    Write-Output "== Requisitos de Windows 11 =="

    # TPM: hace falta 2.0, presente y habilitado. Un TPM 1.2 no sirve.
    try {
        $tpm = Get-CimInstance -Namespace "root\CIMV2\Security\MicrosoftTpm" `
            -ClassName Win32_Tpm -ErrorAction Stop
        $version = ($tpm.SpecVersion -split ",")[0].Trim()
        Write-Output "  TPM:              versión $version, habilitado=$($tpm.IsEnabled_InitialValue), listo=$($tpm.IsActivated_InitialValue)"
        if ([double]$version -lt 2.0) {
            [void]$incumplidos.Add("TPM $version (se exige 2.0)")
        }
        elseif (-not $tpm.IsEnabled_InitialValue) {
            [void]$incumplidos.Add("TPM 2.0 presente pero DESHABILITADO en el firmware")
        }
    }
    catch {
        Write-Output "  TPM:              no detectado"
        [void]$incumplidos.Add("sin TPM detectable")
    }

    # Arranque seguro. Confirm-SecureBootUEFI lanza en equipos con BIOS heredado, y esa
    # excepción es en sí la respuesta: no hay UEFI.
    try {
        $arranqueSeguro = Confirm-SecureBootUEFI -ErrorAction Stop
        Write-Output "  Arranque seguro:  $arranqueSeguro"
        if (-not $arranqueSeguro) {
            [void]$incumplidos.Add("Arranque seguro deshabilitado")
        }
    }
    catch {
        Write-Output "  Arranque seguro:  no disponible (equipo en modo BIOS heredado)"
        [void]$incumplidos.Add("sin UEFI/Arranque seguro (BIOS heredado)")
    }

    # Estilo de partición del disco de sistema: GPT es requisito.
    try {
        $letraSistema = $env:SystemDrive -replace ":", ""
        $particion = Get-Partition -DriveLetter $letraSistema -ErrorAction Stop
        $disco = Get-Disk -Number $particion.DiskNumber -ErrorAction Stop
        Write-Output "  disco de sistema: estilo $($disco.PartitionStyle)"
        if ($disco.PartitionStyle -ne "GPT") {
            [void]$incumplidos.Add("disco de sistema en $($disco.PartitionStyle), se exige GPT")
        }
    }
    catch {
        Write-Output "  disco de sistema: no se pudo determinar el estilo de partición"
    }

    # Memoria: mínimo 4 GB.
    try {
        $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $gib = [Math]::Round($sistema.TotalPhysicalMemory / 1GB, 1)
        Write-Output "  memoria:          $gib GiB"
        if ($gib -lt 3.8) {
            [void]$incumplidos.Add("memoria de $gib GiB (se exigen 4)")
        }
    }
    catch {
        Write-Output "  memoria:          no se pudo determinar"
    }

    # Espacio libre: 64 GB de disco, y hacen falta unos 20 GB libres para actualizar.
    try {
        $volumen = Get-Volume -DriveLetter ($env:SystemDrive -replace ":", "") -ErrorAction Stop
        $totalGib = [Math]::Round($volumen.Size / 1GB, 1)
        $libreGib = [Math]::Round($volumen.SizeRemaining / 1GB, 1)
        Write-Output "  disco:            $totalGib GiB totales, $libreGib GiB libres"
        if ($totalGib -lt 62) {
            [void]$incumplidos.Add("disco de $totalGib GiB (se exigen 64)")
        }
        if ($libreGib -lt 20) {
            [void]$incumplidos.Add("solo $libreGib GiB libres (la actualización necesita ~20)")
        }
    }
    catch {
        Write-Output "  disco:            no se pudo determinar"
    }

    # Procesador: se informa modelo y núcleos. La lista oficial de CPU soportadas no se
    # replica acá a propósito: sería un dato externo que envejece y que Microsoft
    # actualiza por su cuenta.
    try {
        $procesador = Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop |
            Select-Object -First 1
        Write-Output "  procesador:       $($procesador.Name)"
        Write-Output "  núcleos/hilos:    $($procesador.NumberOfCores)/$($procesador.NumberOfLogicalProcessors)"
        Write-Output "  arquitectura:     $($procesador.AddressWidth) bits"
        if ($procesador.NumberOfCores -lt 2) {
            [void]$incumplidos.Add("procesador de $($procesador.NumberOfCores) núcleo(s), se exigen 2")
        }
        if ([int]$procesador.AddressWidth -lt 64) {
            [void]$incumplidos.Add("procesador de 32 bits")
        }
    }
    catch {
        Write-Output "  procesador:       no se pudo determinar"
    }
}

Write-Output ""
Write-Output "== Política de versión objetivo =="
$bloqueado = $false
try {
    if (Test-Path $rutaPoliticaWu) {
        $politica = Get-ItemProperty -Path $rutaPoliticaWu -ErrorAction Stop
        if ($politica.TargetReleaseVersion -eq 1 -and $politica.TargetReleaseVersionInfo) {
            $bloqueado = $true
            Write-Output "  congelado en: $($politica.TargetReleaseVersionInfo)"
            if ($politica.ProductVersion) {
                Write-Output "  producto:     $($politica.ProductVersion)"
            }
        }
        else {
            Write-Output "  sin versión objetivo fijada."
        }
    }
    else {
        Write-Output "  sin política de Windows Update configurada."
    }
}
catch {
    Write-Output "  no se pudo leer la política: $($_.Exception.Message)"
}

if ($Modo -eq "verificar") {
    Write-Output ""
    Write-Output "== Resultado =="
    if ($esWin11) {
        Write-Output "  El equipo ya corre Windows 11: no aplica la evaluación."
        exit 0
    }
    if ($incumplidos.Count -eq 0) {
        Write-Output "  COMPATIBLE con Windows 11 según los requisitos verificables acá."
        Write-Output "  Ojo: el modelo de procesador puede dejarlo fuera igual. La lista"
        Write-Output "  oficial la mantiene Microsoft y no se replica en este script."
        exit 0
    }
    Write-Output "  NO compatible. $($incumplidos.Count) requisito(s) sin cumplir:"
    foreach ($incumplido in $incumplidos) { Write-Output "   - $incumplido" }
    Write-Output ""
    Write-Output "  Varios se arreglan en el firmware (habilitar TPM, pasar a UEFI y"
    Write-Output "  Arranque seguro): no todos exigen recambiar el equipo."
    exit 1
}

if ($Modo -eq "desbloquear") {
    Write-Output ""
    Write-Output "== Quitando la versión objetivo =="
    if (-not $bloqueado) {
        Write-Output "  No había ninguna versión objetivo fijada: nada que hacer."
        exit 0
    }
    $errores = 0
    foreach ($valor in @("TargetReleaseVersion", "TargetReleaseVersionInfo", "ProductVersion")) {
        try {
            Remove-ItemProperty -Path $rutaPoliticaWu -Name $valor -ErrorAction Stop
            Write-Output "  quitado: $valor"
        }
        catch {
            # Que un valor no exista no es un error: puede no haberse fijado nunca.
            Write-Verbose "$valor : $($_.Exception.Message)"
        }
    }
    Write-Output ""
    Write-Output "== Resultado =="
    Write-Output "  Versión objetivo quitada. El equipo vuelve a poder actualizarse a la"
    Write-Output "  última versión disponible, incluida Windows 11 si es compatible."
    if ($errores -gt 0) { exit 1 }
    exit 0
}

Write-Output ""
Write-Output "== Fijando la versión objetivo en $VersionObjetivo =="

if (-not (Test-Path $rutaPoliticaWu)) {
    try {
        New-Item -Path $rutaPoliticaWu -Force -ErrorAction Stop | Out-Null
        Write-Output "  clave de política creada."
    }
    catch {
        Write-Output "  ERROR al crear la clave: $($_.Exception.Message)"
        exit 1
    }
}

$errores = 0
$ajustes = @{
    TargetReleaseVersion     = 1
    TargetReleaseVersionInfo = $VersionObjetivo
}

foreach ($clave in $ajustes.Keys) {
    try {
        $tipo = if ($ajustes[$clave] -is [int]) { "DWord" } else { "String" }
        Set-ItemProperty -Path $rutaPoliticaWu -Name $clave -Value $ajustes[$clave] `
            -Type $tipo -ErrorAction Stop
        Write-Output "  $clave = $($ajustes[$clave])"
    }
    catch {
        Write-Output "  ERROR con $clave : $($_.Exception.Message)"
        $errores++
    }
}

# Verificación por efecto.
try {
    $politica = Get-ItemProperty -Path $rutaPoliticaWu -ErrorAction Stop
    if ($politica.TargetReleaseVersion -ne 1 -or $politica.TargetReleaseVersionInfo -ne $VersionObjetivo) {
        Write-Output ""
        Write-Output "FALLA: la política no quedó como se pidió."
        exit 1
    }
    Write-Output "  verificado: congelado en $($politica.TargetReleaseVersionInfo)"
}
catch {
    Write-Output "  no se pudo verificar la política."
    $errores++
}

Write-Output ""
Write-Output "== Resultado =="
if ($errores -gt 0) {
    Write-Output "  Terminó con $errores error(es)."
    exit 1
}
Write-Output "  El equipo queda congelado en $VersionObjetivo y no se actualizará a"
Write-Output "  Windows 11 por su cuenta. Es reversible con -Modo desbloquear."
Write-Output ""
Write-Output "  AVISO: congelar una versión también frena las actualizaciones de"
Write-Output "  característica. Una versión que sale de soporte deja de recibir parches"
Write-Output "  de seguridad, así que esto tiene fecha de revisión."
exit 0
