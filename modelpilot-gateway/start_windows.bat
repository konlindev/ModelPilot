@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo [ModelPilot Gateway] Starting Windows setup...
echo [ModelPilot Gateway] 正在准备 Windows 启动环境...

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Trying to install Python 3.12 with winget...
    echo 未检测到 Python，正在尝试使用 winget 安装 Python 3.12...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo winget was not found. Please install Python 3.10+ manually from https://www.python.org/downloads/
        echo 未检测到 winget，请手动安装 Python 3.10+：https://www.python.org/downloads/
        pause
        exit /b 1
    )

    winget install --id Python.Python.3.12 -e --source winget
    if errorlevel 1 (
        echo Failed to install Python with winget. Please install Python 3.10+ manually.
        echo 使用 winget 安装 Python 失败，请手动安装 Python 3.10+。
        pause
        exit /b 1
    )
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python is still unavailable after installation. Please reopen this terminal or install Python manually.
    echo 安装后仍无法找到 Python，请重新打开终端或手动安装 Python。
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    echo 正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        echo 创建虚拟环境失败。
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    echo 激活虚拟环境失败。
    pause
    exit /b 1
)

echo Checking GitHub repository for updates...
echo 正在检查 GitHub 仓库更新...
python -m app.update_checker

echo Installing requirements...
echo 正在安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    echo 安装依赖失败。
    pause
    exit /b 1
)

echo Running first-run text setup wizard...
echo 正在运行首次启动文字配置向导...
python -m app.setup_wizard
if errorlevel 1 (
    echo First-run setup was not completed. Please run this script again after preparing the required values.
    echo 首次配置未完成。请准备好配置参数后重新运行本脚本。
    pause
    exit /b 1
)

echo Starting ModelPilot Gateway at http://localhost:8000
echo 正在启动 ModelPilot Gateway：http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
if errorlevel 1 (
    echo ModelPilot Gateway exited with an error.
    echo ModelPilot Gateway 异常退出。
    pause
    exit /b 1
)

pause
