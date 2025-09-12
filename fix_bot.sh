#!/bin/bash

echo "🔧 修复Telegram Bot..."

# 停止当前的PM2进程
echo "停止当前进程..."
pm2 stop download-bot
pm2 delete download-bot

# 备份原文件
echo "备份原文件..."
cp main.py main_backup.py

# 使用修复版本
echo "使用修复版本..."
cp main_fixed.py main.py

# 重新启动
echo "重新启动机器人..."
pm2 start ecosystem.config.js

echo "✅ 修复完成！"
echo "查看日志: pm2 logs download-bot"
echo "查看状态: pm2 status"
