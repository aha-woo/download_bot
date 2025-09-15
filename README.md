# Telegram User Client (Telethon版本)

**🎉 已完全迁移到User API！支持2GB大文件下载，无20MB限制**

## 📋 主要变更

### ✅ **已迁移完成**
- ✅ **完全替换为Telethon User API**
- ✅ **支持2GB大文件下载**（无Bot API的20MB限制）
- ✅ **保留所有原有功能**：媒体组处理、自动清理、随机延迟
- ✅ **更强的权限**：可以访问更多频道和功能
- ✅ **更稳定的连接**：User API连接更稳定

### 🔄 **功能对比**

| 功能 | Bot API (旧版) | User API (新版) |
|------|---------------|----------------|
| 文件大小限制 | 20MB | 2GB |
| 支持的媒体类型 | 基本类型 | 所有类型 |
| 频道权限 | 需要Bot权限 | 用户权限 |
| 连接稳定性 | 一般 | 优秀 |
| API限制 | 严格 | 宽松 |

## 🚀 快速开始

### 1. **获取API凭据**
1. 访问 https://my.telegram.org/apps
2. 登录你的Telegram账号
3. 创建新应用，获取 `API_ID` 和 `API_HASH`

### 2. **配置环境变量**
```bash
cp config.env.example .env
nano .env
```

填入以下信息：
```bash
# 必须配置
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE_NUMBER=+1234567890

# 频道配置
SOURCE_CHANNEL_ID=@your_source_channel
TARGET_CHANNEL_ID=@your_target_channel
```

### 3. **安装依赖**
```bash
pip install -r requirements.txt
```

### 4. **首次运行（验证手机号）**
```bash
python3 main.py
```
首次运行时会要求输入验证码，验证后会创建会话文件。

### 5. **生产环境部署**

#### 使用PM2：
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

#### 使用Systemd：
```bash
sudo cp systemd/telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## 📁 文件结构

```
download_bot/
├── main.py                 # 主程序 (Telethon版本)
├── config.py              # 配置管理 (User API)
├── media_downloader.py     # 媒体下载 (Telethon)
├── bot_handler.py          # 消息处理 (Telethon)
├── requirements.txt        # 依赖列表 (Telethon)
├── config.env.example      # 配置模板
├── deploy.sh              # 部署脚本
├── ecosystem.config.js     # PM2配置
└── systemd/
    └── telegram-bot.service # Systemd服务
```

## 🔧 主要功能

### 🎯 **自动监听转发**
- 实时监听源频道新消息
- 自动下载媒体文件（支持2GB）
- 智能处理媒体组
- 自动转发到目标频道

### 📥 **高级下载功能**
- **无文件大小限制**：支持最大2GB文件
- **智能媒体组处理**：自动将多媒体消息组合发送
- **自动文件清理**：发送成功后自动删除本地文件
- **错误恢复**：网络中断后自动重连

### 🎲 **手动控制功能**
- 随机下载历史消息
- 按关键词筛选转发
- 按媒体类型筛选
- 转发最近N条消息

## ⚙️ 高级配置

### 📊 **性能调优**
```bash
# 最大文件大小 (默认2GB)
MAX_FILE_SIZE=2GB

# 下载路径
DOWNLOAD_PATH=./downloads

# 会话文件位置
SESSION_PATH=./
SESSION_NAME=telegram_session
```

### 🔒 **安全建议**
1. **保护会话文件**：`.session` 文件包含登录信息，请妥善保管
2. **限制文件权限**：`chmod 600 .env`
3. **定期更新**：保持依赖库最新版本

## 🆚 与Bot API版本的区别

### **优势**
- ✅ **突破20MB限制**：支持2GB大文件
- ✅ **更强权限**：可以访问私人频道
- ✅ **更稳定**：连接更稳定，断线重连
- ✅ **功能更全**：支持所有Telegram功能

### **注意事项**
- ⚠️ **需要手机验证**：首次运行需要验证码
- ⚠️ **会话管理**：需要妥善保管 `.session` 文件
- ⚠️ **API限制**：虽然宽松，但仍有频率限制

## 📊 监控和日志

### **查看日志**
```bash
# PM2日志
pm2 logs user-client

# Systemd日志
sudo journalctl -u telegram-bot -f

# 本地日志文件
tail -f bot.log
```

### **状态检查**
```bash
# PM2状态
pm2 status

# Systemd状态
sudo systemctl status telegram-bot
```

## 🔧 故障排除

### **常见问题**

1. **验证码问题**
   ```bash
   # 删除会话文件重新验证
   rm telegram_session.session
   python3 main.py
   ```

2. **权限问题**
   ```bash
   # 检查频道权限
   # 确保用户账号可以访问源频道和发送到目标频道
   ```

3. **大文件下载失败**
   ```bash
   # 检查网络连接
   # 检查磁盘空间
   # 查看错误日志
   ```

## 🎉 迁移完成！

恭喜！你的Telegram媒体转发工具已成功升级到User API版本，现在可以：

- 🚀 **下载2GB大文件**
- 🎯 **更稳定的运行**
- 🔧 **更强大的功能**
- 💪 **突破所有限制**

如有问题，请检查日志文件或重新运行配置。