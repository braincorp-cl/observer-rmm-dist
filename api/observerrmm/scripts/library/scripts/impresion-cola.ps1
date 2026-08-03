<#
.SYNOPSIS
    Diagnostica y desatasca la cola de impresión.

.DESCRIPTION
    Une los dos scripts de impresión del catálogo original (purgar todos los trabajos y
    reintentar los atascados) y agrega el modo de diagnóstico que faltaba, porque
    purgar es destructivo y muchas veces innecesario.

    Los tres modos, de menos a más agresivo:

      estado      — informa cada impresora, sus trabajos y desde cuándo están. Un
                    trabajo con horas de antigüedad y estado de error es el atascado;
                    uno de hace un minuto simplemente se está imprimiendo.
      reintentar  — reanuda los trabajos en estado de error o pausados, sin borrar nada.
                    Es lo que suele alcanzar cuando la impresora estuvo apagada.
      purgar      — BORRA todos los trabajos pendientes y reinicia el spooler. Lo que
                    la gente mandó a imprimir y no salió, se pierde y hay que mandarlo
                    de nuevo.

.PARAMETER Modo
    estado (por defecto), reintentar, purgar.

.PARAMETER Impresora
    Limita la acción a una impresora por nombre.

.EXAMPLE
    impresion-cola.ps1
    impresion-cola.ps1 -Modo reintentar
    impresion-cola.ps1 -Modo purgar -Impresora "HP LaserJet"
#>

