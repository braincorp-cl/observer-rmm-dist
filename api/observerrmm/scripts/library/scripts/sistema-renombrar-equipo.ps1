<#
.SYNOPSIS
    Renombra el equipo, validando el nombre y el escenario de dominio.

.DESCRIPTION
    El renombrado parece trivial y tiene tres formas conocidas de salir mal, que este
    script ataja antes de tocar nada:

      1. Nombre invalido. NetBIOS admite hasta 15 caracteres y no acepta puntos ni
         varios simbolos. Un nombre mas largo se trunca de forma silenciosa y el
         equipo queda con un nombre distinto al que se pidio.
      2. Equipo en dominio. Renombrar un miembro exige credenciales con permiso en el
         objeto de AD; sin ellas el cambio falla o rompe la relacion de confianza y el
         equipo deja de autenticar. Por eso, si esta en dominio, el script se niega
         salvo que se le pasen credenciales explicitas.
      3. Reinicio. El nombre no cambia de verdad hasta reiniciar, y hasta entonces el
         equipo reporta el viejo. El script NO reinicia por su cuenta.

    No renombra el registro del agente en la consola: eso lo hace el propio agente en
    su siguiente ciclo de inventario, una vez que el equipo arranco con el nombre nuevo.

.PARAMETER NuevoNombre
    Nombre nuevo. Obligatorio salvo en modo estado.

.PARAMETER Modo
    estado (por defecto) o aplicar.

.PARAMETER UsuarioDominio
    Usuario con permiso para renombrar en AD, por ejemplo "MIDOMINIO\admin".

.PARAMETER ContrasenaDominio
    Contrasena del usuario anterior.

.EXAMPLE
    sistema-renombrar-equipo.ps1
    sistema-renombrar-equipo.ps1 -Modo aplicar -NuevoNombre RECEPCION-01
#>

[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    "PSAvoidUsingConvertToSecureStringWithPlainText", "",
    Justification = "El renombrado en dominio exige un PSCredential y la contrasena llega como argumento del operador: no hay un origen seguro alternativo desde un script remoto."
)]
param(
    [ValidateSet("estado", "aplicar")]
    [string]$Modo = "estado",

    [string]$NuevoNombre,

    [string]$UsuarioDominio,

    [string]$ContrasenaDominio
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

$LARGO_MAXIMO_NETBIOS = 15

function Test-NombreValido {
    param([string]$Nombre)

    if (-not $Nombre) { return "el nombre esta vacio" }
    if ($Nombre.Length -gt $LARGO_MAXIMO_NETBIOS) {
        return "tiene $($Nombre.Length) caracteres y el maximo NetBIOS es $LARGO_MAXIMO_NETBIOS"
    }
    if ($Nombre -match "^\d+$") {
        return "no puede ser solo digitos"
    }
    # Caracteres prohibidos segun la documentacion de nombres NetBIOS, incluido el
    # punto, que Windows acepta al escribir pero rompe la resolucion.
    if ($Nombre -match '[\\/:*?"<>|.,~!@#$%^&()={}\[\]_\s]') {
        return "contiene caracteres no permitidos (solo letras, digitos y guion)"
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
    Write-Output "  no se pudo leer la informacion del sistema: $($_.Exception.Message)"
}

# Un renombrado pendiente de reinicio es invisible si solo se mira COMPUTERNAME, y es
# la causa de "ya lo renombre y sigue igual".
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
    Write-Output "Modo 'estado': no se modifico nada."
    if ($NuevoNombre) {
        $problema = Test-NombreValido $NuevoNombre
        Write-Output ""
        if ($problema) {
            Write-Output "  El nombre '$NuevoNombre' NO es valido: $problema"
            exit 1
        }
        Write-Output "  El nombre '$NuevoNombre' es valido y se podria aplicar."
    }
    exit 0
}

if (-not $NuevoNombre) {
    Write-Output ""
    Write-Output "El modo 'aplicar' exige el parametro -NuevoNombre."
    exit 1
}

$problema = Test-NombreValido $NuevoNombre
if ($problema) {
    Write-Output ""
    Write-Output "ABORTADO: el nombre '$NuevoNombre' no es valido - $problema"
    exit 1
}

if ($NuevoNombre -ieq $env:COMPUTERNAME) {
    Write-Output ""
    Write-Output "Nada que hacer: el equipo ya se llama '$NuevoNombre'."
    exit 0
}

if ($unidoDominio -and -not $UsuarioDominio) {
    Write-Output ""
    Write-Output "ABORTADO: el equipo esta unido al dominio '$dominio'."
    Write-Output "Renombrarlo sin credenciales con permiso en AD puede romper la relacion"
    Write-Output "de confianza y dejar el equipo sin autenticar."
    Write-Output "Volve a correr pasando -UsuarioDominio y -ContrasenaDominio."
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
        Write-Output "  Se paso -UsuarioDominio sin -ContrasenaDominio."
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

# Verificacion por efecto: el nombre pendiente en el registro. COMPUTERNAME sigue
# devolviendo el viejo hasta el reinicio, asi que mirarlo daria un falso negativo.
try {
    $pendiente = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName" -Name ComputerName -ErrorAction Stop).ComputerName
    if ($pendiente -ine $NuevoNombre) {
        Write-Output ""
        Write-Output "FALLA: el nombre pendiente quedo como '$pendiente', no como '$NuevoNombre'."
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
Write-Output "  Este script no reinicia: usa el script de reinicio con una espera que"
Write-Output "  le de tiempo al usuario, o coordina una ventana."
Write-Output ""
Write-Output "  El registro en la consola se actualiza solo, cuando el agente informe"
Write-Output "  su inventario despues de arrancar con el nombre nuevo."
exit 0
