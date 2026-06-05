@echo off
setlocal EnableExtensions

if /I "%~1"=="--check" (
    echo start_windows.bat syntax check OK
    exit /b 0
)

if /I not "%~1"=="--inner" (
    set "RUNNER=%TEMP%\modelpilot-start-windows-runner.bat"
    copy /Y "%~f0" "%RUNNER%" >nul
    if errorlevel 1 (
        echo [ModelPilot Gateway] Failed to prepare temporary startup runner.
        pause
        exit /b 1
    )
    call "%RUNNER%" --inner "%~dp0"
    exit /b %ERRORLEVEL%
)

set "PROJECT_DIR=%~2"
if "%PROJECT_DIR%"=="" set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo [ModelPilot Gateway] Failed to enter project directory: %PROJECT_DIR%
    pause
    exit /b 1
)

title ModelPilot Gateway
echo [ModelPilot Gateway] Starting Windows setup...
echo [ModelPilot Gateway] Project directory: %CD%

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Trying to install Python 3.12 with winget...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo winget was not found. Please install Python 3.10+ manually:
        echo https://www.python.org/downloads/
        pause
        exit /b 1
    )

    winget install --id Python.Python.3.12 -e --source winget
    if errorlevel 1 (
        echo Failed to install Python with winget. Please install Python 3.10+ manually.
        pause
        exit /b 1
    )
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python is still unavailable. Please reopen this terminal or install Python manually.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Checking GitHub repository for updates...
python -m app.update_checker
if errorlevel 1 (
    echo GitHub update check failed. Continuing with local code.
)

echo Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo Running first-run text setup wizard...
python -m app.setup_wizard
if errorlevel 1 (
    echo First-run setup was not completed. Please run this script again after preparing the required values.
    pause
    exit /b 1
)

echo Starting ModelPilot Gateway at http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
if errorlevel 1 (
    echo ModelPilot Gateway exited with an error.
    pause
    exit /b 1
)

echo ModelPilot Gateway stopped.
pause
