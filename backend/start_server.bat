@echo off
chcp 65001 >nul
cd /d I:\BiliNote\BiliNote_src\backend
echo Starting BiliNote Backend...
echo.
.venv\Scripts\python.exe -u -m uvicorn main:app --host 0.0.0.0 --port 8483
echo.
echo Server stopped. Press any key to close...
pause >nul
