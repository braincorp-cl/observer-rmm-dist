<#
.SYNOPSIS
    Salud de los Espacios de almacenamiento (Storage Pools) y sus discos virtuales.

.DESCRIPTION
    Solo LEE. En un servidor con Espacios de almacenamiento, la pérdida de un disco
    del grupo no apaga nada: el volumen sigue funcionando degradado y nadie se entera
    hasta que cae el segundo y se pierde el arreglo. Este script existe para que ese
    primer disco no pase inadvertido.

    Recorre los tres niveles, porque un problema puede verse en uno y no en los otros:
    el grupo, los discos virtuales que viven en él y los discos físicos que lo forman.

    Ignora el grupo "Primordial", que es el contenedor de los discos disponibles y
    aparece siempre: no es un arreglo y su estado no significa nada.

    Sale con 1 si algo no está sano.

.EXAMPLE
    almacenamiento-storage-pools.ps1
#>

[CmdletBinding()]
param()

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

if (-not (Get-Command Get-StoragePool -ErrorAction SilentlyContinue)) {
    Write-Output "Este equipo no tiene el módulo de almacenamiento de Windows."
    exit 1
}

$problemas = New-Object System.Collections.ArrayList

try {
    $grupos = @(Get-StoragePool -ErrorAction Stop |
        Where-Object { $_.FriendlyName -ne "Primordial" })
}
catch {
    Write-Output "No se pudieron consultar los grupos de almacenamiento: $($_.Exception.Message)"
    exit 1
}

if ($grupos.Count -eq 0) {
    Write-Output "Este equipo no tiene Espacios de almacenamiento configurados."
    Write-Output "No es un problema: es la configuración normal de un equipo sin arreglos."
    exit 0
}

foreach ($grupo in $grupos) {
    Write-Output ""
    Write-Output "== Grupo: $($grupo.FriendlyName) =="
    Write-Output "  salud:            $($grupo.HealthStatus)"
    Write-Output "  estado:           $($grupo.OperationalStatus)"
    Write-Output "  tamaño:           $([Math]::Round($grupo.Size / 1GB, 1)) GB"
    Write-Output "  asignado:         $([Math]::Round(($grupo.Size - $grupo.AllocatedSize) / 1GB, 1)) GB sin asignar"
    Write-Output "  solo lectura:     $($grupo.IsReadOnly)"

    if ($grupo.HealthStatus -ne "Healthy") {
        [void]$problemas.Add("grupo '$($grupo.FriendlyName)' con salud $($grupo.HealthStatus)")
    }
    if ($grupo.IsReadOnly) {
        [void]$problemas.Add("grupo '$($grupo.FriendlyName)' en solo lectura")
    }

    Write-Output ""
    Write-Output "  -- Discos virtuales --"
    try {
        $virtuales = @(Get-VirtualDisk -StoragePool $grupo -ErrorAction Stop)
        if ($virtuales.Count -eq 0) {
            Write-Output "    (ninguno)"
        }
        foreach ($virtual in $virtuales) {
            Write-Output ""
            Write-Output "    $($virtual.FriendlyName)"
            Write-Output "      resiliencia:    $($virtual.ResiliencySettingName)"
            Write-Output "      salud:          $($virtual.HealthStatus)"
            Write-Output "      estado:         $($virtual.OperationalStatus)"
            Write-Output "      tamaño:         $([Math]::Round($virtual.Size / 1GB, 1)) GB"
            Write-Output "      aprovisionam.:  $($virtual.ProvisioningType)"

            if ($null -ne $virtual.NumberOfColumns) {
                Write-Output "      columnas:       $($virtual.NumberOfColumns)"
            }

            if ($virtual.HealthStatus -ne "Healthy") {
                [void]$problemas.Add("disco virtual '$($virtual.FriendlyName)' con salud $($virtual.HealthStatus)")
            }

            # Un disco virtual "Degraded" sigue sirviendo datos: es exactamente el
            # estado que pasa inadvertido y el que hay que atender antes del segundo fallo.
            if ($virtual.OperationalStatus -match "Degraded|Incomplete") {
                [void]$problemas.Add("disco virtual '$($virtual.FriendlyName)' en estado $($virtual.OperationalStatus): sirve datos sin redundancia completa")
            }
        }
    }
    catch {
        Write-Output "    No se pudieron consultar los discos virtuales: $($_.Exception.Message)"
    }

    Write-Output ""
    Write-Output "  -- Discos físicos del grupo --"
    try {
        $fisicos = @(Get-PhysicalDisk -StoragePool $grupo -ErrorAction Stop)
        foreach ($fisico in ($fisicos | Sort-Object DeviceId)) {
            Write-Output ""
            Write-Output "    $($fisico.FriendlyName)"
            Write-Output "      salud:          $($fisico.HealthStatus)"
            Write-Output "      estado:         $($fisico.OperationalStatus)"
            Write-Output "      uso:            $($fisico.Usage)"
            Write-Output "      tamaño:         $([Math]::Round($fisico.Size / 1GB, 1)) GB"

            if ($fisico.HealthStatus -ne "Healthy") {
                [void]$problemas.Add("disco físico '$($fisico.FriendlyName)' con salud $($fisico.HealthStatus)")
            }
            if ($fisico.OperationalStatus -match "Lost Communication|Removed|Failed") {
                [void]$problemas.Add("disco físico '$($fisico.FriendlyName)' en estado $($fisico.OperationalStatus)")
            }
        }
    }
    catch {
        Write-Output "    No se pudieron consultar los discos físicos: $($_.Exception.Message)"
    }
}

# Los trabajos de reparación en curso explican un estado degradado transitorio: sin
# esto uno abre un ticket por algo que se está arreglando solo.
Write-Output ""
Write-Output "== Trabajos de almacenamiento en curso =="
try {
    $trabajos = @(Get-StorageJob -ErrorAction Stop)
    if ($trabajos.Count -eq 0) {
        Write-Output "  (ninguno)"
    }
    foreach ($trabajo in $trabajos) {
        Write-Output "  $($trabajo.Name): $($trabajo.JobState) — $($trabajo.PercentComplete)%"
    }
}
catch {
    Write-Output "  No se pudieron consultar los trabajos: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "== Resultado =="

if ($problemas.Count -eq 0) {
    Write-Output "  $($grupos.Count) grupo(s) de almacenamiento, todo sano."
    exit 0
}

Write-Output "  $($problemas.Count) problema(s):"
foreach ($problema in $problemas) {
    Write-Output "   - $problema"
}
exit 1
