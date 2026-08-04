<#
.SYNOPSIS
    Estado de cifrado BitLocker y, opcionalmente, las claves de recuperacion.

.DESCRIPTION
    Reemplaza los cuatro scripts separados del catalogo original (verificar unidad,
    crear reporte, recuperar reporte y obtener claves) por uno con modo. Solo LEE:
    no cifra, no descifra y no suspende la proteccion.

    Advertencia sobre el modo 'claves': imprime las claves de recuperacion de
    BitLocker en la salida del script, que queda guardada en el historial de la
    consola y viaja por NATS. Es la unica forma de recuperarlas de un equipo
    remoto, pero cualquiera con acceso a ese historial puede descifrar el disco.
    Usalo puntualmente y preferi guardarlas en el gestor de secretos, no dejarlas
    en el historial.

    En modo 'estado' sale con 1 si alguna unidad fija esta sin cifrar, para que
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

$ErrorActionPreference = "Stop"

if (-not (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue)) {
    Write-Output "BitLocker no esta disponible en este equipo."
    Write-Output "Falta la caracteristica, o es una edicion de Windows que no lo incluye"
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
    Write-Output "No se encontraron volumenes administrables por BitLocker."
    exit 1
}

$sinCifrar = 0

foreach ($volumen in ($volumenes | Sort-Object MountPoint)) {
    Write-Output ""
    Write-Output "Unidad $($volumen.MountPoint)"
    Write-Output "  estado de proteccion:  $($volumen.ProtectionStatus)"
    Write-Output "  estado del volumen:    $($volumen.VolumeStatus)"
    Write-Output "  porcentaje cifrado:    $($volumen.EncryptionPercentage)%"
    Write-Output "  tipo de volumen:       $($volumen.VolumeType)"

    if ($Modo -ne "estado") {
        Write-Output "  metodo de cifrado:     $($volumen.EncryptionMethod)"
        Write-Output "  tamano:                $([Math]::Round($volumen.CapacityGB, 2)) GB"
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
            Write-Output "  claves de recuperacion: (ninguna configurada en esta unidad)"
        }
        else {
            Write-Output "  claves de recuperacion:"
            foreach ($clave in $recuperacion) {
                Write-Output "    id:    $($clave.KeyProtectorId)"
                Write-Output "    clave: $($clave.RecoveryPassword)"
            }
        }
    }

    # Solo las unidades fijas cuentan para el cumplimiento: una unidad extraible sin
    # cifrar es lo normal y no deberia disparar una alerta.
    if ($volumen.VolumeType -eq "OperatingSystem" -or $volumen.VolumeType -eq "FixedDataVolume") {
        if ($volumen.ProtectionStatus -ne "On") {
            $sinCifrar++
        }
    }
}

Write-Output ""
Write-Output "== Resultado =="

if ($Modo -eq "claves") {
    Write-Output "  Se imprimieron claves de recuperacion: este resultado quedo"
    Write-Output "  guardado en el historial de la consola. Considera borrarlo."
}

if ($sinCifrar -gt 0) {
    Write-Output "  $sinCifrar unidad(es) fija(s) SIN proteccion de BitLocker."
    exit 1
}

Write-Output "  Todas las unidades fijas estan protegidas."
exit 0
