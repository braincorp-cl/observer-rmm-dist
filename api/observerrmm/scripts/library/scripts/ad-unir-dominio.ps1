<#
.SYNOPSIS
    Une el equipo a un dominio de Active Directory.

.DESCRIPTION
    Une el equipo al dominio, comprobando antes las condiciones que hacen fallar la
    operacion y que dejan el equipo en un estado peor que el inicial:

      1. Resolucion DNS del dominio. Es la causa numero uno de fallo: si el equipo no
         resuelve el dominio ni encuentra sus controladores por SRV, la union falla.
         El script lo verifica y lo dice, en vez de devolver un error generico.
      2. Alcanzabilidad de un controlador. Resolver no es alcanzar.
      3. Nombre del equipo. Un nombre invalido o duplicado en el dominio hace fallar la
         union a mitad de camino.
      4. Estado previo. Si ya esta unido a ESE dominio no hace nada; si esta unido a
         OTRO, se niega, porque migrar entre dominios no es unir dos veces.

    ADVERTENCIA: la contrasena de la cuenta con permiso de union se pasa como argumento
    y queda escrita en el historial de la consola. Conviene una cuenta delegada solo
    para unir equipos, no una de administrador de dominio, y rotarla despues.

    No reinicia por su cuenta, aunque la union lo exija para completarse.

.PARAMETER Dominio
    FQDN del dominio, por ejemplo "empresa.local".

.PARAMETER Usuario
    Cuenta con permiso para unir equipos, por ejemplo "EMPRESA\unir-equipos".

.PARAMETER Contrasena
    Contrasena de esa cuenta.

.PARAMETER Modo
    verificar (por defecto, solo comprueba) o unir.

.PARAMETER UnidadOrganizativa
    DN de la OU destino, por ejemplo "OU=Equipos,DC=empresa,DC=local".

.EXAMPLE
    ad-unir-dominio.ps1 -Dominio empresa.local
    ad-unir-dominio.ps1 -Modo unir -Dominio empresa.local -Usuario "EMPRESA\unir" -Contrasena "..."
#>

[CmdletBinding()]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    "PSAvoidUsingConvertToSecureStringWithPlainText", "",
    Justification = "Add-Computer exige un PSCredential y la contrasena llega como argumento del operador: no hay origen seguro alternativo desde un script remoto."
)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Dominio,

    [ValidateSet("verificar", "unir")]
    [string]$Modo = "verificar",

    [string]$Usuario,

    [string]$Contrasena,

    [string]$UnidadOrganizativa
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

$problemas = New-Object System.Collections.ArrayList

Write-Output "== Estado actual =="
Write-Output "  equipo: $env:COMPUTERNAME"

$unidoDominio = $false
$dominioActual = ""
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    $unidoDominio = $sistema.PartOfDomain
    $dominioActual = $sistema.Domain
    Write-Output "  unido a dominio: $unidoDominio"
    Write-Output "  dominio/grupo:   $dominioActual"
}
catch {
    Write-Output "  no se pudo leer la informacion del sistema: $($_.Exception.Message)"
}

if ($unidoDominio) {
    if ($dominioActual -ieq $Dominio) {
        Write-Output ""
        Write-Output "Nada que hacer: el equipo ya esta unido a '$Dominio'."
        # Se verifica la relacion de confianza: estar "unido" no garantiza que
        # autentique, y una confianza rota se ve exactamente asi.
        try {
            $confianza = Test-ComputerSecureChannel -ErrorAction Stop
            Write-Output "  relacion de confianza: $(if ($confianza) { 'sana' } else { 'ROTA' })"
            if (-not $confianza) {
                Write-Output ""
                Write-Output "  La relacion de confianza esta rota. El equipo figura unido"
                Write-Output "  pero no autentica contra el dominio. Se repara con"
                Write-Output "  Test-ComputerSecureChannel -Repair y credenciales, que este"
                Write-Output "  script no hace por no tocar un equipo en produccion sin pedirlo."
                exit 1
            }
        }
        catch {
            Write-Output "  no se pudo verificar la relacion de confianza: $($_.Exception.Message)"
        }
        exit 0
    }

    Write-Output ""
    Write-Output "ABORTADO: el equipo ya esta unido al dominio '$dominioActual'."
    Write-Output "Pasarlo a '$Dominio' es una migracion, no una union: hay que sacarlo"
    Write-Output "del dominio actual primero y eso exige decisiones que este script no toma."
    exit 1
}

Write-Output ""
Write-Output "== Comprobaciones previas =="

# 1) Resolucion del dominio.
$direcciones = @()
try {
    $direcciones = @([System.Net.Dns]::GetHostAddresses($Dominio) |
        Where-Object { $_.AddressFamily -eq "InterNetwork" } |
        ForEach-Object { $_.IPAddressToString })
    if ($direcciones.Count -gt 0) {
        Write-Output "  DNS del dominio:      OK ($($direcciones -join ', '))"
    }
    else {
        Write-Output "  DNS del dominio:      FALLA (resolvio sin direcciones IPv4)"
        [void]$problemas.Add("el dominio '$Dominio' no resuelve a ninguna IPv4")
    }
}
catch {
    Write-Output "  DNS del dominio:      FALLA (no resuelve '$Dominio')"
    Write-Output "    Es la causa mas frecuente. El equipo tiene que usar el DNS del"
    Write-Output "    dominio, no un resolutor publico: los registros SRV que localizan"
    Write-Output "    los controladores solo existen en el DNS interno."
    [void]$problemas.Add("el dominio '$Dominio' no resuelve por DNS")
}

