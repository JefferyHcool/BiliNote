@echo off
cd /d "%~dp0"

start "Backend" powershell -NoExit -Command "cd backend; conda activate bili; python main.py"
start "Frontend" powershell -NoExit -Command "cd BillNote_frontend; npm run dev"

start http://localhost:3015/