# author: https://github.com/bradhawkins85
param([switch]$TlsPrepared)

$innosetup = 'innosetupchange'
$api = '"apichange"'
$clientid = 'clientchange'
$siteid = 'sitechange'
$agenttype = '"atypechange"'
$power = powerchange
$rdp = rdpchange
$ping = pingchange
$auth = '"tokenchange"'
$downloadlink = 'downloadchange'
$apilink = $downloadlink.split('/')

# ─── Compatibilidad con Windows 7 / Server 2008 R2 (PowerShell 2.0) ───────────
#
# Medido el 2026-08-06 en un Win7 SP1 real: de fábrica traen PowerShell 2.0 sobre
# CLR 2.0, donde NO existen tres cosas que este script usaba:
#
#   [Net.SecurityProtocolType]::Tls12  -> el enum de .NET 3.5 sólo tiene Ssl3 y Tls
#   Test-NetConnection                 -> cmdlet de PowerShell 4.0
#   Invoke-WebRequest                  -> cmdlet de PowerShell 3.0
#
# El resultado era una excepción, un "Unable to connect to server" y cero
# instalación, justo en la única plataforma para la que existe el binario legacy.
#
# ⚠️ No basta con cambiar los cmdlets por equivalentes de .NET 2.0: por omisión el
# CLR 2.0 impone su propia lista de protocolos (SSL 3.0 / TLS 1.0) y ningún host de
# este producto la acepta. La vía —sin instalar nada— es que .NET delegue en el
# schannel del sistema, que en Win7 SP1 sí sabe TLS 1.2 pero viene apagado. Eso son
# las dos claves de `Set-LegacyTlsRegistry` (soporte "TLS System Default Versions",
# KB3154518, hoy absorbido por los rollups de .NET).
#
# 🪤 Esas claves las lee el CLR **al arrancar el proceso**, así que ponerlas y seguir
# no sirve de nada: hay que relanzar. Por eso el `-TlsPrepared`, que además corta
# cualquier bucle si el relanzamiento no arreglara el problema.

function Test-LegacyTlsRegistry {
    $paths = @(
        @{ Path = 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client';
           Values = @{ 'Enabled' = 1; 'DisabledByDefault' = 0 } },
        @{ Path = 'HKLM:\SOFTWARE\Microsoft\.NETFramework\v2.0.50727';
           Values = @{ 'SystemDefaultTlsVersions' = 1; 'SchUseStrongCrypto' = 1 } }
    )
    foreach ($entry in $paths) {
        foreach ($name in $entry.Values.Keys) {
            $current = $null
            Try {
                $current = (Get-ItemProperty -Path $entry.Path -Name $name -ErrorAction Stop).$name
            } Catch {
                return $false
            }
            if ($current -ne $entry.Values[$name]) { return $false }
        }
    }
    return $true
}

