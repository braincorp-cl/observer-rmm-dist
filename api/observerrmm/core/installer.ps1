# author: https://github.com/bradhawkins85
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

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

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
    
    $X = 0
    do {
      Write-Output "Waiting for network"
      Start-Sleep -s 5
      $X += 1      
    } until(($connectresult = Test-NetConnection $apilink[2] -Port 443 | ? { $_.TcpTestSucceeded }) -or $X -eq 3)
    
    if ($connectresult.TcpTestSucceeded -eq $true){
        Try
        {  
            Invoke-WebRequest -Uri $downloadlink -OutFile $OutPath\$output
            write-host ('Installing...')
            # full-A: el asset de release es el instalador Inno Setup. Flujo de dos pasos:
            # 1) instalar en silencio (copia el binario a Program Files, registra el servicio
            #    y crea la entrada de desinstalacion en "Agregar o quitar programas").
            Start-Process -FilePath $OutPath\$output -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES') -Wait
            # dar margen a que el servicio quede asentado en equipos lentos antes de enrolar (backport v1.5.1 B3).
            Start-Sleep -s 7
            # 2) enrolar desde el binario ya instalado.
            Start-Process -FilePath 'C:\Program Files\ObserverAgent\observeragent.exe' -ArgumentList $installArgs -Wait
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
            Remove-Item -Path $OutPath\$output
        }
    } else {
        Write-Output "Unable to connect to server"
    }
}
