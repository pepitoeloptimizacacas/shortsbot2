$panelRoot = $PSScriptRoot
try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8787/api/estado' -TimeoutSec 3 | Out-Null }
catch {
    Start-Process -FilePath "$panelRoot\.venv-voz\Scripts\python.exe" -ArgumentList 'panel.py' -WorkingDirectory $panelRoot -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Start-Process 'http://127.0.0.1:8787'
