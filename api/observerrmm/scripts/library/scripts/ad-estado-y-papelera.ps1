<#
.SYNOPSIS
    Estado de union a Entra ID y de la Papelera de reciclaje de Active Directory.

.DESCRIPTION
    Une los dos chequeos de estado de directorio del catalogo original, que estaban
    separados y son los dos que se consultan al hacerse cargo de un parque ajeno.

    Sobre Entra ID (ex Azure AD): distingue los tres estados que se confunden todo el
    tiempo y que significan cosas muy distintas -dispositivo unido a Entra, union
    hibrida, y registro de area de trabajo, que es solo del usuario y no implica
    ninguna administracion del equipo.

    Sobre la Papelera de AD: es una caracteristica del bosque que, una vez habilitada,
    NO se puede deshabilitar. Habilitada, un objeto borrado se puede restaurar entero
    durante el periodo de vida de la tumba; sin ella, restaurar un usuario borrado por
    error significa recuperar desde respaldo. Casi todo bosque deberia tenerla y muchos
    no la tienen porque nadie la habilito nunca.

    Con -HabilitarPapelera la habilita. Es una decision irreversible a nivel bosque, asi
    que el modo por defecto solo informa.

.PARAMETER HabilitarPapelera
    Habilita la Papelera de reciclaje de AD. IRREVERSIBLE.

.EXAMPLE
    ad-estado-y-papelera.ps1
    ad-estado-y-papelera.ps1 -HabilitarPapelera
#>

[CmdletBinding()]
param(
    [switch]$HabilitarPapelera
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

Write-Output "== Union a dominio y a Entra ID =="

$rol = -1
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    $rol = [int]$sistema.DomainRole
    Write-Output "  unido a dominio AD: $($sistema.PartOfDomain)"
    Write-Output "  dominio/grupo:      $($sistema.Domain)"
}
catch {
    Write-Output "  no se pudo leer la informacion del sistema: $($_.Exception.Message)"
}

$esControlador = ($rol -eq 4 -or $rol -eq 5)

