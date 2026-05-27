@echo off
setlocal
cd /d "%~dp0"

set "CONDA_ENV=bili"
set "PYTHON_VERSION=3.11"
set "CONDA_CHANNEL=conda-forge"
set "BACKEND_DIR=%~dp0backend"
set "FRONTEND_DIR=%~dp0BillNote_frontend"

where conda >nul 2>nul
if errorlevel 1 (
    echo [ERROR] conda was not found. Please install Anaconda or Miniconda first.
    pause
    exit /b 1
)

for /f "delims=" %%I in ('conda info --base') do set "CONDA_BASE=%%I"
set "CONDA_BAT=%CONDA_BASE%\condabin\conda.bat"
if not exist "%CONDA_BAT%" set "CONDA_BAT=conda"

set "INSTALL_BACKEND_DEPS=0"
call "%CONDA_BAT%" env list | findstr /R /C:"^%CONDA_ENV%[ ]" >nul
if errorlevel 1 (
    echo [INFO] Conda environment "%CONDA_ENV%" not found. Creating it...
    echo [INFO] Using "%CONDA_CHANNEL%" with --override-channels to avoid non-interactive Anaconda ToS prompts.
    call "%CONDA_BAT%" create -y -n "%CONDA_ENV%" --override-channels --channel "%CONDA_CHANNEL%" python=%PYTHON_VERSION%
    if errorlevel 1 (
        echo [ERROR] Failed to create conda environment "%CONDA_ENV%".
        pause
        exit /b 1
    )
    set "INSTALL_BACKEND_DEPS=1"
) else (
    echo [INFO] Conda environment "%CONDA_ENV%" already exists.
)

call "%CONDA_BAT%" run -n "%CONDA_ENV%" python -c "import pkg_resources, fastapi, faster_whisper" >nul 2>nul
if errorlevel 1 set "INSTALL_BACKEND_DEPS=1"

if "%INSTALL_BACKEND_DEPS%"=="1" (
    echo [INFO] Installing backend dependencies for "%CONDA_ENV%"...
    call "%CONDA_BAT%" run -n "%CONDA_ENV%" python -m pip install --upgrade pip "setuptools<81" wheel
    if errorlevel 1 (
        echo [ERROR] Failed to install Python bootstrap dependencies in "%CONDA_ENV%".
        pause
        exit /b 1
    )

    call "%CONDA_BAT%" run -n "%CONDA_ENV%" python -m pip install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install backend dependencies.
        pause
        exit /b 1
    )
    call "%CONDA_BAT%" run -n "%CONDA_ENV%" python -c "import pkg_resources" >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python package pkg_resources is still missing after dependency installation.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Backend dependencies already installed.
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found. Please install Node.js first.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules\.bin\vite.cmd" (
    echo [INFO] Frontend dependencies not found. Running npm install...
    pushd "%FRONTEND_DIR%"
    call npm install --legacy-peer-deps
    if errorlevel 1 (
        popd
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
    popd
) else (
    echo [INFO] Frontend dependencies already installed.
)

start "Backend" cmd /k call "%CONDA_BAT%" activate "%CONDA_ENV%" ^&^& cd /d "%BACKEND_DIR%" ^&^& python main.py
start "Frontend" powershell -NoExit -Command "Set-Location -LiteralPath '%FRONTEND_DIR%'; npm run dev"

start http://localhost:3015/
