#!/usr/bin/env bash
# Make executable first: chmod +x start_linux.sh

set -e

cd "$(dirname "$0")"

echo "[ModelPilot Gateway] Starting Linux setup..."
echo "[ModelPilot Gateway] 正在准备 Linux 启动环境..."

install_with_package_manager() {
  if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip
    return
  fi

  if command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3 python3-pip
    return
  fi

  echo "No supported package manager found. Please install Python 3.10+, venv, and pip manually."
  echo "未找到支持的包管理器，请手动安装 Python 3.10+、venv 和 pip。"
  exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Trying to install it..."
  echo "未检测到 python3，正在尝试安装..."
  install_with_package_manager
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "python3-venv is unavailable. Trying to install Python venv support..."
  echo "未检测到 python3-venv，正在尝试安装..."
  install_with_package_manager
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "pip is unavailable. Trying to install pip..."
  echo "未检测到 pip，正在尝试安装..."
  install_with_package_manager
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating virtual environment..."
  echo "正在创建虚拟环境..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Checking GitHub repository for updates..."
echo "正在检查 GitHub 仓库更新..."
python -m app.update_checker

echo "Installing requirements..."
echo "正在安装依赖..."
python -m pip install -r requirements.txt

echo "Running first-run text setup wizard..."
echo "正在运行首次启动文字配置向导..."
python -m app.setup_wizard

echo "Starting ModelPilot Gateway at http://localhost:8000"
echo "正在启动 ModelPilot Gateway：http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
