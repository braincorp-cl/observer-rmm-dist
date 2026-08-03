<#
.SYNOPSIS
    Renombra el equipo, validando el nombre y el escenario de dominio.

.DESCRIPTION
    El renombrado parece trivial y tiene tres formas conocidas de salir mal, que este
    script ataja antes de tocar nada:

      1. Nombre inválido. NetBIOS admite hasta 15 caracteres y no acepta puntos ni
         varios símbolos. Un nombre más largo se trunca de forma silenciosa y el
         equipo queda con un nombre distinto al que se pidió.
      2. Equipo en dominio. Renombrar un miembro exige credenciales con permiso en el
         objeto de AD; sin ellas el cambio falla o rompe la relación de confianza y el
         equipo deja de autenticar. Por eso, si está en dominio, el script se niega
         salvo que se le pasen credenciales explícitas.
      3. Reinicio. El nombre no cambia de verdad hasta reiniciar, y hasta entonces el
         equipo reporta el viejo. El script NO reinicia por su cuenta.

    No renombra el registro del agente en la consola: eso lo hace el propio agente en
    su siguiente ciclo de inventario, una vez que el equipo arrancó con el nombre nuevo.

.PARAMETER NuevoNombre
    Nombre nuevo. Obligatorio salvo en modo estado.

.PARAMETER Modo
    estado (por defecto) o aplicar.

.PARAMETER UsuarioDominio
    Usuario con permiso para renombrar en AD, por ejemplo "MIDOMINIO\admin".

.PARAMETER ContrasenaDominio
    Contraseña del usuario anterior.

.EXAMPLE
    sistema-renombrar-equipo.ps1
    sistema-renombrar-equipo.ps1 -Modo aplicar -NuevoNombre RECEPCION-01
#>

[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    "PSAvoidUsingConvertToSecureStringWithPlainText", "",
    Justification = "El renombrado en dominio exige un PSCredential y la contraseña llega como argumento del operador: no hay un origen seguro alternativo desde un script remoto."
)]
param(
    [ValidateSet("estado", "aplicar")]
    [string]$Modo = "estado",

    [string]$NuevoNombre,

    [string]$UsuarioDominio,

    [string]$ContrasenaDominio
)

$ErrorActionPreference = "Continue"

$LARGO_MAXIMO_NETBIOS = 15

function Test-NombreValido {
    param([string]$Nombre)

    if (-not $Nombre) { return "el nombre está vacío" }
    if ($Nombre.Length -gt $LARGO_MAXIMO_NETBIOS) {
        return "tiene $($Nombre.Length) caracteres y el máximo NetBIOS es $LARGO_MAXIMO_NETBIOS"
    }
    if ($Nombre -match "^\d+$") {
        return "no puede ser solo dígitos"
    }
    # Caracteres prohibidos según la documentación de nombres NetBIOS, incluido el
    # punto, que Windows acepta al escribir pero rompe la resolución.
    if ($Nombre -match '[\\/:*?"<>|.,~!@#$%^&()={}\[\]_\s]') {
        return "contiene caracteres no permitidos (solo letras, dígitos y guion)"
    }
    if ($Nombre.StartsWith("-") -or $Nombre.EndsWith("-")) {
        return "no puede empezar ni terminar con guion"
    }
    return $null
}

Write-Output "== Estado actual =="
Write-Output "  nombre actual: $env:COMPUTERNAME"

$unidoDominio = $false
$dominio = ""
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    $unidoDominio = $sistema.PartOfDomain
    $dominio = $sistema.Domain
    Write-Output "  unido a dominio: $unidoDominio"
    Write-Output "  dominio/grupo:   $dominio"
}
catch {
    Write-Output "  no se pudo leer la información del sistema: $($_.Exception.Message)"
}

