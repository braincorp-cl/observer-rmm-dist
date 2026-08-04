<#
.SYNOPSIS
    Habilita o consulta caracteristicas opcionales de Windows (.NET 3.5, OpenSSH, RDP).

.DESCRIPTION
    Reemplaza los tres scripts separados del catalogo original por uno con un catalogo
    de caracteristicas conocidas, para no tener que recordar el nombre interno exacto
    de cada una ni la API que le corresponde.

    Las tres no se activan igual, y ahi esta el valor de tenerlas juntas:

      dotnet35  - es una caracteristica de imagen (DISM). En Windows cliente suele
                  necesitar el origen de instalacion o salida a Windows Update: no esta
                  en el disco. El script lo dice en vez de fallar con un codigo.
      openssh   - es una capacidad (Windows Capability), no una caracteristica. Se
                  instala y ademas hay que habilitar y arrancar su servicio, que es el
                  paso que se olvida y deja "instalado pero sin escuchar".
      rdp       - no se instala: se habilita con dos ajustes de registro mas una regla
                  de firewall. Sin la regla, RDP queda escuchando y bloqueado.

.PARAMETER Caracteristica
    dotnet35, openssh, rdp.

.PARAMETER Modo
    estado (por defecto) o habilitar.

.EXAMPLE
    windows-caracteristica.ps1 -Caracteristica rdp
    windows-caracteristica.ps1 -Caracteristica openssh -Modo habilitar
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dotnet35", "openssh", "rdp")]
    [string]$Caracteristica,

    [ValidateSet("estado", "habilitar")]
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

# El estado "en ejecucion" como valor del enum de .NET y no como la cadena "Running":
# el enum no se traduce, el texto que Windows muestra si. Comparar contra el enum
# sigue valiendo si manana el objeto viene de Win32_Service en vez de Get-Service.
$EN_EJECUCION = [System.ServiceProcess.ServiceControllerStatus]::Running
$rutaTerminalServer = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
$rutaRdpTcp = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"

function Show-EstadoDotnet {
    try {
        $caracteristica = Get-WindowsOptionalFeature -Online -FeatureName "NetFx3" -ErrorAction Stop
        Write-Output "  NetFx3 (.NET 3.5): $($caracteristica.State)"
        return $caracteristica.State -eq "Enabled"
    }
    catch {
        Write-Output "  No se pudo consultar NetFx3: $($_.Exception.Message)"
        return $null
    }
}

function Show-EstadoOpenssh {
    $instalado = $false
    try {
        $capacidades = @(Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction Stop)
        foreach ($capacidad in $capacidades) {
            Write-Output "  $($capacidad.Name): $($capacidad.State)"
            if ($capacidad.State -eq "Installed") { $instalado = $true }
        }
        if ($capacidades.Count -eq 0) {
            Write-Output "  OpenSSH.Server no esta disponible como capacidad en esta version."
        }
    }
    catch {
        Write-Output "  No se pudo consultar la capacidad OpenSSH: $($_.Exception.Message)"
        return $null
    }

    try {
        $servicio = Get-Service -Name sshd -ErrorAction Stop
        Write-Output "  servicio sshd:      $($servicio.Status) / inicio $($servicio.StartType)"
        $escuchando = $false
        try {
            $conexiones = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction Stop)
            $escuchando = $conexiones.Count -gt 0
        }
        catch {
            Write-Verbose $_.Exception.Message
        }
        Write-Output "  escuchando en 22:   $escuchando"
        return ($instalado -and $servicio.Status -eq $EN_EJECUCION -and $escuchando)
    }
    catch {
        Write-Output "  servicio sshd:      no existe todavia"
        return $false
    }
}

function Show-EstadoRdp {
    $habilitado = $false
    try {
        $valor = (Get-ItemProperty -Path $rutaTerminalServer -Name fDenyTSConnections -ErrorAction Stop).fDenyTSConnections
        $habilitado = [int]$valor -eq 0
        Write-Output "  conexiones RDP:     $(if ($habilitado) { 'permitidas' } else { 'DENEGADAS (fDenyTSConnections=1)' })"
    }
    catch {
        Write-Output "  no se pudo leer fDenyTSConnections: $($_.Exception.Message)"
        return $null
    }

    try {
        $nla = (Get-ItemProperty -Path $rutaRdpTcp -Name UserAuthentication -ErrorAction Stop).UserAuthentication
        Write-Output "  autenticacion NLA:  $(if ([int]$nla -eq 1) { 'exigida (recomendado)' } else { 'no exigida' })"
    }
    catch {
        Write-Verbose $_.Exception.Message
    }

    $reglasActivas = 0
    try {
        $reglas = @(Get-NetFirewallRule -Group "@FirewallAPI.dll,-28752" -ErrorAction Stop)
        $reglasActivas = @($reglas | Where-Object { $_.Enabled -eq "True" }).Count
        Write-Output "  reglas de firewall: $reglasActivas habilitada(s) de $($reglas.Count)"
    }
    catch {
        Write-Output "  reglas de firewall: no se pudieron consultar"
    }

    $escuchando = $false
    try {
        $conexiones = @(Get-NetTCPConnection -LocalPort 3389 -State Listen -ErrorAction Stop)
        $escuchando = $conexiones.Count -gt 0
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
    Write-Output "  escuchando en 3389: $escuchando"

    return ($habilitado -and $reglasActivas -gt 0 -and $escuchando)
}

Write-Output "== Estado de '$Caracteristica' =="
$estadoInicial = switch ($Caracteristica) {
    "dotnet35" { Show-EstadoDotnet }
    "openssh" { Show-EstadoOpenssh }
    "rdp" { Show-EstadoRdp }
}

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modifico nada."
    if ($estadoInicial -eq $true) { exit 0 }
    exit 1
}

