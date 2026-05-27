@echo off
setlocal
cd /d "%~dp0"

set "SCRIPT=%~dp0backend\scripts\bilibili_login.py"

where python >nul 2>nul
if not errorlevel 1 (
    python "%SCRIPT%" %*
    goto done
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%SCRIPT%" %*
    goto done
)

echo [ERROR] Python was not found. Please install Python 3 or run this from your BiliNote Python environment.
exit /b 1

:done
echo.
pause
