<#
.SYNOPSIS
    Gestiona el plan de energía: alto rendimiento, restablecer o evitar suspensión.

.DESCRIPTION
    Une los dos scripts de energía del catálogo original (activar alto rendimiento y
    restablecer el plan a sus valores por defecto) y agrega el caso que en un RMM
    importa más que el rendimiento: que el equipo NO se suspenda, porque un equipo
    suspendido aparece caído en la consola y no recibe ni tareas ni parches.

    Modos:
      estado        — informa el plan activo y sus tiempos. No toca nada.
      rendimiento   — activa el plan de alto rendimiento.
      sin-suspender — deja el plan activo tal cual pero pone en 0 (nunca) los tiempos
                      de suspensión, hibernación y apagado de disco, con corriente y
                      con batería. Es lo mínimo necesario para que el equipo siga
                      alcanzable, sin imponerle un plan que quizá el cliente eligió.
      restablecer   — devuelve el plan activo a los valores de fábrica.

    Se usa powercfg y no WMI porque es la única interfaz que cubre todas las versiones
    de Windows por igual, incluidas las ediciones donde el plan de alto rendimiento
    viene oculto.

.PARAMETER Modo
    estado (por defecto), rendimiento, sin-suspender, restablecer.

.EXAMPLE
    energia-perfil.ps1
    energia-perfil.ps1 -Modo sin-suspender
    energia-perfil.ps1 -Modo rendimiento
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "rendimiento", "sin-suspender", "restablecer")]
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

# GUID fijo del plan "Alto rendimiento": es el mismo en todas las instalaciones de
# Windows, así que no depende del idioma del sistema como sí lo haría buscar el
# nombre del plan en la salida de powercfg.
$GUID_ALTO_RENDIMIENTO = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

function Get-PlanActivo {
    $salida = & powercfg /getactivescheme 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $salida) { return $null }
    # La salida es del tipo "GUID del plan de energía: <guid>  (<nombre>)".
    $encontrado = [regex]::Match($salida, "([0-9a-fA-F]{8}-[0-9a-fA-F-]{27})")
    if (-not $encontrado.Success) { return $null }
    $nombre = [regex]::Match($salida, "\(([^)]+)\)")
    return @{
        Guid   = $encontrado.Groups[1].Value
        Nombre = if ($nombre.Success) { $nombre.Groups[1].Value } else { "(sin nombre)" }
    }
}

function Show-Energia {
    param([string]$Titulo)

    Write-Output ""
    Write-Output "== $Titulo =="

    $plan = Get-PlanActivo
    if ($plan) {
        Write-Output "  plan activo: $($plan.Nombre)"
        Write-Output "  GUID:        $($plan.Guid)"
    }
    else {
        Write-Output "  no se pudo determinar el plan activo."
    }

    # Los tiempos salen de las consultas por subgrupo: SUB_SLEEP para suspensión e
    # hibernación, SUB_DISK para el apagado del disco.
    foreach ($par in @(
            @("SUB_SLEEP", "STANDBYIDLE", "suspensión"),
            @("SUB_SLEEP", "HIBERNATEIDLE", "hibernación"),
            @("SUB_DISK", "DISKIDLE", "apagado de disco"),
            @("SUB_VIDEO", "VIDEOIDLE", "apagado de pantalla")
        )) {
        $subgrupo = $par[0]
        $ajuste = $par[1]
        $etiqueta = $par[2]

        $salida = & powercfg /query SCHEME_CURRENT $subgrupo $ajuste 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $salida) { continue }

        $conCorriente = [regex]::Match(($salida -join "`n"), "(?im)^\s*Índice de configuración de CA:\s*0x([0-9a-f]+)|^\s*Current AC Power Setting Index:\s*0x([0-9a-f]+)")
        $conBateria = [regex]::Match(($salida -join "`n"), "(?im)^\s*Índice de configuración de CC:\s*0x([0-9a-f]+)|^\s*Current DC Power Setting Index:\s*0x([0-9a-f]+)")

        function Convert-Indice {
            param($Coincidencia)
            if (-not $Coincidencia.Success) { return "?" }
            $hex = if ($Coincidencia.Groups[1].Success) { $Coincidencia.Groups[1].Value } else { $Coincidencia.Groups[2].Value }
            $segundos = [Convert]::ToInt32($hex, 16)
            if ($segundos -eq 0) { return "nunca" }
            return "$([Math]::Round($segundos / 60)) min"
        }

        Write-Output "  $($etiqueta): corriente=$(Convert-Indice $conCorriente), batería=$(Convert-Indice $conBateria)"
    }
}

