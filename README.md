# Telegram User Client - 智能媒体转发工具

> 🎉 **基于Telethon User API，支持2GB大文件下载，智能队列延迟转发**

## ✨ 核心特性

### 🚀 **技术突破**
- **2GB大文件支持**：突破Bot API的20MB限制
- **User API优势**：可下载受限内容和私密频道媒体
- **高稳定性**：PM2进程管理，24小时稳定运行

### 🔄 **双模式转发**
- **⚡ 立即模式**：收到消息后立即转发（2-15秒延迟）
- **📋 队列模式**：下载后加入队列，随机延迟发送（5分钟-2小时）
- **🔄 实时切换**：运行时通过命令切换模式

### 🎯 **智能功能**
- **📱 Telegram控制**：私聊发送命令控制所有功能
- **📦 媒体组保持**：完整保持多媒体消息结构
- **🧹 自动清理**：转发成功后自动删除本地文件
- **⏱️ 防检测算法**：智能随机延迟，避免被识别为机器人
- **🔁 重试机制**：失败消息自动重试，提高成功率

### 📋 **队列系统**
- **延迟发送**：支持5分钟到2小时的随机延迟
- **分批处理**：可配置批次大小和发送间隔
- **状态持久化**：程序重启后队列数据不丢失
- **实时监控**：详细的队列状态和统计信息

## 🚀 快速开始

### 1. 获取API凭据