# dsregcmd es la fuente autoritativa del estado de Entra ID. Se parsea su salida
# porque no hay API de PowerShell equivalente.
Write-Output ""
try {
    $dsreg = & dsregcmd /status 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $dsreg) {
        Write-Output "  dsregcmd no disponible: no se puede evaluar Entra ID."
    }
    else {
        $texto = $dsreg -join "`n"

        function Get-EstadoDsreg {
            param([string]$Clave)
            $coincidencia = [regex]::Match($texto, "(?im)^\s*$Clave\s*:\s*(\S+)")
            if ($coincidencia.Success) { return $coincidencia.Groups[1].Value }
            return "?"
        }

        $unidoEntra = Get-EstadoDsreg "AzureAdJoined"
        $registrado = Get-EstadoDsreg "WorkplaceJoined"
        $unidoDominioDsreg = Get-EstadoDsreg "DomainJoined"

        Write-Output "  AzureAdJoined:      $unidoEntra"
        Write-Output "  WorkplaceJoined:    $registrado"
        Write-Output "  DomainJoined:       $unidoDominioDsreg"

        Write-Output ""
        if ($unidoEntra -eq "YES" -and $unidoDominioDsreg -eq "YES") {
            Write-Output "  Interpretacion: union HIBRIDA (dominio local + Entra ID)."
            Write-Output "  El equipo se administra desde los dos lados."
        }
        elseif ($unidoEntra -eq "YES") {
            Write-Output "  Interpretacion: unido solo a Entra ID (sin dominio local)."
        }
        elseif ($registrado -eq "YES") {
            Write-Output "  Interpretacion: solo REGISTRO de area de trabajo. Es del"
            Write-Output "  usuario, no del dispositivo: el equipo NO esta administrado"
            Write-Output "  y no recibe directivas. Es el estado que mas se confunde con"
            Write-Output "  estar unido."
        }
        elseif ($unidoDominioDsreg -eq "YES") {
            Write-Output "  Interpretacion: unido solo al dominio local."
        }
        else {
            Write-Output "  Interpretacion: sin union a ningun directorio."
        }

        $inquilino = [regex]::Match($texto, "(?im)^\s*TenantName\s*:\s*(.+)$")
        if ($inquilino.Success) {
            Write-Output "  inquilino:          $($inquilino.Groups[1].Value.Trim())"
        }
    }
}
catch {
    Write-Output "  no se pudo ejecutar dsregcmd: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "== Papelera de reciclaje de Active Directory =="

if (-not $esControlador) {
    Write-Output "  Este equipo no es controlador de dominio."
    Write-Output "  La Papelera es una caracteristica del BOSQUE y se consulta desde un"
    Write-Output "  controlador: no hay nada que revisar aca."
    exit 0
}

if (-not (Get-Module -ListAvailable -Name ActiveDirectory)) {
    Write-Output "  Falta el modulo ActiveDirectory (herramientas de administracion de AD)."
    exit 1
}

try {
    Import-Module ActiveDirectory -ErrorAction Stop
}
catch {
    Write-Output "  No se pudo cargar el modulo ActiveDirectory: $($_.Exception.Message)"
    exit 1
}

$bosque = $null
try {
    $bosque = Get-ADForest -ErrorAction Stop
    Write-Output "  bosque:             $($bosque.Name)"
    Write-Output "  modo del bosque:    $($bosque.ForestMode)"
    Write-Output "  maestro de esquema: $($bosque.SchemaMaster)"
}
catch {
    Write-Output "  No se pudo consultar el bosque: $($_.Exception.Message)"
    exit 1
}

# La Papelera se representa como una caracteristica opcional del bosque: si tiene
# ambitos habilitados, esta activa.
$habilitada = $false
try {
    $caracteristica = Get-ADOptionalFeature -Filter 'Name -like "Recycle Bin Feature"' -ErrorAction Stop
    if ($caracteristica) {
        $habilitada = @($caracteristica.EnabledScopes).Count -gt 0
        Write-Output "  Papelera:           $(if ($habilitada) { 'HABILITADA' } else { 'no habilitada' })"
        if ($habilitada) {
            Write-Output "  ambitos:            $($caracteristica.EnabledScopes -join '; ')"
        }
    }
    else {
        Write-Output "  Papelera:           no se encontro la caracteristica"
    }
}
catch {
    Write-Output "  No se pudo consultar la caracteristica: $($_.Exception.Message)"
    exit 1
}

if ($habilitada) {
    Write-Output ""
    Write-Output "== Resultado =="
    Write-Output "  La Papelera de AD ya esta habilitada: nada que hacer."
    exit 0
}

Write-Output ""
Write-Output "  Sin la Papelera, restaurar un objeto borrado por error exige recuperar"
Write-Output "  desde respaldo, con la interrupcion que eso implica."

if (-not $HabilitarPapelera) {
    Write-Output ""
    Write-Output "== Resultado =="
    Write-Output "  La Papelera NO esta habilitada."
    Write-Output "  Para habilitarla, volve a correr con -HabilitarPapelera."
    Write-Output "  Tene en cuenta que es IRREVERSIBLE y afecta a todo el bosque."
    exit 1
}

# El modo del bosque tiene que ser al menos Windows2008R2Forest: por debajo, la
# caracteristica no existe y el cmdlet falla con un error poco claro.
if ($bosque.ForestMode -match "2000|2003|2008Forest$") {
    Write-Output ""
    Write-Output "ABORTADO: el modo del bosque es $($bosque.ForestMode)."
    Write-Output "La Papelera exige nivel funcional Windows Server 2008 R2 o superior."
    exit 1
}

Write-Output ""
Write-Output "== Habilitando la Papelera de reciclaje de AD =="
Write-Output "  Esto afecta a TODO el bosque '$($bosque.Name)' y NO se puede deshacer."

try {
    Enable-ADOptionalFeature -Identity "Recycle Bin Feature" `
        -Scope ForestOrConfigurationSet -Target $bosque.Name `
        -Confirm:$false -ErrorAction Stop
    Write-Output "  Enable-ADOptionalFeature: OK"
}
catch {
    Write-Output "  ERROR: $($_.Exception.Message)"
    exit 1
}

# Verificacion por efecto.
try {
    $caracteristica = Get-ADOptionalFeature -Filter 'Name -like "Recycle Bin Feature"' -ErrorAction Stop
    if (@($caracteristica.EnabledScopes).Count -gt 0) {
        Write-Output "  verificado: ambitos habilitados = $($caracteristica.EnabledScopes -join '; ')"
    }
    else {
        Write-Output "  FALLA: la caracteristica sigue sin ambitos habilitados."
        exit 1
    }
}
catch {
    Write-Output "  No se pudo verificar el resultado: $($_.Exception.Message)"
    exit 1
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  Papelera de reciclaje de AD habilitada."
Write-Output "  Protege los objetos borrados DESDE AHORA: los borrados antes no se"
Write-Output "  recuperan con esto. La replicacion al resto del bosque toma su tiempo."
exit 0