function Set-LegacyTlsRegistry {
    # Habilita TLS 1.2 en el sistema y hace que .NET 2.0/3.5 respete esa decisión.
    # Sólo AGREGA capacidad criptográfica; no desactiva ni debilita nada.
    $targets = @(
        @{ Path = 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client';
           Values = @{ 'Enabled' = 1; 'DisabledByDefault' = 0 } },
        @{ Path = 'HKLM:\SOFTWARE\Microsoft\.NETFramework\v2.0.50727';
           Values = @{ 'SystemDefaultTlsVersions' = 1; 'SchUseStrongCrypto' = 1 } },
        # En x64 los procesos .NET de 32 bits leen la vista Wow6432Node, así que la
        # clave tiene que estar en las dos o el arreglo cubre sólo la mitad.
        @{ Path = 'HKLM:\SOFTWARE\Wow6432Node\Microsoft\.NETFramework\v2.0.50727';
           Values = @{ 'SystemDefaultTlsVersions' = 1; 'SchUseStrongCrypto' = 1 } }
    )
    foreach ($entry in $targets) {
        # Wow6432Node no existe en equipos de 32 bits: ahí se salta, no se falla.
        if ($entry.Path -like '*Wow6432Node*' -and -not (Test-Path 'HKLM:\SOFTWARE\Wow6432Node')) {
            continue
        }
        if (-not (Test-Path $entry.Path)) {
            New-Item -Path $entry.Path -Force | Out-Null
        }
        foreach ($name in $entry.Values.Keys) {
            New-ItemProperty -Path $entry.Path -Name $name -Value $entry.Values[$name] `
                -PropertyType DWord -Force | Out-Null
        }
    }
}

# Vale para PowerShell 5.1 igual que para 2.0: en .NET 4.x el valor por omisión
# también es SSL3/TLS1.0. En CLR 2.0 el `-bor 3072` produce un valor que el enum no
# reconoce y la asignación lanza; ahí manda la preparación del registro de abajo.
Try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
} Catch {
    # .NET 3.5: no hay Tls12 que pedir. Se depende de SystemDefaultTlsVersions.
}

if ($PSVersionTable.PSVersion.Major -lt 3 -and -not (Test-LegacyTlsRegistry)) {
    if ($TlsPrepared) {
        Write-Error -Message ('No se pudo habilitar TLS 1.2 en este equipo. ' +
            'Verifique que tenga Windows 7 SP1 con los rollups de .NET al dia, ' +
            'o instale el agente con el metodo Manual.')
        exit 1
    }
    Write-Output 'Habilitando TLS 1.2 para PowerShell 2.0...'
    Set-LegacyTlsRegistry
    # El CLR ya arranco sin esas claves: hay que releer la configuracion en un
    # proceso nuevo. El -TlsPrepared garantiza que esto ocurra una sola vez.
    $mySelf = $MyInvocation.MyCommand.Definition
    $child = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-ExecutionPolicy', 'Bypass', '-File', "`"$mySelf`"", '-TlsPrepared'
    ) -Wait -PassThru
    exit $child.ExitCode
}

$serviceName = 'observeragent'
If (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    write-host ('Observer RMM Is Already Installed')
} Else {
    $OutPath = $env:TMP
    $output = $innosetup

    $installArgs = @('-m install --api ', "$api", '--client-id', $clientid, '--site-id', $siteid, '--agent-type', "$agenttype", '--auth', "$auth")

    if ($power) {
        $installArgs += "--power"
    }

    if ($rdp) {
        $installArgs += "--rdp"
    }

    if ($ping) {
        $installArgs += "--ping"
    }

    Try
    {
        $DefenderStatus = Get-MpComputerStatus | select  AntivirusEnabled
        if ($DefenderStatus -match "True") {
            Add-MpPreference -ExclusionPath 'C:\Program Files\ObserverAgent\*'
            Add-MpPreference -ExclusionPath 'C:\Program Files\Mesh Agent\*'
            Add-MpPreference -ExclusionPath 'C:\ProgramData\ObserverRMM\*'
            Add-MpPreference -ExclusionProcess 'C:\Windows\Temp\is-*.tmp\observeragent*'
        }
    }
    Catch {
        # pass
    }

    # Reemplaza a Test-NetConnection (PowerShell 4.0), que no existe en Win7.
    # BeginConnect + WaitOne da el timeout que Connect() no tiene: sin eso, un host
    # inalcanzable bloquea ~20 s por intento en vez de los 10 que se piden aca.
    function Test-TcpPort {
        param([string]$ComputerName, [int]$Port)
        $ok = $false
        $client = New-Object System.Net.Sockets.TcpClient
        Try {
            $iar = $client.BeginConnect($ComputerName, $Port, $null, $null)
            if ($iar.AsyncWaitHandle.WaitOne(10000, $false)) {
                $client.EndConnect($iar)
                $ok = $true
            }
        }
        Catch {
            $ok = $false
        }
        Finally {
            $client.Close()
        }
        return $ok
    }

    # El exe se descarga de agents.observer.cl, cuyo cert es de Let's Encrypt y
    # encadena a ISRG Root X1. Windows no la trae de fabrica: la baja bajo demanda
    # desde ctldl.windowsupdate.com (actualizacion automatica de raices), y en redes
    # que bloquean ese host o con esa actualizacion desactivada por GPO la raiz nunca
    # llega. El navegador del mismo equipo confia igual (usa su propio almacen), pero
    # WebClient valida contra el de Windows y falla con "No se puede establecer una
    # relacion de confianza para el canal seguro SSL/TLS". Caso medido: SML
    # Valparaiso, 2026-09-28, misma IP publica con descargas OK y equipos fallidos.
    # Se agrega la raiz publica, verificada por huella, solo si falta.
    function Install-IsrgRootX1 {
        $thumb = 'CABD2A79A1076A31F21D253635CB039D4329A5E8'
        if (Test-Path "Cert:\LocalMachine\Root\$thumb") { return }
        Try {
            $der = [Convert]::FromBase64String('MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAwTzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2VhcmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygch77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6UA5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sWT8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyHB5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UCB5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUvKBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWnOlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTnjh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbwqHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CIrU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkqhkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZLubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KKNFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7UrTkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdCjNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVcoyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPAmRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57demyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=')
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(,$der)
            if ($cert.Thumbprint -ne $thumb) { return }
            $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
            $store.Open('ReadWrite')
            Try { $store.Add($cert) } Finally { $store.Close() }
            Write-Output 'Raiz ISRG Root X1 agregada al almacen de Windows'
        }
        Catch {
            # Sin permisos de administrador u otro fallo: se sigue, y si la raiz
            # hacia falta la descarga lo informa.
        }
    }

    Install-IsrgRootX1

    $X = 0
    $connectresult = $false
    do {
      Write-Output "Waiting for network"
      Start-Sleep -s 5
      $X += 1
      $connectresult = Test-TcpPort $apilink[2] 443
    } until($connectresult -or $X -eq 3)

    if ($connectresult) {
        Try
        {
            # Reemplaza a Invoke-WebRequest (PowerShell 3.0), que no existe en Win7.
            $wc = New-Object System.Net.WebClient
            Try {
                $wc.DownloadFile($downloadlink, "$OutPath\$output")
            }
            Finally {
                $wc.Dispose()
            }
            write-host ('Installing...')
            # full-A: el asset de release es el instalador Inno Setup. Flujo de dos pasos:
            # 1) instalar en silencio (copia el binario a Program Files, registra el servicio
            #    y crea la entrada de desinstalacion en "Agregar o quitar programas").
            Start-Process -FilePath $OutPath\$output -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES') -Wait
            # dar margen a que el servicio quede asentado en equipos lentos antes de enrolar (backport v1.5.1 B3).
            Start-Sleep -s 7

            # El instalador puede haberse NEGADO a instalar, y hasta el 2026-08-09
            # eso terminaba en `exit 0`. El caso concreto: el guard de arquitectura
            # de setup.iss (instalador de 32 bits en un Windows de 64 bits, o el de
            # 64 en uno de 32) aborta antes de copiar nada. Como acá se corre con
            # /SUPPRESSMSGBOXES, el operador NO ve el mensaje del guard; y como
            # `Start-Process` sobre una ruta inexistente es un error NO terminante
            # -- este script no fija $ErrorActionPreference = 'Stop' -- el `Catch`
            # de abajo no se enteraba y la linea siguiente declaraba exito.
            #
            # O sea: el instalador se negaba correctamente y la consola informaba
            # que todo salio bien. La unica senal que queda es esta.
            $agentExe = 'C:\Program Files\ObserverAgent\observeragent.exe'
            if (-not (Test-Path $agentExe)) {
                Write-Error -Message ("La instalacion no dejo el agente en $agentExe, asi que no se enrola nada. " +
                    "La causa mas probable es que el instalador se haya negado a instalarse en este equipo: " +
                    "revise que la arquitectura del instalador (32 o 64 bits) sea la del equipo, y consulte el " +
                    "log del instalador de Inno Setup.")
                exit 1
            }

            # 2) enrolar desde el binario ya instalado.
            Start-Process -FilePath $agentExe -ArgumentList $installArgs -Wait
            exit 0
        }
        Catch
        {
            $ErrorMessage = $_.Exception.Message
            $FailedItem = $_.Exception.ItemName
            Write-Error -Message "$ErrorMessage $FailedItem"
            exit 1
        }
        Finally
        {
            Remove-Item -Path $OutPath\$output -ErrorAction SilentlyContinue
        }
    } else {
        Write-Output "Unable to connect to server"
    }
}
