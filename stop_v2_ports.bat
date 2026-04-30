@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($port in @(18483,13015)){ $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach($listener in $listeners){ $procId = [int]$listener.OwningProcess; Write-Host ('Stopping PID ' + $procId + ' on port ' + $port); Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } }"