if ($estadoInicial -eq $true) {
    Write-Output ""
    Write-Output "Nada que hacer: '$Caracteristica' ya esta habilitada y funcionando."
    exit 0
}

Write-Output ""
Write-Output "== Habilitando '$Caracteristica' =="
$errores = 0

switch ($Caracteristica) {
    "dotnet35" {
        try {
            # -All arrastra las caracteristicas padre; sin eso falla en equipos donde
            # NetFx3ServerFeatures no esta habilitado.
            $resultado = Enable-WindowsOptionalFeature -Online -FeatureName "NetFx3" -All `
                -NoRestart -ErrorAction Stop
            Write-Output "  DISM: OK"
            if ($resultado.RestartNeeded) {
                Write-Output "  PENDIENTE DE REINICIO."
            }
        }
        catch {
            Write-Output "  ERROR: $($_.Exception.Message)"
            Write-Output ""
            Write-Output "  La causa habitual es que los archivos de .NET 3.5 no estan en"
            Write-Output "  el disco: hay que dar el origen de instalacion (el ISO de"
            Write-Output "  Windows) o permitir la descarga desde Windows Update. Si el"
            Write-Output "  equipo apunta a un WSUS que no lo ofrece, tampoco lo baja."
            $errores++
        }
    }

    "openssh" {
        try {
            $capacidad = @(Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction Stop |
                Select-Object -First 1)
            if (-not $capacidad) {
                Write-Output "  ERROR: esta version de Windows no ofrece OpenSSH como capacidad."
                exit 1
            }
            if ($capacidad.State -ne "Installed") {
                Add-WindowsCapability -Online -Name $capacidad.Name -ErrorAction Stop | Out-Null
                Write-Output "  capacidad instalada: $($capacidad.Name)"
            }
            else {
                Write-Output "  la capacidad ya estaba instalada."
            }
        }
        catch {
            Write-Output "  ERROR al instalar la capacidad: $($_.Exception.Message)"
            $errores++
        }

        # El paso que se olvida: instalar no arranca ni habilita el servicio.
        try {
            Set-Service -Name sshd -StartupType Automatic -ErrorAction Stop
            Start-Service -Name sshd -ErrorAction Stop
            Write-Output "  servicio sshd: automatico y arrancado."
        }
        catch {
            Write-Output "  ERROR con el servicio sshd: $($_.Exception.Message)"
            $errores++
        }

        try {
            $regla = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
            if (-not $regla) {
                New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" `
                    -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound `
                    -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction Stop | Out-Null
                Write-Output "  regla de firewall creada para el puerto 22."
            }
            elseif ($regla.Enabled -ne "True") {
                Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction Stop
                Write-Output "  regla de firewall habilitada."
            }
            else {
                Write-Output "  la regla de firewall ya estaba habilitada."
            }
        }
        catch {
            Write-Output "  ERROR con la regla de firewall: $($_.Exception.Message)"
            $errores++
        }
    }

    "rdp" {
        try {
            Set-ItemProperty -Path $rutaTerminalServer -Name fDenyTSConnections -Value 0 `
                -Type DWord -ErrorAction Stop
            Write-Output "  fDenyTSConnections = 0 : OK"
        }
        catch {
            Write-Output "  ERROR: $($_.Exception.Message)"
            $errores++
        }

        # NLA se deja exigida: es la diferencia entre un RDP expuesto y uno que pide
        # autenticacion antes de dibujar el escritorio.
        try {
            Set-ItemProperty -Path $rutaRdpTcp -Name UserAuthentication -Value 1 `
                -Type DWord -ErrorAction Stop
            Write-Output "  autenticacion NLA exigida : OK"
        }
        catch {
            Write-Output "  AVISO: no se pudo exigir NLA: $($_.Exception.Message)"
        }

        try {
            Enable-NetFirewallRule -Group "@FirewallAPI.dll,-28752" -ErrorAction Stop
            Write-Output "  reglas de firewall de RDP habilitadas."
        }
        catch {
            Write-Output "  ERROR con las reglas de firewall: $($_.Exception.Message)"
            $errores++
        }
    }
}

Write-Output ""
Write-Output "== Estado resultante =="
$estadoFinal = switch ($Caracteristica) {
    "dotnet35" { Show-EstadoDotnet }
    "openssh" { Show-EstadoOpenssh }
    "rdp" { Show-EstadoRdp }
}

Write-Output ""
Write-Output "== Resultado =="
if ($errores -gt 0) {
    Write-Output "  Termino con $errores error(es)."
    exit 1
}
if ($estadoFinal -eq $true) {
    Write-Output "  '$Caracteristica' habilitada y verificada."
    exit 0
}
Write-Output "  Se aplicaron los cambios pero la verificacion no dio positiva."
Write-Output "  En .NET 3.5 es normal si queda pendiente de reinicio."
exit 1