# 2) Registros SRV de los controladores: es lo que realmente usa la union.
try {
    $srv = @(Resolve-DnsName -Name "_ldap._tcp.dc._msdcs.$Dominio" -Type SRV -ErrorAction Stop)
    $controladores = @($srv | Where-Object { $_.NameTarget } | ForEach-Object { $_.NameTarget })
    if ($controladores.Count -gt 0) {
        Write-Output "  controladores (SRV):  OK ($($controladores.Count) encontrado[s])"
        foreach ($controlador in ($controladores | Select-Object -First 3)) {
            Write-Output "    - $controlador"
        }
    }
    else {
        Write-Output "  controladores (SRV):  FALLA (sin registros)"
        [void]$problemas.Add("no se encontraron registros SRV de controladores")
    }
}
catch {
    Write-Output "  controladores (SRV):  FALLA ($($_.Exception.Message))"
    [void]$problemas.Add("no se pudieron resolver los registros SRV del dominio")
}

# 3) Alcanzabilidad LDAP: resolver no es alcanzar.
if ($direcciones.Count -gt 0) {
    $alcanzable = $false
    foreach ($direccion in $direcciones) {
        try {
            $conexion = New-Object System.Net.Sockets.TcpClient
            $tarea = $conexion.ConnectAsync($direccion, 389)
            if ($tarea.Wait(3000) -and $conexion.Connected) {
                $alcanzable = $true
                Write-Output "  LDAP (TCP 389):       OK contra $direccion"
                $conexion.Close()
                break
            }
            $conexion.Close()
        }
        catch {
            Write-Verbose "$direccion : $($_.Exception.Message)"
        }
    }
    if (-not $alcanzable) {
        Write-Output "  LDAP (TCP 389):       FALLA (no se alcanzo ningun controlador)"
        [void]$problemas.Add("ningun controlador responde en el puerto LDAP 389")
    }
}

# 4) Nombre del equipo.
if ($env:COMPUTERNAME.Length -gt 15) {
    Write-Output "  nombre del equipo:    FALLA (mas de 15 caracteres)"
    [void]$problemas.Add("el nombre del equipo excede el largo NetBIOS de 15")
}
else {
    Write-Output "  nombre del equipo:    OK ($($env:COMPUTERNAME.Length) caracteres)"
}

# 5) Desfase de reloj: Kerberos rechaza mas de 5 minutos de diferencia, y el sintoma
# no menciona la hora en ningun momento.
if ($controladores -and $controladores.Count -gt 0) {
    try {
        $salida = & w32tm /stripchart /computer:$($controladores[0]) /samples:1 /dataonly 2>&1
        $desfase = ($salida | Select-String -Pattern "([+-]?\d+\.\d+)s" | Select-Object -First 1)
        if ($desfase) {
            Write-Output "  desfase de reloj:     $($desfase.Matches[0].Value) contra $($controladores[0])"
            $segundos = [Math]::Abs([double]($desfase.Matches[0].Groups[1].Value))
            if ($segundos -gt 300) {
                [void]$problemas.Add("desfase de reloj de $([int]$segundos)s: Kerberos rechaza mas de 300s")
            }
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}

Write-Output ""
if ($problemas.Count -gt 0) {
    Write-Output "== Resultado =="
    Write-Output "  $($problemas.Count) problema(s) que impedirian la union:"
    foreach ($problema in $problemas) { Write-Output "   - $problema" }
    exit 1
}

Write-Output "  Todas las comprobaciones previas pasaron."

if ($Modo -eq "verificar") {
    Write-Output ""
    Write-Output "Modo 'verificar': no se unio al dominio."
    Write-Output "Volve a correr con -Modo unir mas -Usuario y -Contrasena."
    exit 0
}

if (-not $Usuario -or -not $Contrasena) {
    Write-Output ""
    Write-Output "El modo 'unir' exige -Usuario y -Contrasena."
    exit 1
}

Write-Output ""
Write-Output "== Uniendo al dominio '$Dominio' =="
Write-Output "  cuenta: $Usuario"
if ($UnidadOrganizativa) {
    Write-Output "  OU:     $UnidadOrganizativa"
}

$segura = ConvertTo-SecureString $Contrasena -AsPlainText -Force
$credencial = New-Object System.Management.Automation.PSCredential($Usuario, $segura)

$argumentos = @{
    DomainName  = $Dominio
    Credential  = $credencial
    Force       = $true
    ErrorAction = "Stop"
}
if ($UnidadOrganizativa) { $argumentos["OUPath"] = $UnidadOrganizativa }

try {
    Add-Computer @argumentos
    Write-Output "  Add-Computer: OK"
}
catch {
    Write-Output "  ERROR: $($_.Exception.Message)"
    exit 1
}

# Verificacion por efecto: releer la pertenencia. Add-Computer no lanza en todos los
# escenarios de fallo parcial.
try {
    $sistema = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    if (-not $sistema.PartOfDomain -or $sistema.Domain -ine $Dominio) {
        Write-Output ""
        Write-Output "FALLA: tras la union el equipo reporta dominio '$($sistema.Domain)'."
        exit 1
    }
    Write-Output "  verificado: el equipo reporta dominio '$($sistema.Domain)'."
}
catch {
    Write-Output "  AVISO: no se pudo verificar la pertenencia tras la union."
}

Write-Output ""
Write-Output "== Resultado =="
Write-Output "  Union registrada. PENDIENTE DE REINICIO para completarse."
Write-Output "  Hasta reiniciar, las cuentas de dominio no pueden iniciar sesion."
Write-Output "  Este script no reinicia: coordina una ventana."
Write-Output ""
Write-Output "  Rota la contrasena de '$Usuario': quedo en el historial de la consola."
exit 0
