# Telegram Media Forward Bot

一个用于自动从源频道下载媒体文件并转发到目标频道的Telegram机器人。

## 功能特性

- 🤖 自动监听源频道的消息
- 📥 下载图片、视频、文档等媒体文件
- 📤 转发消息到目标频道
- 🔄 支持多种媒体格式
- 📝 完整的日志记录
- 🛡️ 错误处理和重试机制
- 🚀 支持VPS部署和系统服务

## 支持的媒体类型

- 图片 (Photo)
- 视频 (Video)
- 文档 (Document)
- 音频 (Audio)
- 语音 (Voice)
- 视频笔记 (Video Note)
- 动画 (Animation/GIF)
- 贴纸 (Sticker)

## 安装和配置

### 1. 获取Bot Token

1. 在Telegram中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取Bot Token

### 2. 获取频道信息

#### 源频道（要监听的频道）
- 将机器人添加到源频道
- 给机器人管理员权限（至少需要读取消息权限）
- 获取频道ID（格式：`@channel_username` 或 `-1001234567890`）

#### 目标频道（要转发到的频道）
- 将机器人添加到目标频道
- 给机器人管理员权限（需要发送消息权限）
- 获取频道ID（格式：`@channel_username` 或 `-1001234567890`）

### 3. 部署到VPS

#### 方法一：使用部署脚本（推荐）

```bash
# 克隆项目
git clone <your-repo-url> download_bot
cd download_bot

# 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

#### 方法二：手动部署

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 2. 创建项目目录
mkdir -p ~/download_bot
cd ~/download_bot

# 3. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 4. 安装Python依赖
pip install -r requirements.txt

# 5. 配置环境变量
cp config.env.example .env
nano .env  # 编辑配置文件

# 6. 安装系统服务
sudo cp systemd/telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### 4. 配置环境变量

编辑 `.env` 文件：

```env
# Telegram Bot Configuration
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
SOURCE_CHANNEL_ID=@source_channel_username
TARGET_CHANNEL_ID=@target_channel_username

# 下载设置
DOWNLOAD_PATH=./downloads
MAX_FILE_SIZE=50MB
```

## 使用方法

### 启动机器人

```bash
# 启动服务
sudo systemctl start telegram-bot

# 查看状态
sudo systemctl status telegram-bot

# 查看日志
sudo journalctl -u telegram-bot -f
```

### 机器人命令

- `/start` - 显示机器人状态信息
- `/status` - 查看详细状态和统计信息

## 配置说明

### 环境变量

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| `BOT_TOKEN` | ✅ | Bot Token | `1234567890:ABCdef...` |
| `SOURCE_CHANNEL_ID` | ✅ | 源频道ID | `@source_channel` |
| `TARGET_CHANNEL_ID` | ✅ | 目标频道ID | `@target_channel` |
| `DOWNLOAD_PATH` | ❌ | 下载目录 | `./downloads` |
| `MAX_FILE_SIZE` | ❌ | 最大文件大小 | `50MB` |

### 文件大小限制

支持的文件大小单位：
- `KB` - 千字节
- `MB` - 兆字节  
- `GB` - 千兆字节

示例：`10MB`, `1GB`, `500KB`

## 日志和监控

### 查看日志

```bash
# 实时查看日志
sudo journalctl -u telegram-bot -f

# 查看最近的日志
sudo journalctl -u telegram-bot -n 100

# 查看今天的日志
sudo journalctl -u telegram-bot --since today
```

### 日志文件

机器人还会在项目目录下创建 `bot.log` 文件记录详细日志。

## 故障排除

### 常见问题

1. **机器人无法启动**
   - 检查Bot Token是否正确
   - 检查频道ID格式是否正确
   - 查看日志：`sudo journalctl -u telegram-bot -f`

2. **无法接收消息**
   - 确认机器人已添加到源频道
   - 确认机器人有读取消息的权限
   - 检查频道ID是否正确

3. **无法发送消息**
   - 确认机器人已添加到目标频道
   - 确认机器人有发送消息的权限
   - 检查目标频道ID是否正确

4. **文件下载失败**
   - 检查磁盘空间是否充足
   - 检查文件大小是否超过限制
   - 查看详细错误日志

### 权限检查

确保机器人在频道中有以下权限：

**源频道权限：**
- 读取消息
- 查看媒体

**目标频道权限：**
- 发送消息
- 发送媒体
- 嵌入链接

## 安全注意事项

1. **保护Bot Token**
   - 不要将Bot Token提交到代码仓库
   - 使用 `.env` 文件存储敏感信息
   - 设置适当的文件权限：`chmod 600 .env`

2. **网络安全**
   - 使用防火墙限制不必要的端口访问
   - 定期更新系统和依赖包
   - 监控异常活动

3. **数据安全**
   - 定期清理下载的临时文件
   - 备份重要配置
   - 监控磁盘使用情况

## 开发和贡献

### 项目结构

```
download_bot/
├── main.py              # 主程序入口
├── config.py            # 配置管理
├── bot_handler.py       # 消息处理
├── media_downloader.py  # 媒体下载
├── requirements.txt     # Python依赖
├── config.env.example   # 配置示例
├── deploy.sh           # 部署脚本
├── systemd/            # 系统服务配置
│   └── telegram-bot.service
└── README.md           # 说明文档
```

### 开发环境

```bash
# 克隆项目
git clone <repo-url>
cd download_bot

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp config.env.example .env
# 编辑 .env 文件

# 运行机器人
python main.py
```

## 许可证

MIT License

## 支持

如果遇到问题或有建议，请：

1. 查看日志文件排查问题
2. 检查配置是否正确
3. 提交Issue或Pull Request

---

**注意：** 使用此机器人时请遵守Telegram的使用条款和相关法律法规。
