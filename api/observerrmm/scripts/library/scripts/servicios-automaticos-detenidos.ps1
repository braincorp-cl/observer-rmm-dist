<#
.SYNOPSIS
    Encuentra servicios con inicio automático que están detenidos y los arranca.

.DESCRIPTION
    Un servicio configurado como automático que no está corriendo es, casi siempre, un
    síntoma: algo falló al arrancar y nadie lo notó porque el equipo funciona "casi
    bien". Este script los encuentra y opcionalmente los levanta.

    Filtra el ruido que hace inútil la versión ingenua de este chequeo:

      * Los de inicio "Automático (inicio retrasado)" que todavía están dentro de su
         ventana de arranque no cuentan como caídos.
      * Hay servicios de Windows que figuran como automáticos y terminan solos por
         diseño: se detienen cuando acaban su trabajo. Levantarlos es inútil y llena
         el reporte de falsos positivos.
      * Los servicios con dependencias caídas se informan aparte, porque arrancarlos
         directamente falla mientras la dependencia siga abajo.

    Por defecto solo INFORMA. Hay que pedir 'arrancar' para que actúe.

.PARAMETER Modo
    estado (por defecto) o arrancar.

.PARAMETER Excluir
    Nombres de servicio a ignorar, separados por coma.

.EXAMPLE
    servicios-automaticos-detenidos.ps1
    servicios-automaticos-detenidos.ps1 -Modo arrancar
    servicios-automaticos-detenidos.ps1 -Modo arrancar -Excluir "sppsvc,MapsBroker"
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "arrancar")]
    [string]$Modo = "estado",

    [string]$Excluir = ""
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

# Servicios que Windows marca como automáticos y que terminan por su cuenta cuando
# cumplen su tarea. Aparecen "detenidos" en estado normal y arrancarlos no arregla
# nada: solo generan ruido en el reporte.
$TERMINAN_SOLOS = @(
    "sppsvc",              # Protección de software: corre y termina
    "MapsBroker",          # Mapas descargados
    "dmwappushservice",    # Servicio de mensajería WAP
    "gpsvc",               # Cliente de directiva de grupo: gestionado por el sistema
    "TrustedInstaller",    # Instalador de módulos de Windows
    "RemoteRegistry",      # Deshabilitado por endurecimiento en muchos equipos
    "tiledatamodelsvc",
    "CDPUserSvc",
    "OneSyncSvc",
    "WpnUserService",
    "edgeupdate",
    "MicrosoftEdgeElevationService",
    "GoogleChromeElevationService",
    "gupdate"
)

$excluidos = @()
if ($Excluir) {
    $excluidos = $Excluir.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

# El tiempo desde el arranque decide si un servicio de inicio retrasado todavía está
# a tiempo: Windows los lanza hasta unos minutos después del arranque.
$minutosDesdeArranque = 999
try {
    $sistemaOperativo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $minutosDesdeArranque = ((Get-Date) - $sistemaOperativo.LastBootUpTime).TotalMinutes
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output "Minutos desde el arranque: $([int]$minutosDesdeArranque)"

try {
    # Win32_Service trae DelayedAutoStart, que Get-Service no expone y que hace falta
    # para no confundir "retrasado" con "caído".
    $servicios = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
        Where-Object { $_.StartMode -eq "Auto" -and $_.State -ne "Running" })
}
catch {
    Write-Output "No se pudieron consultar los servicios: $($_.Exception.Message)"
    exit 1
}

$candidatos = New-Object System.Collections.ArrayList
$omitidos = 0
$retrasados = 0

foreach ($servicio in ($servicios | Sort-Object Name)) {
    if ($excluidos -contains $servicio.Name) {
        $omitidos++
        continue
    }
    if ($TERMINAN_SOLOS -contains $servicio.Name) {
        $omitidos++
        continue
    }
    # Los servicios de usuario por sesión (sufijo _<id>) no se administran así.
    if ($servicio.Name -match "_[0-9a-f]{4,}$") {
        $omitidos++
        continue
    }
    if ($servicio.DelayedAutoStart -and $minutosDesdeArranque -lt 10) {
        $retrasados++
        continue
    }
    [void]$candidatos.Add($servicio)
}

Write-Output ""
Write-Output "== Servicios automáticos detenidos =="

if ($candidatos.Count -eq 0) {
    Write-Output "  Ninguno. ($omitidos omitido(s) por lista, $retrasados de inicio retrasado aún a tiempo)"
    Write-Output ""
    Write-Output "  Sin observaciones."
    exit 0
}

foreach ($servicio in $candidatos) {
    Write-Output ""
    Write-Output "  $($servicio.Name)"
    Write-Output "    nombre visible: $($servicio.DisplayName)"
    Write-Output "    estado:         $($servicio.State)"
    Write-Output "    inicio:         $($servicio.StartMode)$(if ($servicio.DelayedAutoStart) { ' (retrasado)' })"
    if ($servicio.ExitCode -and $servicio.ExitCode -ne 0) {
        Write-Output "    código salida:  $($servicio.ExitCode)"
    }

    # Las dependencias caídas explican por qué el servicio no arranca, y evitan el
    # intento inútil de levantarlo primero.
    try {
        $dependencias = @(Get-Service -Name $servicio.Name -ErrorAction Stop).ServicesDependedOn
        $caidas = @($dependencias | Where-Object { $_.Status -ne "Running" })
        if ($caidas.Count -gt 0) {
            Write-Output "    DEPENDENCIAS DETENIDAS: $(($caidas | ForEach-Object { $_.Name }) -join ', ')"
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}

Write-Output ""
Write-Output "  ($omitidos omitido(s) por lista, $retrasados de inicio retrasado aún a tiempo)"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "  $($candidatos.Count) servicio(s) automático(s) detenido(s)."
    Write-Output "  Modo 'estado': no se arrancó nada. Volvé a correr con -Modo arrancar."
    exit 1
}

Write-Output ""
Write-Output "== Arrancando =="

$arrancados = 0
$fallidos = 0

foreach ($servicio in $candidatos) {
    try {
        Start-Service -Name $servicio.Name -ErrorAction Stop

        # Verificación por efecto: Start-Service vuelve antes de que el servicio esté
        # realmente corriendo, así que se espera y se relee el estado.
        $limite = (Get-Date).AddSeconds(20)
        $estado = "Unknown"
        while ((Get-Date) -lt $limite) {
            $estado = (Get-Service -Name $servicio.Name -ErrorAction Stop).Status
            if ($estado -eq "Running") { break }
            Start-Sleep -Milliseconds 500
        }

        if ($estado -eq "Running") {
            Write-Output "  OK    $($servicio.Name)"
            $arrancados++
        }
        else {
            Write-Output "  FALLA $($servicio.Name) — quedó en estado $estado"
            $fallidos++
        }
    }
    catch {
        Write-Output "  ERROR $($servicio.Name) — $($_.Exception.Message)"
        $fallidos++
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $arrancados arrancado(s), $fallidos con falla."

if ($fallidos -gt 0) {
    Write-Output ""
    Write-Output "  Un servicio que no arranca a mano suele tener una causa concreta:"
    Write-Output "  dependencia caída, credenciales de la cuenta de servicio vencidas o"
    Write-Output "  binario faltante. Revisá el visor de eventos del equipo."
    exit 1
}
exit 0
