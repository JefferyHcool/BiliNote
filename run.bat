@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BACKEND_PORT=18483"
set "FRONTEND_PORT=13015"
set "NODE_OPTIONS=--max-old-space-size=4096"

set "BACKEND_HOST=0.0.0.0"
set "APP_PORT=%FRONTEND_PORT%"
set "VITE_FRONTEND_PORT=%FRONTEND_PORT%"
set "VITE_API_BASE_URL=http://127.0.0.1:%BACKEND_PORT%/api"
set "VITE_SCREENSHOT_BASE_URL=http://127.0.0.1:%BACKEND_PORT%/static/screenshots"
set "API_BASE_URL=http://127.0.0.1:%BACKEND_PORT%"
set "SCREENSHOT_BASE_URL=http://127.0.0.1:%BACKEND_PORT%/static/screenshots"
set "NOTE_TASK_MAX_WORKERS=2"


echo [BiliNote v2] root: %ROOT%
echo [BiliNote v2] backend: http://127.0.0.1:%BACKEND_PORT%
echo [BiliNote v2] frontend: http://127.0.0.1:%FRONTEND_PORT%

echo [1/3] stopping old BiliNote v2 isolated ports if any...
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($port in @(18483,13015)){ $listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach($listener in $listeners){ $pidToStop=[int]$listener.OwningProcess; Write-Host ('Stopping PID '+$pidToStop+' on port '+$port); Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Seconds 1"

echo [2/3] starting backend...
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo ERROR: Python venv not found: %ROOT%.venv\Scripts\python.exe
  pause
  exit /b 1
)
if not exist "%ROOT%backend\logs" mkdir "%ROOT%backend\logs"
(
  echo @echo off
  echo cd /d "%%~dp0backend"
  echo set "BACKEND_PORT=18483"
  echo set "BACKEND_HOST=0.0.0.0"
  echo set "VIDEO_UNDERSTANDING_MAX_FRAMES=8"
  echo set "BILIBILI_CDP_FIRST=1"
  echo set "BILIBILI_LOWEST_VIDEO_FIRST=1"
  echo set "BILIBILI_LOWEST_AUDIO_FIRST=1"
  echo set "BILIBILI_MEDIA_RETRY_ATTEMPTS=8"
  echo set "BILIBILI_SKIP_YTDLP_SUBTITLES=1"
  echo set "NOTE_TASK_MAX_WORKERS=2"
  echo "..\.venv\Scripts\python.exe" main.py
) > "%ROOT%start_backend_18483.cmd"
start "BiliNote v2 Backend 18483" /D "%ROOT%" "%ROOT%start_backend_18483.cmd"

echo [3/3] starting frontend static server...
if not exist "%ROOT%BillNote_frontend\dist\index.html" (
  echo ERROR: frontend dist not found. Run npm run build first.
  pause
  exit /b 1
)
start "BiliNote v2 Frontend 13015" /D "%ROOT%" "%ROOT%.venv\Scripts\python.exe" "%ROOT%serve_frontend_13015.py"

echo Waiting for services...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 90;$i++){ Start-Sleep -Seconds 2; try{$b=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:18483/api/sys_check; $f=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:13015/; if($b.StatusCode -eq 200 -and $f.StatusCode -eq 200){$ok=$true; break}}catch{} }; if(-not $ok){ Write-Host 'ERROR: services not ready'; exit 1 }"
if errorlevel 1 (
  echo Backend or frontend did not become ready. Check the opened windows.
  pause
  exit /b 1
)

echo Ready. Opening http://127.0.0.1:13015/
start http://127.0.0.1:13015/
endlocal
