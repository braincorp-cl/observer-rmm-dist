<#
.SYNOPSIS
    Fuerza la sincronización de replicación de AD y la del reloj con el dominio.

.DESCRIPTION
    Une los dos scripts del catálogo original (sincronizar AD y sincronizar la hora con
    el controlador) porque son la pareja que se corre junta cuando algo del dominio
    "no llega": un cambio de contraseña que no se propagó, una GPO que no se aplica, un
    usuario recién creado que no puede entrar.

    Se comporta distinto según el equipo, que es lo que el original no distinguía:

      * En un controlador de dominio fuerza la replicación entrante desde sus pares
        (repadmin /syncall) y muestra el estado de replicación. Ahí sí tiene sentido.
      * En un miembro no hay replicación que forzar: lo que se puede hacer es
        refrescar las directivas de grupo y volver a registrar el equipo en DNS, que es
        lo que en la práctica se busca. Forzar "sync de AD" en un miembro no hace nada
        y da la falsa sensación de haber actuado.

    La hora se sincroniza en los dos casos, porque un desfase mayor a cinco minutos
    rompe Kerberos y el síntoma nunca menciona el reloj.

.PARAMETER Modo
    estado (por defecto), sincronizar.

.PARAMETER SoloHora
    Sincroniza únicamente el reloj.

.EXAMPLE
    ad-sincronizar.ps1
    ad-sincronizar.ps1 -Modo sincronizar
    ad-sincronizar.ps1 -Modo sincronizar -SoloHora
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "sincronizar")]
    [string]$Modo = "estado",

    [switch]$SoloHora
)

$ErrorActionPreference = "Continue"

# DomainRole de Win32_ComputerSystem: 4 y 5 son controladores de dominio (respaldo y
# principal), 1 y 3 son miembros, 0 y 2 son equipos en grupo de trabajo.
$ROLES = @{
    0 = "estación en grupo de trabajo"
    1 = "estación miembro de dominio"
    2 = "servidor en grupo de trabajo"
    3 = "servidor miembro de dominio"
    4 = "controlador de dominio de respaldo"
    5 = "controlador de dominio principal"
}

$rol = -1
$dominio = ""
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    $rol = [int]$sistema.DomainRole
    $dominio = $sistema.Domain
}
catch {
    Write-Output "No se pudo leer la información del sistema: $($_.Exception.Message)"
    exit 1
}

$esControlador = ($rol -eq 4 -or $rol -eq 5)
$esMiembro = ($rol -eq 1 -or $rol -eq 3)

Write-Output "== Equipo =="
Write-Output "  nombre:  $env:COMPUTERNAME"
Write-Output "  dominio: $dominio"
Write-Output "  rol:     $(if ($ROLES.ContainsKey($rol)) { $ROLES[$rol] } else { "desconocido ($rol)" })"

if (-not $esControlador -and -not $esMiembro) {
    Write-Output ""
    Write-Output "El equipo no pertenece a un dominio: no hay nada que sincronizar."
    exit 0
}

Write-Output ""
Write-Output "== Estado del reloj =="
try {
    $estadoHora = & w32tm /query /status 2>&1
    if ($LASTEXITCODE -eq 0) {
        foreach ($linea in $estadoHora) {
            if ($linea -and $linea.Trim()) { Write-Output "  $($linea.Trim())" }
        }
    }
    else {
        Write-Output "  w32tm /query /status devolvió $LASTEXITCODE"
    }
}
catch {
    Write-Output "  no se pudo consultar el estado del servicio de hora."
}

