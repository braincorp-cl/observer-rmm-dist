<#
.SYNOPSIS
    Encuentra servicios con inicio automatico que estan detenidos y los arranca.

.DESCRIPTION
    Un servicio configurado como automatico que no esta corriendo es, casi siempre, un
    sintoma: algo fallo al arrancar y nadie lo noto porque el equipo funciona "casi
    bien". Este script los encuentra y opcionalmente los levanta.

    Filtra el ruido que hace inutil la version ingenua de este chequeo:

      * Los de inicio "Automatico (inicio retrasado)" que todavia estan dentro de su
         ventana de arranque no cuentan como caidos.
      * Hay servicios de Windows que figuran como automaticos y terminan solos por
         diseno: se detienen cuando acaban su trabajo. Levantarlos es inutil y llena
         el reporte de falsos positivos.
      * Los servicios con dependencias caidas se informan aparte, porque arrancarlos
         directamente falla mientras la dependencia siga abajo.

    Por defecto solo INFORMA. Hay que pedir 'arrancar' para que actue.

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

# Servicios que Windows marca como automaticos y que terminan por su cuenta cuando
# cumplen su tarea. Aparecen "detenidos" en estado normal y arrancarlos no arregla
# nada: solo generan ruido en el reporte.
$TERMINAN_SOLOS = @(
    "sppsvc",              # Proteccion de software: corre y termina
    "MapsBroker",          # Mapas descargados
    "dmwappushservice",    # Servicio de mensajeria WAP
    "gpsvc",               # Cliente de directiva de grupo: gestionado por el sistema
    "TrustedInstaller",    # Instalador de modulos de Windows
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

# El modo de inicio de un servicio vive en el registro como un numero, y ese numero es
# el mismo en cualquier idioma de Windows: 2 = automatico, 3 = manual, 4 = deshabilitado.
# Es el dato que lee el propio panel de servicios antes de traducirlo para mostrarlo.
$RAIZ_SERVICIOS = "HKLM:\SYSTEM\CurrentControlSet\Services"
$INICIO_AUTOMATICO = 2

# El estado "en ejecucion" como valor del enum de .NET y no como la cadena que el panel
# de servicios muestra traducida. OJO con como se obtiene: escribir aca
# [System.ServiceProcess.ServiceControllerStatus]::Running falla con TypeNotFound, porque
# Windows PowerShell carga el assembly System.ServiceProcess de forma PEREZOSA -- recien
# cuando se usa Get-Service-- y en esta linea todavia no esta cargado. Se carga explicito.
# Sigue siendo invariante al idioma: los nombres del enum no se traducen.
Add-Type -AssemblyName System.ServiceProcess -ErrorAction SilentlyContinue
$EN_EJECUCION = [System.ServiceProcess.ServiceControllerStatus]::Running
if ($null -eq $EN_EJECUCION) {
    # Sin el enum, las comparaciones de estado darian siempre falso y el script reportaria
    # FALLA a servicios que si arrancaron. Mejor abortar que mentir.
    Write-Output "No se pudo resolver el enum de estado de servicios (System.ServiceProcess)."
    Write-Output "Sin ese dato las comprobaciones de estado no son confiables; no se continua."
    exit 1
}

function Test-InicioAutomatico {
    param([string]$Nombre)

    try {
        $clave = Get-ItemProperty -Path (Join-Path $RAIZ_SERVICIOS $Nombre) -ErrorAction Stop
        return ($clave.Start -eq $INICIO_AUTOMATICO)
    }
    catch {
        # Un servicio sin clave legible no se puede clasificar; se prefiere omitirlo
        # antes que reportarlo como caido sin fundamento.
        Write-Verbose $_.Exception.Message
        return $false
    }
}

$excluidos = @()
if ($Excluir) {
    $excluidos = $Excluir.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

# El tiempo desde el arranque decide si un servicio de inicio retrasado todavia esta
# a tiempo: Windows los lanza hasta unos minutos despues del arranque.
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
    # para no confundir "retrasado" con "caido".
    #
    # El filtro NO usa StartMode ni State: Windows traduce esas dos propiedades, asi
    # que en un equipo en espanol valen "Automatico" y "Detenido", y comparar contra
    # "Auto" o "Running" no encuentra nada. En su lugar se usan dos datos que ningun
    # idioma cambia:
    #   * Started, un booleano de la misma clase Win32_Service.
    #   * el modo de inicio leido del registro como numero (ver Test-InicioAutomatico).
    # State y StartMode se siguen mostrando en el reporte, ya traducidos, que es justo
    # donde conviene que esten en el idioma del equipo.
    $servicios = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
        Where-Object { -not $_.Started -and (Test-InicioAutomatico -Nombre $_.Name) })
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
    # Los servicios de usuario por sesion (sufijo _<id>) no se administran asi.
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
Write-Output "== Servicios automaticos detenidos =="

if ($candidatos.Count -eq 0) {
    Write-Output "  Ninguno. ($omitidos omitido(s) por lista, $retrasados de inicio retrasado aun a tiempo)"
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
        Write-Output "    codigo salida:  $($servicio.ExitCode)"
    }

    # Las dependencias caidas explican por que el servicio no arranca, y evitan el
    # intento inutil de levantarlo primero.
    try {
        $dependencias = @(Get-Service -Name $servicio.Name -ErrorAction Stop).ServicesDependedOn
        # Status de Get-Service es un enum de .NET, no texto traducido: comparar contra
        # el valor del enum vale igual en un Windows en espanol que en uno en ingles.
        $caidas = @($dependencias | Where-Object { $_.Status -ne $EN_EJECUCION })
        if ($caidas.Count -gt 0) {
            Write-Output "    DEPENDENCIAS DETENIDAS: $(($caidas | ForEach-Object { $_.Name }) -join ', ')"
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}

Write-Output ""
Write-Output "  ($omitidos omitido(s) por lista, $retrasados de inicio retrasado aun a tiempo)"

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "  $($candidatos.Count) servicio(s) automatico(s) detenido(s)."
    Write-Output "  Modo 'estado': no se arranco nada. Volve a correr con -Modo arrancar."
    exit 1
}

Write-Output ""
Write-Output "== Arrancando =="

$arrancados = 0
$fallidos = 0

foreach ($servicio in $candidatos) {
    try {
        Start-Service -Name $servicio.Name -ErrorAction Stop

        # Verificacion por efecto: Start-Service vuelve antes de que el servicio este
        # realmente corriendo, asi que se espera y se relee el estado.
        $limite = (Get-Date).AddSeconds(20)
        $estado = $null
        while ((Get-Date) -lt $limite) {
            $estado = (Get-Service -Name $servicio.Name -ErrorAction Stop).Status
            if ($estado -eq $EN_EJECUCION) { break }
            Start-Sleep -Milliseconds 500
        }

        if ($estado -eq $EN_EJECUCION) {
            Write-Output "  OK    $($servicio.Name)"
            $arrancados++
        }
        else {
            Write-Output "  FALLA $($servicio.Name) - quedo en estado $estado"
            $fallidos++
        }
    }
    catch {
        Write-Output "  ERROR $($servicio.Name) - $($_.Exception.Message)"
        $fallidos++
    }
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  $arrancados arrancado(s), $fallidos con falla."

if ($fallidos -gt 0) {
    Write-Output ""
    Write-Output "  Un servicio que no arranca a mano suele tener una causa concreta:"
    Write-Output "  dependencia caida, credenciales de la cuenta de servicio vencidas o"
    Write-Output "  binario faltante. Revisa el visor de eventos del equipo."
    exit 1
}
exit 0