Show-Energia -Titulo "Estado actual"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    exit 0
}

$errores = 0

function Invoke-Powercfg {
    param([string[]]$Argumentos, [string]$Descripcion)
    $salida = & powercfg @Argumentos 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  OK    $Descripcion"
    }
    else {
        Write-Output "  ERROR $Descripcion (powercfg devolvió $LASTEXITCODE)"
        Write-Verbose ($salida -join "`n")
        $script:errores++
    }
}

Write-Output ""
switch ($Modo) {
    "rendimiento" {
        Write-Output "== Activando el plan de alto rendimiento =="
        $plan = Get-PlanActivo
        if ($plan -and $plan.Guid -ieq $GUID_ALTO_RENDIMIENTO) {
            Write-Output "  ya estaba activo: no se toca."
        }
        else {
            # En equipos donde el plan viene oculto, /setactive falla; duplicarlo
            # primero lo hace visible y devuelve un GUID usable.
            Invoke-Powercfg @("/setactive", $GUID_ALTO_RENDIMIENTO) "activar alto rendimiento"
            if ($errores -gt 0) {
                Write-Output "  reintentando: el plan puede venir oculto en esta edición."
                $errores = 0
                $duplicado = & powercfg /duplicatescheme $GUID_ALTO_RENDIMIENTO 2>&1
                $nuevoGuid = [regex]::Match(($duplicado -join " "), "([0-9a-fA-F]{8}-[0-9a-fA-F-]{27})")
                if ($nuevoGuid.Success) {
                    Invoke-Powercfg @("/setactive", $nuevoGuid.Groups[1].Value) "activar el plan duplicado"
                }
                else {
                    Write-Output "  ERROR no se pudo duplicar el plan."
                    $errores++
                }
            }
        }
    }

    "sin-suspender" {
        Write-Output "== Evitando que el equipo se suspenda =="
        Write-Output "  Se modifican los tiempos del plan ACTIVO, sin cambiar de plan."
        Invoke-Powercfg @("/change", "standby-timeout-ac", "0") "suspensión con corriente: nunca"
        Invoke-Powercfg @("/change", "standby-timeout-dc", "0") "suspensión con batería: nunca"
        Invoke-Powercfg @("/change", "hibernate-timeout-ac", "0") "hibernación con corriente: nunca"
        Invoke-Powercfg @("/change", "hibernate-timeout-dc", "0") "hibernación con batería: nunca"
        Invoke-Powercfg @("/change", "disk-timeout-ac", "0") "apagado de disco con corriente: nunca"
        Write-Output ""
        Write-Output "  La pantalla se sigue apagando: eso ahorra energía y no afecta"
        Write-Output "  la conectividad del agente, así que no se toca."
    }

    "restablecer" {
        Write-Output "== Restableciendo el plan activo a los valores de fábrica =="
        $plan = Get-PlanActivo
        if (-not $plan) {
            Write-Output "  No se pudo determinar el plan activo: no se hace nada."
            exit 1
        }
        Write-Output "  plan: $($plan.Nombre)"
        Invoke-Powercfg @("-restoredefaultschemes") "restaurar todos los planes por defecto"
        Write-Output ""
        Write-Output "  AVISO: -restoredefaultschemes restaura TODOS los planes y borra"
        Write-Output "  los personalizados. Si el cliente tenía un plan propio, se fue."
    }
}

Show-Energia -Titulo "Estado resultante"

Write-Output ""
if ($errores -gt 0) {
    Write-Output "Terminó con $errores error(es)."
    exit 1
}
Write-Output "Aplicado sin errores."
exit 0