# Un renombrado pendiente de reinicio es invisible si solo se mira COMPUTERNAME, y es
# la causa de "ya lo renombré y sigue igual".
try {
    $activo = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName" -Name ComputerName -ErrorAction Stop).ComputerName
    $pendiente = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName" -Name ComputerName -ErrorAction Stop).ComputerName
    if ($activo -ne $pendiente) {
        Write-Output ""
        Write-Output "  RENOMBRADO YA PENDIENTE:"
        Write-Output "    nombre activo:    $activo"
        Write-Output "    nombre pendiente: $pendiente"
        Write-Output "    Falta reiniciar para que tome efecto."
    }
}
catch {
    Write-Verbose $_.Exception.Message
}

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    if ($NuevoNombre) {
        $problema = Test-NombreValido $NuevoNombre
        Write-Output ""
        if ($problema) {
            Write-Output "  El nombre '$NuevoNombre' NO es válido: $problema"
            exit 1
        }
        Write-Output "  El nombre '$NuevoNombre' es válido y se podría aplicar."
    }
    exit 0
}

if (-not $NuevoNombre) {
    Write-Output ""
    Write-Output "El modo 'aplicar' exige el parámetro -NuevoNombre."
    exit 1
}

$problema = Test-NombreValido $NuevoNombre
if ($problema) {
    Write-Output ""
    Write-Output "ABORTADO: el nombre '$NuevoNombre' no es válido — $problema"
    exit 1
}

if ($NuevoNombre -ieq $env:COMPUTERNAME) {
    Write-Output ""
    Write-Output "Nada que hacer: el equipo ya se llama '$NuevoNombre'."
    exit 0
}

if ($unidoDominio -and -not $UsuarioDominio) {
    Write-Output ""
    Write-Output "ABORTADO: el equipo está unido al dominio '$dominio'."
    Write-Output "Renombrarlo sin credenciales con permiso en AD puede romper la relación"
    Write-Output "de confianza y dejar el equipo sin autenticar."
    Write-Output "Volvé a correr pasando -UsuarioDominio y -ContrasenaDominio."
    exit 1
}

Write-Output ""
Write-Output "== Renombrando: $env:COMPUTERNAME -> $NuevoNombre =="

$argumentos = @{
    NewName     = $NuevoNombre
    Force       = $true
    ErrorAction = "Stop"
}

if ($UsuarioDominio) {
    if (-not $ContrasenaDominio) {
        Write-Output "  Se pasó -UsuarioDominio sin -ContrasenaDominio."
        exit 1
    }
    $segura = ConvertTo-SecureString $ContrasenaDominio -AsPlainText -Force
    $argumentos["DomainCredential"] = New-Object System.Management.Automation.PSCredential($UsuarioDominio, $segura)
    Write-Output "  usando credenciales de dominio: $UsuarioDominio"
}

try {
    Rename-Computer @argumentos | Out-Null
    Write-Output "  Rename-Computer: OK"
}
catch {
    Write-Output "  ERROR: $($_.Exception.Message)"
    exit 1
}

# Verificación por efecto: el nombre pendiente en el registro. COMPUTERNAME sigue
# devolviendo el viejo hasta el reinicio, así que mirarlo daría un falso negativo.
try {
    $pendiente = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName" -Name ComputerName -ErrorAction Stop).ComputerName
    if ($pendiente -ine $NuevoNombre) {
        Write-Output ""
        Write-Output "FALLA: el nombre pendiente quedó como '$pendiente', no como '$NuevoNombre'."
        exit 1
    }
    Write-Output "  nombre pendiente verificado: $pendiente"
}
catch {
    Write-Output "  AVISO: no se pudo verificar el nombre pendiente en el registro."
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  Renombrado registrado. PENDIENTE DE REINICIO."
Write-Output "  Hasta que el equipo se reinicie sigue reportando '$env:COMPUTERNAME'."
Write-Output "  Este script no reinicia: usá el script de reinicio con una espera que"
Write-Output "  le dé tiempo al usuario, o coordiná una ventana."
Write-Output ""
Write-Output "  El registro en la consola se actualiza solo, cuando el agente informe"
Write-Output "  su inventario después de arrancar con el nombre nuevo."
exit 0
