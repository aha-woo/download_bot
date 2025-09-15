#!/bin/bash

# Telegram User Client 部署脚本
# 适用于 Ubuntu/Debian VPS
# 使用 Telethon User API，支持2GB大文件

set -e

echo "🚀 开始部署 Telegram User Client..."

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    echo "❌ 请不要使用root用户运行此脚本"
    exit 1
fi

# 设置变量
PROJECT_DIR="/home/$(whoami)/download_bot"
SERVICE_NAME="telegram-bot"

# 更新系统包
echo "📦 更新系统包..."
sudo apt update && sudo apt upgrade -y

# 安装Python和pip
echo "🐍 安装Python和依赖..."
sudo apt install -y python3 python3-pip python3-venv git

# 创建项目目录
echo "📁 创建项目目录..."
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 创建虚拟环境
echo "🔧 创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo "📚 安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 复制systemd服务文件
echo "⚙️ 配置系统服务..."
sudo cp systemd/telegram-bot.service /etc/systemd/system/
sudo sed -i "s|/home/ubuntu|/home/$(whoami)|g" /etc/systemd/system/telegram-bot.service

# 重新加载systemd
sudo systemctl daemon-reload

# 创建配置文件
if [ ! -f .env ]; then
    echo "📝 创建配置文件..."
    cp config.env.example .env
    echo "⚠️  请编辑 .env 文件，填入你的API_ID、API_HASH和手机号"
    echo "   配置文件位置: $PROJECT_DIR/.env"
    echo "   获取API凭据: https://my.telegram.org/apps"
fi

# 创建下载目录
mkdir -p downloads

# 设置权限
chmod +x main.py
chmod 600 .env

echo "✅ 部署完成！"
echo ""
echo "📋 接下来的步骤："
echo "1. 编辑配置文件: nano $PROJECT_DIR/.env"
echo "2. 首次运行验证: python3 main.py (需要输入验证码)"
echo "3. 启动服务: sudo systemctl start $SERVICE_NAME"
echo "4. 设置开机自启: sudo systemctl enable $SERVICE_NAME"
echo "5. 查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "🔧 常用命令："
echo "  启动服务: sudo systemctl start $SERVICE_NAME"
echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