if ($esControlador -and -not $SoloHora) {
    Write-Output ""
    Write-Output "== Estado de replicación =="
    try {
        $replicacion = & repadmin /showrepl /csv 2>&1
        if ($LASTEXITCODE -eq 0 -and $replicacion) {
            $fallas = 0
            foreach ($linea in $replicacion) {
                # La columna de fallos consecutivos es la que importa: un valor > 0
                # significa que ese enlace de replicación está roto ahora mismo.
                if ($linea -match '^"[^"]*","([^"]+)","([^"]+)"' -and $linea -notmatch "showrepl_COLUMNS") {
                    $campos = $linea -split '","'
                    if ($campos.Count -ge 10) {
                        $fallosConsecutivos = $campos[9] -replace '"', ''
                        if ($fallosConsecutivos -match '^\d+$' -and [int]$fallosConsecutivos -gt 0) {
                            Write-Output "  FALLA: $($campos[2]) -> $($campos[3]) con $fallosConsecutivos fallo(s)"
                            $fallas++
                        }
                    }
                }
            }
            if ($fallas -eq 0) {
                Write-Output "  Sin enlaces de replicación en falla."
            }
        }
        else {
            Write-Output "  repadmin no disponible o devolvió $LASTEXITCODE"
            Write-Output "  (repadmin viene con las herramientas de administración de AD)"
        }
    }
    catch {
        Write-Output "  no se pudo consultar la replicación: $($_.Exception.Message)"
    }
}

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se sincronizó nada."
    exit 0
}

$errores = 0

Write-Output ""
Write-Output "== Sincronizando el reloj =="
# /resync fuerza la sincronización inmediata; /rediscover hace que además vuelva a
# buscar su fuente de tiempo, que es lo que hace falta si el controlador cambió.
$salida = & w32tm /resync /rediscover 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Output "  w32tm /resync: OK"
    foreach ($linea in $salida) {
        if ($linea -and $linea.Trim()) { Write-Output "  $($linea.Trim())" }
    }
}
else {
    Write-Output "  w32tm /resync devolvió $LASTEXITCODE"
    Write-Output "  $($salida -join ' ')"
    Write-Output "  Si el servicio de hora está detenido, arrancalo antes (w32time)."
    $errores++
}

if ($SoloHora) {
    Write-Output ""
    Write-Output "Modo -SoloHora: no se tocó nada más."
    if ($errores -gt 0) { exit 1 }
    exit 0
}

if ($esControlador) {
    Write-Output ""
    Write-Output "== Forzando replicación entrante =="
    # /e incluye todos los sitios, /A todas las particiones, /P empuja también hacia
    # afuera. Sin /e solo replica dentro del sitio local.
    $salida = & repadmin /syncall /e /A /P 2>&1
    $codigo = $LASTEXITCODE
    foreach ($linea in $salida) {
        if ($linea -and $linea.Trim()) { Write-Output "  $($linea.Trim())" }
    }
    if ($codigo -ne 0) {
        Write-Output "  repadmin /syncall devolvió $codigo"
        $errores++
    }
}
else {
    Write-Output ""
    Write-Output "== Refrescando directivas de grupo y registro DNS =="
    Write-Output "  (este equipo es miembro: no tiene replicación de AD que forzar)"

    $salida = & gpupdate /force /target:computer 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  gpupdate: OK"
    }
    else {
        Write-Output "  gpupdate devolvió $LASTEXITCODE"
        $errores++
    }

    # Volver a registrar en DNS resuelve el caso del equipo que cambió de IP y al que
    # nadie encuentra por nombre.
    $salida = & ipconfig /registerdns 2>&1
    Write-Output "  ipconfig /registerdns: lanzado (se completa en segundo plano)"

    try {
        $confianza = Test-ComputerSecureChannel -ErrorAction Stop
        Write-Output "  relación de confianza: $(if ($confianza) { 'sana' } else { 'ROTA' })"
        if (-not $confianza) {
            Write-Output "  La confianza con el dominio está rota: ninguna sincronización"
            Write-Output "  la arregla. Hay que repararla con credenciales de dominio."
            $errores++
        }
    }
    catch {
        Write-Output "  no se pudo verificar la relación de confianza."
    }
}

Write-Output ""
Write-Output "== Resultado =="
if ($errores -gt 0) {
    Write-Output "  Terminó con $errores problema(s)."
    exit 1
}
Write-Output "  Sincronización completada."
exit 0
