<#
.SYNOPSIS
    Estado de cifrado BitLocker y, opcionalmente, las claves de recuperación.

.DESCRIPTION
    Reemplaza los cuatro scripts separados del catálogo original (verificar unidad,
    crear reporte, recuperar reporte y obtener claves) por uno con modo. Solo LEE:
    no cifra, no descifra y no suspende la protección.

    Advertencia sobre el modo 'claves': imprime las claves de recuperación de
    BitLocker en la salida del script, que queda guardada en el historial de la
    consola y viaja por NATS. Es la única forma de recuperarlas de un equipo
    remoto, pero cualquiera con acceso a ese historial puede descifrar el disco.
    Usalo puntualmente y preferí guardarlas en el gestor de secretos, no dejarlas
    en el historial.

    En modo 'estado' sale con 1 si alguna unidad fija está sin cifrar, para que
    sirva como check de cumplimiento.

.PARAMETER Modo
    estado (por defecto), detalle, o claves.

.PARAMETER Unidad
    Limita el reporte a una unidad, por ejemplo "C:". Por defecto, todas.

.EXAMPLE
    bitlocker-estado.ps1
    bitlocker-estado.ps1 -Modo detalle
    bitlocker-estado.ps1 -Modo claves -Unidad C:
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "detalle", "claves")]
    [string]$Modo = "estado",

    [string]$Unidad
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue)) {
    Write-Output "BitLocker no está disponible en este equipo."
    Write-Output "Falta la característica, o es una edición de Windows que no lo incluye"
    Write-Output "(Home no trae BitLocker administrable)."
    exit 1
}

try {
    if ($Unidad) {
        $volumenes = @(Get-BitLockerVolume -MountPoint $Unidad -ErrorAction Stop)
    }
    else {
        $volumenes = @(Get-BitLockerVolume -ErrorAction Stop)
    }
}
catch {
    Write-Output "No se pudo consultar BitLocker: $($_.Exception.Message)"
    exit 1
}

if ($volumenes.Count -eq 0) {
    Write-Output "No se encontraron volúmenes administrables por BitLocker."
    exit 1
}

$sinCifrar = 0

foreach ($volumen in ($volumenes | Sort-Object MountPoint)) {
    Write-Output ""
    Write-Output "Unidad $($volumen.MountPoint)"
    Write-Output "  estado de protección:  $($volumen.ProtectionStatus)"
    Write-Output "  estado del volumen:    $($volumen.VolumeStatus)"
    Write-Output "  porcentaje cifrado:    $($volumen.EncryptionPercentage)%"
    Write-Output "  tipo de volumen:       $($volumen.VolumeType)"

    if ($Modo -ne "estado") {
        Write-Output "  método de cifrado:     $($volumen.EncryptionMethod)"
        Write-Output "  tamaño:                $([Math]::Round($volumen.CapacityGB, 2)) GB"
        Write-Output "  bloqueado:             $($volumen.LockStatus)"
        Write-Output "  auto-desbloqueo:       $($volumen.AutoUnlockEnabled)"

        $tipos = @($volumen.KeyProtector | ForEach-Object { $_.KeyProtectorType })
        if ($tipos.Count -gt 0) {
            Write-Output "  protectores de clave:  $($tipos -join ', ')"
        }
        else {
            Write-Output "  protectores de clave:  (ninguno)"
        }
    }

    if ($Modo -eq "claves") {
        $recuperacion = @($volumen.KeyProtector |
            Where-Object { $_.KeyProtectorType -eq "RecoveryPassword" })

        if ($recuperacion.Count -eq 0) {
            Write-Output "  claves de recuperación: (ninguna configurada en esta unidad)"
        }
        else {
            Write-Output "  claves de recuperación:"
            foreach ($clave in $recuperacion) {
                Write-Output "    id:    $($clave.KeyProtectorId)"
                Write-Output "    clave: $($clave.RecoveryPassword)"
            }
        }
    }

    # Solo las unidades fijas cuentan para el cumplimiento: una unidad extraíble sin
    # cifrar es lo normal y no debería disparar una alerta.
    if ($volumen.VolumeType -eq "OperatingSystem" -or $volumen.VolumeType -eq "FixedDataVolume") {
        if ($volumen.ProtectionStatus -ne "On") {
            $sinCifrar++
        }
    }
}

Write-Output ""
Write-Output "== Resultado =="

if ($Modo -eq "claves") {
    Write-Output "  Se imprimieron claves de recuperación: este resultado quedó"
    Write-Output "  guardado en el historial de la consola. Considerá borrarlo."
}

if ($sinCifrar -gt 0) {
    Write-Output "  $sinCifrar unidad(es) fija(s) SIN protección de BitLocker."
    exit 1
}

Write-Output "  Todas las unidades fijas están protegidas."
exit 0