[CmdletBinding()]
param(
    [ValidateSet("estado", "reintentar", "purgar")]
    [string]$Modo = "estado",

    [string]$Impresora
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

$rutaSpool = Join-Path $env:SystemRoot "System32\spool\PRINTERS"

Write-Output "== Servicio de cola de impresión =="
try {
    $spooler = Get-Service -Name Spooler -ErrorAction Stop
    Write-Output "  estado: $($spooler.Status) / inicio $($spooler.StartType)"
    if ($spooler.Status -ne "Running") {
        Write-Output "  El spooler está detenido: ninguna impresora funciona hasta que arranque."
    }
}
catch {
    Write-Output "  No se pudo consultar el servicio Spooler: $($_.Exception.Message)"
    exit 1
}

# Los archivos de spool en disco son la señal objetiva de trabajos pendientes: si la
# cola figura vacía y acá hay archivos, el spooler perdió la referencia.
try {
    $archivosSpool = @(Get-ChildItem -Path $rutaSpool -File -ErrorAction Stop)
    $bytesSpool = 0
    foreach ($archivo in $archivosSpool) { $bytesSpool += $archivo.Length }
    Write-Output "  archivos en cola (disco): $($archivosSpool.Count) — $([Math]::Round($bytesSpool / 1MB, 1)) MB"
}
catch {
    Write-Output "  no se pudo leer $rutaSpool"
    $archivosSpool = @()
}

try {
    if ($Impresora) {
        $impresoras = @(Get-Printer -Name "*$Impresora*" -ErrorAction Stop)
    }
    else {
        $impresoras = @(Get-Printer -ErrorAction Stop)
    }
}
catch {
    Write-Output ""
    Write-Output "No se pudieron enumerar las impresoras: $($_.Exception.Message)"
    exit 1
}

if ($impresoras.Count -eq 0) {
    Write-Output ""
    Write-Output "No hay impresoras que coincidan."
    exit 1
}

$ahora = Get-Date
$totalTrabajos = 0
$atascados = New-Object System.Collections.ArrayList

Write-Output ""
Write-Output "== Impresoras y trabajos =="

foreach ($impresoraActual in ($impresoras | Sort-Object Name)) {
    Write-Output ""
    Write-Output "  $($impresoraActual.Name)"
    Write-Output "    estado:  $($impresoraActual.PrinterStatus)"
    Write-Output "    puerto:  $($impresoraActual.PortName)"

    try {
        $trabajos = @(Get-PrintJob -PrinterName $impresoraActual.Name -ErrorAction Stop)
    }
    catch {
        Write-Output "    no se pudieron leer los trabajos: $($_.Exception.Message)"
        continue
    }

    $totalTrabajos += $trabajos.Count

    if ($trabajos.Count -eq 0) {
        Write-Output "    trabajos: ninguno"
        continue
    }

    Write-Output "    trabajos: $($trabajos.Count)"
    foreach ($trabajo in $trabajos) {
        $antiguedad = if ($trabajo.SubmittedTime) { $ahora - $trabajo.SubmittedTime } else { $null }
        $textoAntiguedad = if ($antiguedad) { "hace $([int]$antiguedad.TotalMinutes) min" } else { "sin fecha" }

        Write-Output ""
        Write-Output "      id $($trabajo.Id): $($trabajo.DocumentName)"
        Write-Output "        usuario:  $($trabajo.UserName)"
        Write-Output "        estado:   $($trabajo.JobStatus)"
        Write-Output "        enviado:  $textoAntiguedad"
        Write-Output "        páginas:  $($trabajo.PagesPrinted) de $($trabajo.TotalPages)"

        # Se considera atascado lo que está en error o pausado, o lo que lleva más de
        # media hora sin avanzar. Un trabajo reciente en curso NO es un atasco.
        $enProblema = $trabajo.JobStatus -match "Error|Paused|Blocked|Offline|PaperOut"
        $muyViejo = $antiguedad -and $antiguedad.TotalMinutes -gt 30

        if ($enProblema -or $muyViejo) {
            Write-Output "        DIAGNÓSTICO: atascado ($(if ($enProblema) { 'estado de error' } else { 'sin avanzar hace más de 30 min' }))"
            [void]$atascados.Add(@{
                    Impresora = $impresoraActual.Name
                    Id        = $trabajo.Id
                    Documento = $trabajo.DocumentName
                })
        }
    }
}

Write-Output ""
Write-Output "  total: $totalTrabajos trabajo(s), $($atascados.Count) atascado(s)."

if ($Modo -eq "estado") {
    Write-Output ""
    Write-Output "Modo 'estado': no se modificó nada."
    if ($atascados.Count -gt 0) {
        Write-Output "Probá primero -Modo reintentar, que no pierde los trabajos."
        exit 1
    }
    exit 0
}

$errores = 0

if ($Modo -eq "reintentar") {
    Write-Output ""
    Write-Output "== Reintentando trabajos atascados =="

    if ($atascados.Count -eq 0) {
        Write-Output "  No hay trabajos atascados que reintentar."
        exit 0
    }

    foreach ($item in $atascados) {
        try {
            # Reanudar un trabajo que no está pausado no hace daño: el spooler lo
            # ignora. Lo que importa es sacarlo del estado de error.
            Resume-PrintJob -PrinterName $item.Impresora -ID $item.Id -ErrorAction Stop
            Write-Output "  reanudado: [$($item.Impresora)] id $($item.Id) — $($item.Documento)"
        }
        catch {
            Write-Output "  ERROR con [$($item.Impresora)] id $($item.Id): $($_.Exception.Message)"
            $errores++
        }
    }

    # Verificación por efecto: releer las colas y ver si el estado de error se fue.
    Start-Sleep -Seconds 5
    $siguenEnError = 0
    foreach ($item in $atascados) {
        try {
            $trabajo = Get-PrintJob -PrinterName $item.Impresora -ID $item.Id -ErrorAction Stop
            if ($trabajo.JobStatus -match "Error|Blocked|Offline|PaperOut") {
                $siguenEnError++
            }
        }
        catch {
            # El trabajo ya no existe: se imprimió o salió de la cola. Es el resultado
            # que se buscaba.
            Write-Verbose "el trabajo $($item.Id) ya no está en la cola"
        }
    }

    Write-Output ""
    Write-Output "== Resultado =="
    Write-Output "  $siguenEnError trabajo(s) siguen en error tras el reintento."
    if ($siguenEnError -gt 0) {
        Write-Output "  Si la impresora está sin papel, sin tóner o apagada, ningún"
        Write-Output "  reintento lo arregla: hay que ir al equipo."
        exit 1
    }
    if ($errores -gt 0) { exit 1 }
    exit 0
}

Write-Output ""
Write-Output "== Purgando la cola y reiniciando el spooler =="
Write-Output "  Los $totalTrabajos trabajo(s) pendientes se van a perder."

foreach ($impresoraActual in $impresoras) {
    try {
        $trabajos = @(Get-PrintJob -PrinterName $impresoraActual.Name -ErrorAction Stop)
        foreach ($trabajo in $trabajos) {
            try {
                Remove-PrintJob -PrinterName $impresoraActual.Name -ID $trabajo.Id -ErrorAction Stop
                Write-Output "  borrado: [$($impresoraActual.Name)] id $($trabajo.Id)"
            }
            catch {
                Write-Output "  ERROR al borrar id $($trabajo.Id): $($_.Exception.Message)"
                $errores++
            }
        }
    }
    catch {
        Write-Verbose $_.Exception.Message
    }
}

# El reinicio del spooler es lo que libera los archivos que quedaron trabados en disco
# y que Remove-PrintJob no alcanza.
Write-Output ""
Write-Output "  Reiniciando el spooler..."
try {
    Restart-Service -Name Spooler -Force -ErrorAction Stop
    Start-Sleep -Seconds 3
    $spooler = Get-Service -Name Spooler -ErrorAction Stop
    if ($spooler.Status -eq "Running") {
        Write-Output "  spooler reiniciado y corriendo."
    }
    else {
        Write-Output "  FALLA: el spooler quedó en estado $($spooler.Status)."
        $errores++
    }
}
catch {
    Write-Output "  ERROR al reiniciar el spooler: $($_.Exception.Message)"
    $errores++
}

# Verificación por efecto: los archivos de spool en disco.
try {
    $restantes = @(Get-ChildItem -Path $rutaSpool -File -ErrorAction Stop)
    Write-Output "  archivos en cola tras la purga: $($restantes.Count)"
    if ($restantes.Count -gt 0) {
        Write-Output "  Quedaron archivos: suelen liberarse solos, o con el equipo reiniciado."
    }
}
catch {
    Write-Verbose $_.Exception.Message
}

Write-Output ""
Write-Output "== Resultado =="
if ($errores -gt 0) {
    Write-Output "  Terminó con $errores error(es)."
    exit 1
}
Write-Output "  Cola purgada y spooler reiniciado."
exit 0