1. 访问 [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. 登录你的Telegram账号
3. 创建新应用，获取 `API_ID` 和 `API_HASH`

### 2. 环境配置

```bash
# 复制配置模板
cp config.env.example .env

# 编辑配置文件
nano .env
```

**基础配置：**
```bash
# Telegram User API 配置 (必需)
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE_NUMBER=+1234567890

# 频道配置
SOURCE_CHANNEL_ID=@your_source_channel
TARGET_CHANNEL_ID=@your_target_channel

# 多源频道配置 (可选)
SOURCE_CHANNELS=@channel1,@channel2,-1001234567890

# 下载设置
DOWNLOAD_PATH=./downloads
MAX_FILE_SIZE=2GB

# 队列延迟转发设置
QUEUE_ENABLED=false                 # 启用队列模式
MIN_SEND_DELAY=300                  # 最小发送延迟(5分钟)
MAX_SEND_DELAY=7200                 # 最大发送延迟(2小时)
BATCH_SEND_ENABLED=false            # 启用分批发送
BATCH_SIZE=5                        # 每批消息数量
BATCH_INTERVAL=1800                 # 批次间隔(30分钟)

# 防检测延迟设置
RANDOM_DELAY_MIN=2
RANDOM_DELAY_MAX=15
BATCH_DELAY_MIN=30
BATCH_DELAY_MAX=120
```

### 3. 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 首次验证

```bash
# 首次运行需要验证手机号
python3 main.py
```

程序会要求输入验证码，验证成功后创建会话文件。

### 5. 生产部署

#### PM2部署（推荐）

```bash
# 创建日志目录
mkdir -p logs

# 启动服务
pm2 start ecosystem.config.js

# 设置开机自启
pm2 save
pm2 startup
```

#### 系统服务部署

```bash
# 复制服务文件
sudo cp systemd/telegram-bot.service /etc/systemd/system/

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## 🎮 使用方法

### 📱 Telegram命令控制

程序运行后，直接给你的账号发私聊消息控制：

#### 基础命令

```
/help                                    # 查看帮助
/status                                  # 查看系统状态和队列信息
```

#### 手动下载命令

```
/download <频道ID> <天数> [数量]           # 下载指定频道的历史消息

# 示例：
/download @channel1 0 20                 # 下载今天的20条消息
/download @channel1 3 50                 # 下载3天前的50条消息
/download -1001234567890 7 30            # 下载7天前的30条消息
```

#### 🔄 模式切换命令

```
/mode                                    # 查看当前转发模式
/mode immediate                          # 切换到立即转发模式
/mode queue                              # 切换到队列延迟转发模式
```

#### 📋 队列管理命令

```
/queue status                            # 查看详细队列状态
/queue clear                             # 清空队列
/queue start                             # 启动队列处理器
/queue stop                              # 停止队列处理器
```

#### 📊 队列模式说明

- **⚡ 立即模式**：收到消息→短延迟(2-15秒)→下载→立即转发
- **📋 队列模式**：收到消息→下载→加入队列→延迟发送(5分钟-2小时)

**队列模式优势：**
- 🕐 **延迟发送**：避免被识别为机器人
- 📦 **批量处理**：可配置分批发送
- 🔄 **重试机制**：失败自动重试
- 💾 **状态持久化**：程序重启后队列不丢失

#### 支持的频道ID格式

```
@channel_username       # 公开频道用户名
@group_username        # 公开群组用户名
-1001234567890         # 频道/群组数字ID
1234567890             # 普通群组ID
```

### 🔍 获取私有群组ID

如果需要监听私有群组，创建临时脚本获取ID：

```python
# get_group_id.py
import asyncio
from telethon import TelegramClient
from config import Config

async def main():
    config = Config()
    session_path = config.session_path / f"{config.session_name}.session"
    client = TelegramClient(str(session_path), config.api_id, config.api_hash)
    
    await client.start(phone=config.phone_number)
    
    async for dialog in client.iter_dialogs():
        print(f"📋 {dialog.title}")
        print(f"   ID: {dialog.id}")
        print(f"   类型: {'群组' if dialog.is_group else '频道' if dialog.is_channel else '私聊'}")
        print("-" * 40)
    
    await client.disconnect()

asyncio.run(main())
```

```bash
python3 get_group_id.py
```

## 📊 监控和管理

### 查看状态

```bash
# PM2状态
pm2 status download-bot
pm2 logs download-bot

# 系统服务状态
sudo systemctl status telegram-bot
sudo journalctl -u telegram-bot -f
```

### Telegram状态查看

```
/status    # 发送私聊消息查看详细状态
```

显示信息包括：
- 客户端连接状态
- 监听频道数量
- 随机延迟设置
- 下载路径和文件大小限制

## ⚙️ 高级配置

### 多源频道监听

```bash
# 同时监听多个频道/群组
SOURCE_CHANNELS=@channel1,@channel2,-1001234567890,-1005678901234
```

### 性能优化

```bash
# 大文件处理
MAX_FILE_SIZE=2GB                # 最大文件大小
DOWNLOAD_TIMEOUT=3600            # 下载超时（1小时）
MEDIA_GROUP_TIMEOUT=60           # 媒体组等待时间

# 内存优化
max_memory_restart: '2G'         # PM2内存限制
```

### 防检测设置

```bash
# 随机延迟范围
RANDOM_DELAY_MIN=2               # 普通操作最小延迟（秒）
RANDOM_DELAY_MAX=15              # 普通操作最大延迟（秒）
BATCH_DELAY_MIN=30               # 批量操作最小延迟（秒）
BATCH_DELAY_MAX=120              # 批量操作最大延迟（秒）
```

### 队列延迟转发配置

```bash
# 队列基础设置
QUEUE_ENABLED=true               # 启用队列模式
MIN_SEND_DELAY=300               # 最小发送延迟（5分钟）
MAX_SEND_DELAY=7200              # 最大发送延迟（2小时）
QUEUE_CHECK_INTERVAL=30          # 队列检查间隔（30秒）
MAX_QUEUE_SIZE=100               # 最大队列大小

# 分批发送设置
BATCH_SEND_ENABLED=true          # 启用分批发送模式
BATCH_SIZE=5                     # 每批消息数量
BATCH_INTERVAL=1800              # 批次间隔（30分钟）

# 队列持久化
QUEUE_SAVE_PATH=./queue_data.json
AUTO_SAVE_QUEUE=true             # 自动保存队列状态
```

**队列配置说明：**
- **随机模式**：每条消息随机延迟5分钟-2小时发送
- **分批模式**：每5条消息为一批，批次间隔30分钟
- **混合模式**：分批基础上增加随机延迟，更自然

## 🔧 功能详解

### 🔄 双模式转发系统

#### ⚡ 立即转发模式
- **实时响应**：收到消息后立即处理
- **短延迟**：2-15秒随机延迟后转发
- **适用场景**：实时性要求高的场景

#### 📋 队列延迟转发模式
- **智能队列**：消息下载后加入发送队列
- **延迟发送**：5分钟-2小时随机延迟
- **分批处理**：支持批量发送策略
- **重试机制**：失败消息自动重试
- **状态持久化**：程序重启后队列数据不丢失

### 自动监听转发

- **实时监听**：自动监听配置的源频道新消息
- **智能识别**：自动识别媒体组、单媒体、文本消息
- **完整转发**：保持原始格式和标题
- **去标识化**：转发后看起来像原创内容

### 📋 智能队列管理

#### 队列工作流程
1. **消息接收** → 检测转发模式
2. **媒体下载** → 立即下载到本地
3. **队列入队** → 计算发送时间并入队
4. **延迟发送** → 到期后自动发送
5. **文件清理** → 发送成功后清理本地文件

#### 队列特性
- **优先级支持**：支持消息优先级排序
- **智能延迟**：随机延迟 + 分批发送组合
- **错误恢复**：失败重试和状态保存
- **实时监控**：详细的队列状态信息

### 媒体组处理

- **智能等待**：等待媒体组所有文件接收完成
- **动态超时**：根据文件大小智能调整等待时间
- **批量下载**：一次性下载所有媒体文件
- **组合发送**：保持媒体组结构发送

### 大文件支持

- **突破限制**：支持最大2GB文件下载
- **断点续传**：网络中断后自动重试
- **进度监控**：实时显示下载进度
- **错误处理**：详细的错误日志和恢复机制

## 🛡️ 安全建议

### 会话安全

```bash
# 保护会话文件
chmod 600 *.session
chmod 600 .env

# 备份会话文件
cp telegram_session.session telegram_session.session.backup
```

### 运行安全

```bash
# 限制用户权限
sudo useradd -r -s /bin/false telegram-bot
sudo chown telegram-bot:telegram-bot /path/to/bot

# 防火墙设置（如有必要）
sudo ufw allow out 443
sudo ufw allow out 80
```

## 🔧 故障排除

### 常见问题

**1. 验证码问题**
```bash
# 删除会话文件重新验证
rm *.session
python3 main.py
```

**2. 权限错误**
```bash
# 检查频道权限
# 确保账号已加入源频道
# 确保在目标频道有发送权限
```

**3. 大文件下载失败**
```bash
# 检查磁盘空间
df -h

# 检查网络连接
ping api.telegram.org

# 查看详细错误
pm2 logs download-bot --lines 100
```

**4. 内存不足**
```bash
# 增加PM2内存限制
# 编辑 ecosystem.config.js
max_memory_restart: '4G'

# 重启服务
pm2 restart download-bot
```

### 调试模式

```bash
# 开启详细日志
export PYTHONPATH=/path/to/bot
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from main import TelegramUserClient
import asyncio
asyncio.run(TelegramUserClient().run())
"
```

## 📁 项目结构

```
download_bot/
├── main.py                    # 主程序入口
├── config.py                  # 配置管理
├── message_queue.py           # 消息队列管理器 (新增)
├── media_downloader.py        # 媒体下载器
├── bot_handler.py             # 消息处理器
├── requirements.txt           # Python依赖
├── config.env.example         # 配置模板
├── ecosystem.config.js        # PM2配置
├── deploy.sh                  # 部署脚本
├── README.md                  # 说明文档
├── queue_data.json            # 队列数据文件 (自动生成)
├── logs/                      # 日志目录
├── downloads/                 # 下载目录
└── systemd/
    └── telegram-bot.service   # 系统服务配置
```

## 🆚 版本对比

| 功能 | Bot API (旧版) | User API v2.0 | User API v3.0 (当前版) |
|------|---------------|---------------|---------------------|
| 文件大小限制 | 20MB | 2GB | 2GB |
| 控制方式 | 命令行 | Telegram私聊 | Telegram私聊 |
| 转发模式 | 立即转发 | 立即转发 | 双模式(立即/队列) |
| 延迟发送 | ❌ | ❌ | ✅ (5分钟-2小时) |
| 批量处理 | ❌ | ❌ | ✅ |
| 队列管理 | ❌ | ❌ | ✅ |
| 重试机制 | ❌ | ❌ | ✅ |
| 状态持久化 | ❌ | ❌ | ✅ |
| 权限级别 | Bot权限 | 用户权限 | 用户权限 |
| 稳定性 | 一般 | 优秀 | 优秀 |
| 防检测能力 | 低 | 中 | 高 |

## 📈 更新日志

### v3.0.0 (当前版本) - 🚀 智能队列系统
- ✅ **新增消息队列系统** - 支持延迟发送和批量处理
- ✅ **双模式转发** - 立即模式 + 队列模式，运行时切换
- ✅ **智能延迟算法** - 5分钟-2小时随机延迟，避免检测
- ✅ **分批发送功能** - 可配置批次大小和间隔
- ✅ **重试机制** - 失败消息自动重试，提高成功率
- ✅ **状态持久化** - 队列数据自动保存，程序重启不丢失
- ✅ **新增Telegram命令** - `/mode`, `/queue` 等队列管理命令
- ✅ **实时状态监控** - 详细的队列状态和统计信息

### v2.0.0
- ✅ 完全迁移到Telethon User API
- ✅ 支持2GB大文件下载
- ✅ Telegram私聊命令控制
- ✅ 移除命令行交互，纯后台运行
- ✅ 优化PM2配置适配虚拟环境

### v1.0.0 (已废弃)
- Bot API版本
- 20MB文件大小限制
- 命令行交互控制

## 🤝 支持

如遇问题：

1. **查看日志**：`pm2 logs download-bot`
2. **检查配置**：确认 `.env` 文件配置正确
3. **验证权限**：确认账号对频道的访问权限
4. **重启服务**：`pm2 restart download-bot`

---

**🎉 享受智能化的Telegram媒体转发体验！**

> **v3.0.0 特色：** 🚀 智能队列系统 + 🔄 双模式转发 + 📋 延迟发送策略

## 🔄 **是的，必须重启服务！**

修改 `.env` 文件后，**必须重启服务**才能生效，因为：

### 📋 **为什么需要重启**

1. **环境变量在程序启动时读取** - `.env` 文件只在程序启动时被 `python-dotenv` 加载
2. **配置对象在初始化时创建** - `Config()` 类在程序启动时读取环境变量
3. **运行中的程序不会自动重新读取** - 程序运行时不会监控 `.env` 文件变化

### 🔧 **重启方法**

#### **PM2方式（推荐）**
```bash
# 重启指定服务
pm2 restart download-bot

# 或者重启所有服务
pm2 restart all

# 查看状态确认重启成功
pm2 status
```

#### **系统服务方式**
```bash
# 重启服务
sudo systemctl restart telegram-bot

# 查看状态
sudo systemctl status telegram-bot
```

#### **手动方式**
```bash
# 停止程序
pm2 stop download-bot

# 启动程序
pm2 start ecosystem.config.js

# 或者直接
pm2 restart download-bot
```

### 📊 **验证配置生效**

重启后检查配置是否正确加载：

#### **方法1：查看日志**
```bash
<code_block_to_apply_changes_from>
```

日志应该显示：
```
✅ 用户客户端已启动: Toymaster (@ToymasterX)
🎯 User Client 配置信息:
源频道: -1001234567890  # ← 检查这里是否是新配置
目标频道: @your_target_channel
```

#### **方法2：发送状态命令**
```
/status
```

返回的信息会显示当前监听的频道列表。

#### **方法3：测试新配置**
```
/download -1001234567890 0 1   # 测试下载1条消息
```

### ⚠️ **常见问题**

1. **配置没生效**
   ```bash
   # 确认PM2服务名称正确
   pm2 list
   
   # 重启正确的服务
   pm2 restart download-bot  # 或者你的实际服务名
   ```

2. **重启失败**
   ```bash
   # 查看错误日志
   pm2 logs download-bot --err
   
   # 检查配置文件语法
   python3 -c "from config import Config; print('配置检查通过')"
   ```

3. **会话问题**
   ```bash
   # 如果重启后提示验证，可能是会话文件问题
   ls -la *.session
   ```

### 🎯 **最佳实践**

修改配置的完整流程：
```bash
# 1. 修改配置
nano .env

# 2. 验证配置语法
python3 -c "from config import Config; c=Config(); print('配置正确')"

# 3. 重启服务
pm2 restart download-bot

# 4. 查看启动日志
pm2 logs download-bot --lines 10

# 5. 测试功能
# 发送私聊: /status
```

### 📱 **快速测试**

重启后立即测试：
```
/help      # 确认命令处理正常
/status    # 确认新配置已加载
/download <新群组ID> 0 1   # 测试新群组连接
```

**总结：修改 `.env` 后必须重启服务，推荐使用 `pm2 restart download-bot`！** 🔄