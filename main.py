#!/usr/bin/env python3
"""
Telegram User Client for downloading media from source channel and forwarding to target channel
使用 Telethon User API 版本 - 支持2GB大文件下载
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import RPCError

from bot_handler import TelegramBotHandler
from media_downloader import MediaDownloader
from config import Config
from message_queue import MessageQueue
from proxy_manager import ProxyManager

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramUserClient:
    def __init__(self):
        self.config = Config()
        self.bot_handler = TelegramBotHandler(self.config)
        self.media_downloader = MediaDownloader(self.config)
        self.client = None
        
        # 消息队列系统
        self.message_queue = MessageQueue(self.config)
        
        # 代理管理器
        self.proxy_manager = ProxyManager(self.config)
        
        # 媒体组缓存 (复用原有逻辑)
        self.media_groups = {}  # {media_group_id: {'messages': [], 'timer': asyncio.Task, 'last_message_time': float, 'status': str, 'download_start_time': float}}
        self.media_group_timeout = 3  # 秒 - 等待更多消息的时间
        self.media_group_max_wait = 60  # 秒 - 等待新消息的最大时间
        self.download_timeout = 3600  # 秒 - 下载超时时间（1小时）
        self.download_progress_check_interval = 60  # 秒 - 下载进度检查间隔（1分钟）
        
        # 随机延迟配置（从配置文件读取）
        self.random_delay_min = self.config.random_delay_min
        self.random_delay_max = self.config.random_delay_max
        self.batch_delay_min = self.config.batch_delay_min
        self.batch_delay_max = self.config.batch_delay_max
        
        # 命令控制
        self.running = True
        self.command_loop_task = None
    
    async def smart_delay(self, delay_type="normal"):
        """智能随机延迟 - 避免被检测为机器人"""
        if delay_type == "normal":
            delay = random.uniform(self.random_delay_min, self.random_delay_max)
        elif delay_type == "batch":
            delay = random.uniform(self.batch_delay_min, self.batch_delay_max)
        elif delay_type == "short":
            delay = random.uniform(1, 5)
        else:
            delay = random.uniform(2, 8)
        
        logger.info(f"⏰ 智能延迟 {delay:.1f} 秒（类型: {delay_type}）")
        await asyncio.sleep(delay)
    
    async def _handle_command_message(self, event):
        """处理Telegram私聊命令"""
        try:
            message_text = event.message.text.strip()
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', 'Unknown')
            
            logger.info(f"📱 处理来自 {sender_name} 的命令: {message_text}")
            
            # 解析命令
            parts = message_text.split()
            command = parts[0][1:].lower()  # 移除 '/' 前缀
            
            if command == "help":
                await self._send_help_message(event)
            elif command == "status":
                await self._send_status_message(event)
            elif command == "download":
                await self._handle_telegram_download_command(event, parts[1:])
            elif command == "queue":
                await self._handle_queue_command(event, parts[1:])
            elif command == "mode":
                await self._handle_mode_command(event, parts[1:])
            elif command == "proxy":
                await self._handle_proxy_command(event, parts[1:])
            else:
                await event.respond("❌ 未知命令，请使用 /help 查看可用命令")
            
        except Exception as e:
            logger.error(f"❌ 处理Telegram命令时出错: {e}")
            await event.respond(f"❌ 命令处理失败: {str(e)}")
    
    async def _send_help_message(self, event):
        """发送帮助消息"""
        help_text = """🎮 **可用命令：**

📥 `/download <频道ID> <天数> [数量]` - 下载指定频道指定日期的消息
   例如: `/download @channel1 0 20` (下载今天的20条消息)
   例如: `/download @channel1 3 50` (下载3天前的50条消息)
   例如: `/download -1001234567890 7 30` (下载7天前的30条消息)

📊 `/status` - 显示当前状态和队列信息
📋 `/queue <操作>` - 队列管理命令
   `/queue status` - 查看队列状态
   `/queue clear` - 清空队列
   `/queue start` - 启动队列处理
   `/queue stop` - 停止队列处理

🔄 `/mode <模式>` - 切换转发模式
   `/mode immediate` - 立即转发模式
   `/mode queue` - 队列延迟转发模式

🔗 `/proxy [操作]` - 代理管理命令
   `/proxy` - 查看代理状态
   `/proxy status` - 查看当前代理
   `/proxy test` - 测试所有代理
   `/proxy rotate` - 强制轮换代理
   `/proxy stats` - 详细统计信息

❓ `/help` - 显示此帮助信息

💡 **提示：**
  • 频道ID可以是 @username 或数字ID格式
  • 天数=0表示今天，1表示昨天，以此类推
  • 数量默认为50条消息
  • 队列模式支持延迟发送和批量处理
  • 系统会自动添加随机延迟避免被检测
  • 只有你本人可以使用这些命令"""
        
        await event.respond(help_text)
    
    async def _send_status_message(self, event):
        """发送状态消息"""
        # 获取队列状态
        queue_status = self.message_queue.get_status()
        
        # 构建基本状态信息
        status_text = f"""📊 **系统状态：**

🔗 客户端连接: {'✅ 已连接' if self.client and self.client.is_connected() else '❌ 未连接'}
📡 监听频道数: {len(self.config.source_channels)}
🎯 目标频道: `{self.config.target_channel_id}`
⏱️ 随机延迟: {self.random_delay_min}-{self.random_delay_max}秒
📦 批量延迟: {self.batch_delay_min}-{self.batch_delay_max}秒
📁 下载路径: `{self.config.download_path}`
📏 最大文件: {self.config.max_file_size / (1024**3):.1f}GB

🔄 **转发模式：** {'📋 队列延迟转发' if queue_status['enabled'] else '⚡ 立即转发'}

📋 **监听的源频道：**
{chr(10).join([f'  • `{ch}`' for ch in self.config.source_channels])}"""

        # 添加队列状态信息
        if queue_status['enabled']:
            next_send_text = "无待发送消息"
            if queue_status['next_send_in_seconds'] is not None:
                minutes = int(queue_status['next_send_in_seconds'] // 60)
                seconds = int(queue_status['next_send_in_seconds'] % 60)
                next_send_text = f"{minutes}分{seconds}秒后"
            
            queue_text = f"""

📋 **队列状态：**
🔄 队列处理: {'✅ 运行中' if queue_status['processing'] else '❌ 已停止'}
📊 待发送: {queue_status['pending_count']} 条消息
⏰ 可发送: {queue_status['ready_count']} 条消息
📈 总统计: {queue_status['total_queued']} 入队 | {queue_status['total_sent']} 已发送 | {queue_status['total_failed']} 失败
⏳ 下次发送: {next_send_text}
📦 队列限制: {queue_status['queue_size_limit']} 条消息
🚀 批量模式: {'✅ 启用' if queue_status['batch_mode'] else '❌ 禁用'}"""
            status_text += queue_text

        status_text += f"""

🤖 **运行状态：** ✅ 正常运行"""
        
        await event.respond(status_text)
    
    async def _handle_telegram_download_command(self, event, args):
        """处理Telegram下载命令"""
        if len(args) < 2:
            await event.respond("""❌ **使用方法：**
`/download <频道ID> <天数> [数量]`

**例如：**
• `/download @channel1 0 20` (下载今天的20条消息)
• `/download @channel1 3 50` (下载3天前的50条消息)""")
            return
            
        try:
            channel_id = args[0]
            days_ago = int(args[1])
            limit = int(args[2]) if len(args) > 2 else 50
            
            await event.respond(f"🚀 开始执行下载命令...\n📡 频道: `{channel_id}`\n📅 日期: {days_ago}天前\n📊 数量: {limit}条消息")
            
            # 执行下载
            count = await self.command_download_by_channel_date(channel_id, days_ago, limit)
            
            await event.respond(f"✅ **下载完成！**\n📊 成功处理了 **{count}** 条消息")
            
        except ValueError:
            await event.respond("❌ 参数错误：天数和数量必须是数字")
        except Exception as e:
            logger.error(f"❌ Telegram下载命令执行失败: {e}")
            await event.respond(f"❌ 下载失败: {str(e)}")
    
    async def _handle_proxy_command(self, event, args):
        """处理代理相关命令"""
        try:
            if not args:
                # 显示当前代理状态
                proxy_info = self.proxy_manager.get_current_proxy_info()
                stats = self.proxy_manager.get_proxy_statistics()
                
                status_msg = f"""🔗 **代理状态**
                
**当前代理:** {proxy_info}

**统计信息:**
• 总代理数: {stats['total_proxies']}
• 当前索引: {stats['current_proxy_index'] + 1}/{stats['total_proxies']}
• 失败代理数: {stats['failed_proxies_count']}
• 轮换启用: {'✅' if stats['rotation_enabled'] else '❌'}

**可用命令:**
• `/proxy status` - 查看代理状态
• `/proxy test` - 测试所有代理
• `/proxy rotate` - 强制轮换代理
• `/proxy stats` - 详细统计信息"""
                
                await event.respond(status_msg)
                return
            
            subcommand = args[0].lower()
            
            if subcommand == "status":
                proxy_info = self.proxy_manager.get_current_proxy_info()
                await event.respond(f"🔗 **当前代理**\n{proxy_info}")
                
            elif subcommand == "test":
                await event.respond("🔍 开始测试所有代理连通性...")
                results = await self.proxy_manager.test_all_proxies()
                
                success_proxies = [name for name, success in results.items() if success]
                failed_proxies = [name for name, success in results.items() if not success]
                
                result_msg = f"""📊 **代理测试结果**

✅ **可用代理 ({len(success_proxies)}):**
{chr(10).join(f'• {name}' for name in success_proxies) if success_proxies else '无'}

❌ **失败代理 ({len(failed_proxies)}):**
{chr(10).join(f'• {name}' for name in failed_proxies) if failed_proxies else '无'}

**总成功率:** {len(success_proxies)}/{len(results)} ({len(success_proxies)/len(results)*100:.1f}%)"""
                
                await event.respond(result_msg)
                
            elif subcommand == "rotate":
                if await self.proxy_manager.force_rotate_proxy():
                    new_proxy_info = self.proxy_manager.get_current_proxy_info()
                    await event.respond(f"✅ **代理已轮换**\n🔗 新代理: {new_proxy_info}")
                else:
                    await event.respond("❌ 代理轮换失败（可能只有一个代理或都不可用）")
                    
            elif subcommand == "stats":
                stats = self.proxy_manager.get_proxy_statistics()
                
                stats_msg = f"""📊 **详细代理统计**

**基本信息:**
• 总代理数: {stats['total_proxies']}
• 当前代理: {stats.get('current_proxy_name', '未知')}
• 代理地址: {stats.get('current_proxy_host', '未知')}:{stats.get('current_proxy_port', '未知')}

**轮换信息:**
• 轮换启用: {'✅' if stats['rotation_enabled'] else '❌'}
• 当前索引: {stats['current_proxy_index'] + 1}/{stats['total_proxies']}
• 失败代理数: {stats['failed_proxies_count']}
• 上次轮换时间: {datetime.fromtimestamp(stats['last_rotation_time']).strftime('%Y-%m-%d %H:%M:%S') if stats['last_rotation_time'] else '从未轮换'}"""
                
                await event.respond(stats_msg)
                
            else:
                await event.respond("❌ 未知的代理子命令\n\n可用命令: status, test, rotate, stats")
                
        except Exception as e:
            logger.error(f"❌ 代理命令执行失败: {e}")
            await event.respond(f"❌ 代理命令失败: {str(e)}")
    
    async def _test_proxy_connection(self):
        """测试代理连接"""
        try:
            import socket
            import socks
            
            logger.info("🔍 正在测试代理连接...")
            
            # 创建socket并设置代理
            sock = socks.socksocket()
            
            # 根据代理类型设置
            if self.config.proxy_type == 'socks5':
                proxy_type = socks.SOCKS5
            elif self.config.proxy_type == 'socks4':
                proxy_type = socks.SOCKS4
            else:  # http
                proxy_type = socks.HTTP
            
            # 设置代理
            if self.config.proxy_username and self.config.proxy_password:
                sock.set_proxy(
                    proxy_type,
                    self.config.proxy_host,
                    self.config.proxy_port,
                    username=self.config.proxy_username,
                    password=self.config.proxy_password
                )
            else:
                sock.set_proxy(
                    proxy_type,
                    self.config.proxy_host,
                    self.config.proxy_port
                )
            
            # 设置超时
            sock.settimeout(self.config.proxy_test_timeout)
            
            # 尝试连接到Telegram的服务器
            try:
                sock.connect(('149.154.167.50', 443))  # Telegram DC1
                sock.close()
                logger.info("✅ 代理连接测试成功")
                return True
            except Exception as connect_error:
                logger.error(f"❌ 代理连接测试失败: {connect_error}")
                return False
                
        except ImportError:
            logger.warning("⚠️ 未安装PySocks，跳过代理测试。请运行: pip install PySocks")
            return True  # 跳过测试，继续执行
        except Exception as e:
            logger.error(f"❌ 代理测试过程出错: {e}")
            return False
    
    async def start_client(self):
        """启动 Telethon 客户端"""
        try:
            # 创建客户端实例
            session_path = self.config.session_path / f"{self.config.session_name}.session"
            
            # 获取代理配置（通过代理管理器）
            proxy_config = await self.proxy_manager.get_current_proxy_config()
            
            if proxy_config:
                logger.info(f"🔗 使用代理连接: {self.proxy_manager.get_current_proxy_info()}")
                
                # 创建带代理的客户端
                self.client = TelegramClient(
                    str(session_path),
                    self.config.api_id,
                    self.config.api_hash,
                    proxy=proxy_config
                )
            else:
                logger.info("🚫 直连模式（未启用代理）")
                self.client = TelegramClient(
                    str(session_path),
                    self.config.api_id,
                    self.config.api_hash
                )
            
            # 启动客户端
            await self.client.start(phone=self.config.phone_number)
            
            # 获取客户端信息
            me = await self.client.get_me()
            logger.info(f"✅ 用户客户端已启动: {me.first_name} (@{me.username})")
            
            # 检查频道权限
            if not await self.bot_handler.check_permissions(self.client):
                raise ValueError("频道权限检查失败")
            
            # 创建下载目录
            download_path = Path(self.config.download_path)
            download_path.mkdir(exist_ok=True)
            
            logger.info("🎯 User Client 配置信息:")
            logger.info(f"源频道: {self.config.source_channel_id}")
            logger.info(f"目标频道: {self.config.target_channel_id}")
            logger.info(f"下载目录: {download_path.absolute()}")
            logger.info(f"最大文件大小: {self.config.max_file_size / (1024*1024*1024):.1f}GB")
            
            return True
            
        except Exception as e:
            logger.error(f"启动用户客户端失败: {e}")
            return False
    
    async def setup_handlers(self):
        """设置事件处理器 - 支持多源频道"""
        try:
            # 获取所有源频道实体
            source_entities = []
            for channel_id in self.config.source_channels:
                try:
                    entity = await self.client.get_entity(channel_id)
                    source_entities.append(entity)
                    logger.info(f"✅ 已连接到源频道: {getattr(entity, 'title', 'Unknown')} ({channel_id})")
                except Exception as e:
                    logger.error(f"❌ 无法连接到频道 {channel_id}: {e}")
                    continue
            
            if not source_entities:
                raise ValueError("没有成功连接到任何源频道")
            
            # 为所有源频道设置新消息事件处理器
            @self.client.on(events.NewMessage(chats=source_entities))
            async def handle_new_message(event):
                # 添加频道信息到日志
                channel_title = getattr(event.chat, 'title', 'Unknown')
                logger.info(f"📨 来自频道 '{channel_title}' 的新消息")
                await self._handle_message(event.message)
            
            # 设置私聊命令处理器（用于手动控制）
            @self.client.on(events.NewMessage(pattern=r'^/(download|status|help)', incoming=True))
            async def command_handler(event):
                if event.is_private:  # 只处理私聊消息
                    logger.info(f"📱 收到私聊命令: {event.message.text}")
                    await self._handle_command_message(event)
            
            logger.info(f"✅ 事件处理器已设置，正在监听 {len(source_entities)} 个源频道的新消息...")
            logger.info("✅ 私聊命令处理器已设置 (/download, /status, /help)")
            
            # 显示监听的频道列表
            for entity in source_entities:
                logger.info(f"   📡 监听频道: {getattr(entity, 'title', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"设置事件处理器失败: {e}")
            raise
    
    async def _handle_message(self, message: Message):
        """处理接收到的消息"""
        try:
            logger.info(f"收到来自源频道的消息: {message.id}")
            
            # 检查是否是媒体组消息
            if message.grouped_id:
                logger.info(f"消息 {message.id} 属于媒体组: {message.grouped_id}")
                await self._handle_media_group_message(message)
            else:
                # 处理单独的消息
                await self._handle_single_message(message)
                
        except Exception as e:
            logger.error(f"处理消息 {message.id} 时出错: {e}")
    
    async def _handle_single_message(self, message: Message):
        """处理单独的消息 - 支持队列系统"""
        logger.info(f"🔄 开始处理单独消息 {message.id}")
        
        # 获取频道标题
        channel_title = getattr(message.chat, 'title', 'Unknown')
        
        # 检查是否启用队列模式
        if self.config.queue_enabled:
            await self._handle_message_with_queue(message, channel_title)
        else:
            await self._handle_message_immediate(message)
    
    async def _handle_message_with_queue(self, message: Message, channel_title: str):
        """使用队列模式处理消息"""
        logger.info(f"📋 队列模式：处理消息 {message.id}")
        
        downloaded_files = []
        
        # 检查消息是否包含媒体
        if self.bot_handler.has_media(message):
            logger.info(f"📥 消息 {message.id} 包含媒体，开始下载...")
            
            try:
                downloaded_files = await self.media_downloader.download_media(message, self.client)
                
                if downloaded_files:
                    logger.info(f"📥 消息 {message.id} 下载完成，共 {len(downloaded_files)} 个文件")
                else:
                    logger.warning(f"⚠️ 消息 {message.id} 没有可下载的媒体文件")
                    
            except Exception as e:
                logger.error(f"❌ 消息 {message.id} 下载失败: {e}")
                return
        
        # 添加到队列（包括纯文本消息）
        success = await self.message_queue.add_message(message, downloaded_files, channel_title)
        if not success:
            # 队列添加失败，清理已下载的文件
            await self._cleanup_files(downloaded_files)
    
    async def _handle_message_immediate(self, message: Message):
        """立即模式处理消息（原有逻辑）"""
        logger.info(f"⚡ 立即模式：处理消息 {message.id}")
        
        # 添加智能随机延迟
        await self.smart_delay("normal")
            
        # 检查消息是否包含媒体
        if self.bot_handler.has_media(message):
            logger.info(f"📥 消息 {message.id} 包含媒体，开始下载...")
            
            try:
                downloaded_files = await self.media_downloader.download_media(message, self.client)
                
                if downloaded_files:
                    logger.info(f"📥 消息 {message.id} 下载完成，共 {len(downloaded_files)} 个文件")
                    logger.info(f"📤 开始转发消息 {message.id} 到目标频道...")
                    
                    # 转发消息到目标频道
                    await self.bot_handler.forward_message(message, downloaded_files, self.client)
                    logger.info(f"🎉 成功转发消息 {message.id} 到目标频道")
                    
                    # 自动清理已成功发布的文件
                    logger.info(f"🧹 开始清理消息 {message.id} 的本地文件...")
                    await self._cleanup_files(downloaded_files)
                    logger.info(f"🧹 消息 {message.id} 文件清理完成")
                else:
                    logger.warning(f"⚠️ 消息 {message.id} 没有可下载的媒体文件")
                    logger.info(f"   可能原因: 文件超过大小限制、网络错误或API限制")
                
            except Exception as e:
                logger.error(f"❌ 消息 {message.id} 下载失败: {e}")
                logger.info(f"   消息将被跳过，不会转发到目标频道")
        else:
            logger.info(f"📝 消息 {message.id} 是纯文本消息")
            # 转发纯文本消息
            await self.bot_handler.forward_text_message(message, self.client)
            logger.info(f"🎉 成功转发文本消息 {message.id} 到目标频道")
    
    async def _handle_media_group_message(self, message: Message):
        """处理媒体组消息 (复用原有逻辑)"""
        media_group_id = message.grouped_id
        current_time = asyncio.get_event_loop().time()
        
        # 如果媒体组不存在，创建新的
        if media_group_id not in self.media_groups:
            self.media_groups[media_group_id] = {
                'messages': [],
                'timer': None,
                'last_message_time': current_time,
                'start_time': current_time,
                'status': 'collecting',  # collecting, downloading, completed
                'download_start_time': None
            }
        
        # 添加消息到媒体组
        self.media_groups[media_group_id]['messages'].append(message)
        self.media_groups[media_group_id]['last_message_time'] = current_time
        logger.info(f"媒体组 {media_group_id} 现在有 {len(self.media_groups[media_group_id]['messages'])} 条消息")
        
        # 取消之前的定时器
        if self.media_groups[media_group_id]['timer']:
            self.media_groups[media_group_id]['timer'].cancel()
        
        # 设置新的定时器
        self.media_groups[media_group_id]['timer'] = asyncio.create_task(
            self._process_media_group_after_timeout(media_group_id)
        )
    
    async def _process_media_group_after_timeout(self, media_group_id: str):
        """智能处理媒体组超时 (复用原有逻辑)"""
        try:
            # 等待超时
            await asyncio.sleep(self.media_group_timeout)
            
            if media_group_id not in self.media_groups:
                return
                
            current_time = asyncio.get_event_loop().time()
            group_data = self.media_groups[media_group_id]
            
            # 状态机处理
            if group_data['status'] == 'collecting':
                # 收集阶段：检查是否还有新消息
                if current_time - group_data['last_message_time'] < self.media_group_timeout:
                    # 还有新消息，重新设置定时器
                    group_data['timer'] = asyncio.create_task(
                        self._process_media_group_after_timeout(media_group_id)
                    )
                    return
                elif current_time - group_data['start_time'] > self.media_group_max_wait:
                    # 超过最大等待时间，强制开始下载
                    logger.warning(f"媒体组 {media_group_id} 等待新消息超时，开始下载")
                    await self._start_media_group_download(media_group_id)
                else:
                    # 开始下载
                    await self._start_media_group_download(media_group_id)
                    
            elif group_data['status'] == 'downloading':
                # 下载阶段：检查下载进度
                download_time = current_time - group_data['download_start_time']
                if download_time > self.download_timeout:
                    logger.error(f"媒体组 {media_group_id} 下载超时（{download_time:.1f}秒），放弃处理")
                    del self.media_groups[media_group_id]
                else:
                    # 继续等待下载完成
                    logger.info(f"媒体组 {media_group_id} 正在下载中，已用时 {download_time:.1f} 秒")
                    group_data['timer'] = asyncio.create_task(
                        self._process_media_group_after_timeout(media_group_id)
                    )
                
        except asyncio.CancelledError:
            logger.info(f"媒体组 {media_group_id} 的处理被取消")
        except Exception as e:
            logger.error(f"处理媒体组 {media_group_id} 时出错: {e}")
            # 清理媒体组缓存
            if media_group_id in self.media_groups:
                del self.media_groups[media_group_id]
    
    async def _start_media_group_download(self, media_group_id: str):
        """开始媒体组下载 (复用原有逻辑)"""
        try:
            if media_group_id not in self.media_groups:
                return
                
            group_data = self.media_groups[media_group_id]
            messages = group_data['messages']
            
            # 更新状态为下载中
            group_data['status'] = 'downloading'
            group_data['download_start_time'] = asyncio.get_event_loop().time()
            
            logger.info(f"开始下载媒体组 {media_group_id}，包含 {len(messages)} 条消息")
            
            # 添加智能随机延迟
            await self.smart_delay("normal")
            
            # 设置下载进度监控
            group_data['timer'] = asyncio.create_task(
                self._process_media_group_after_timeout(media_group_id)
            )
            
            # 下载所有媒体文件
            all_downloaded_files = []
            total_messages = len(messages)
            
            logger.info(f"📥 开始下载媒体组 {media_group_id} 的所有文件...")
            for i, message in enumerate(messages, 1):
                if self.bot_handler.has_media(message):
                    logger.info(f"📥 下载媒体组 {media_group_id} 第 {i}/{total_messages} 个文件")
                    downloaded_files = await self.media_downloader.download_media(message, self.client)
                    all_downloaded_files.extend(downloaded_files)
                    logger.info(f"✅ 完成下载第 {i}/{total_messages} 个文件，共获得 {len(downloaded_files)} 个文件")
            
            logger.info(f"📥 媒体组 {media_group_id} 所有文件下载完成，共 {len(all_downloaded_files)} 个文件")
            
            # 取消进度监控定时器
            if group_data['timer']:
                group_data['timer'].cancel()
            
            # 更新状态为完成
            group_data['status'] = 'completed'
            
            if all_downloaded_files:
                # 找到包含文案的消息，如果没有则使用第一条消息
                main_message = messages[0]
                for message in messages:
                    if message.text:
                        main_message = message
                        logger.info(f"📝 使用消息 {message.id} 的文案作为媒体组说明")
                        break
                
                logger.info(f"📤 开始转发媒体组 {media_group_id} 到目标频道...")
                
                try:
                    await self.bot_handler.forward_message(main_message, all_downloaded_files, self.client)
                    
                    download_time = asyncio.get_event_loop().time() - group_data['download_start_time']
                    logger.info(f"🎉 成功转发媒体组 {media_group_id} 到目标频道！包含 {len(all_downloaded_files)} 个文件，总耗时 {download_time:.1f} 秒")
                    
                    # 自动清理已成功发布的文件
                    logger.info(f"🧹 开始清理媒体组 {media_group_id} 的本地文件...")
                    await self._cleanup_files(all_downloaded_files)
                    logger.info(f"🧹 媒体组 {media_group_id} 文件清理完成")
                    
                except Exception as e:
                    logger.error(f"❌ 转发媒体组 {media_group_id} 失败: {e}")
                    logger.info(f"🧹 转发失败，清理本地文件...")
                    await self._cleanup_files(all_downloaded_files)
                    raise
            else:
                logger.warning(f"⚠️ 媒体组 {media_group_id} 没有可下载的媒体文件")
            
            # 清理媒体组缓存
            del self.media_groups[media_group_id]
            
        except Exception as e:
            logger.error(f"下载媒体组 {media_group_id} 时出错: {e}")
            # 清理媒体组缓存
            if media_group_id in self.media_groups:
                del self.media_groups[media_group_id]
    
    async def _cleanup_files(self, file_infos: list):
        """清理已成功发布的文件 (复用原有逻辑)"""
        import os
        for file_info in file_infos:
            try:
                # 处理新的文件格式 {'path': Path, 'type': str}
                if isinstance(file_info, dict):
                    file_path = file_info['path']
                else:
                    # 向后兼容旧格式
                    file_path = file_info
                    
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"已清理文件: {file_path}")
            except Exception as e:
                logger.error(f"清理文件 {file_info} 失败: {e}")
    
    async def download_history_messages(self, limit: int = 100, offset_days: int = 0):
        """下载历史消息 - 支持按时间范围和数量限制"""
        try:
            from datetime import datetime, timedelta
            
            logger.info(f"🔄 开始下载最近 {limit} 条历史消息（{offset_days}天前开始）...")
            
            # 获取源频道实体
            source_entity = await self.client.get_entity(self.config.source_channel_id)
            
            # 计算开始时间
            if offset_days > 0:
                offset_date = datetime.now() - timedelta(days=offset_days)
                logger.info(f"📅 获取 {offset_date.strftime('%Y-%m-%d')} 之后的消息")
            else:
                offset_date = None
            
            # 获取历史消息
            messages = []
            async for message in self.client.iter_messages(
                source_entity, 
                limit=limit,
                offset_date=offset_date
            ):
                if self.bot_handler.has_media(message) or message.text:
                    messages.append(message)
            
            if not messages:
                logger.warning("❌ 没有找到符合条件的历史消息")
                return 0
            
            logger.info(f"📋 找到 {len(messages)} 条历史消息，开始处理...")
            
            success_count = 0
            for i, message in enumerate(messages, 1):
                try:
                    logger.info(f"📥 正在处理第 {i}/{len(messages)} 条历史消息 (ID: {message.id})...")
                    
                    # 检查消息是否包含媒体
                    if self.bot_handler.has_media(message):
                        # 下载媒体文件
                        downloaded_files = await self.media_downloader.download_media(message, self.client)
                        
                        if downloaded_files:
                            # 转发消息到目标频道
                            await self.bot_handler.forward_message(message, downloaded_files, self.client)
                            success_count += 1
                            logger.info(f"✅ 成功转发历史媒体消息 {message.id}")
                            
                            # 自动清理已成功发布的文件
                            await self._cleanup_files(downloaded_files)
                        else:
                            logger.warning(f"⚠️ 历史消息 {message.id} 没有可下载的媒体文件")
                    else:
                        # 转发纯文本消息
                        await self.bot_handler.forward_text_message(message, self.client)
                        success_count += 1
                        logger.info(f"✅ 成功转发历史文本消息 {message.id}")
                    
                    # 添加智能延迟避免频率限制
                    await self.smart_delay("short")
                        
                except Exception as e:
                    logger.error(f"❌ 处理历史消息 {message.id} 时出错: {e}")
                    continue
            
            logger.info(f"🎉 历史消息处理完成！成功处理: {success_count}/{len(messages)} 条消息")
            return success_count
            
        except Exception as e:
            logger.error(f"❌ 下载历史消息时出错: {e}")
            return 0
    
    async def manual_download_command(self, count: int = 5):
        """手动下载命令 - 随机下载N个历史消息"""
        return await self.download_history_messages(limit=count)
    
    async def command_download_by_channel_date(self, channel_id: str, days_ago: int = 0, limit: int = 50):
        """手动命令：下载指定频道指定日期的消息"""
        try:
            logger.info(f"🎮 手动下载命令：频道 {channel_id}，{days_ago}天前的消息，限制 {limit} 条")
            
            # 获取频道实体
            try:
                entity = await self.client.get_entity(channel_id)
                logger.info(f"✅ 已连接到频道: {getattr(entity, 'title', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ 无法连接到频道 {channel_id}: {e}")
                return 0
            
            # 计算日期范围
            if days_ago > 0:
                target_date = datetime.now() - timedelta(days=days_ago)
                end_date = target_date + timedelta(days=1)  # 第二天开始
                logger.info(f"📅 下载日期范围: {target_date.strftime('%Y-%m-%d')} 的消息")
            else:
                target_date = None
                end_date = None
                logger.info(f"📅 下载最新的 {limit} 条消息")
            
            # 获取消息
            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit * 2,  # 多获取一些，因为要过滤
                offset_date=end_date if end_date else None
            ):
                # 如果指定了日期，检查消息日期
                if target_date:
                    if message.date.date() != target_date.date():
                        continue
                
                # 只处理有内容的消息
                if self.bot_handler.has_media(message) or message.text:
                    messages.append(message)
                    if len(messages) >= limit:
                        break
            
            if not messages:
                logger.warning(f"❌ 在频道 {channel_id} 中没有找到符合条件的消息")
                return 0
            
            logger.info(f"📋 找到 {len(messages)} 条符合条件的消息，开始处理...")
            
            # 添加批量操作延迟
            await self.smart_delay("batch")
            
            success_count = 0
            for i, message in enumerate(messages, 1):
                try:
                    logger.info(f"📥 处理第 {i}/{len(messages)} 条消息 (ID: {message.id}, 时间: {message.date})")
                    
                    # 智能延迟
                    await self.smart_delay("short")
                    
                    # 处理消息
                    if self.bot_handler.has_media(message):
                        downloaded_files = await self.media_downloader.download_media(message, self.client)
                        if downloaded_files:
                            await self.bot_handler.forward_message(message, downloaded_files, self.client)
                            await self._cleanup_files(downloaded_files)
                            success_count += 1
                            logger.info(f"✅ 成功转发媒体消息 {message.id}")
                    else:
                        await self.bot_handler.forward_text_message(message, self.client)
                        success_count += 1
                        logger.info(f"✅ 成功转发文本消息 {message.id}")
                        
                except Exception as e:
                    logger.error(f"❌ 处理消息 {message.id} 时出错: {e}")
                    continue
            
            logger.info(f"🎉 手动下载完成！成功处理: {success_count}/{len(messages)} 条消息")
            return success_count
            
        except Exception as e:
            logger.error(f"❌ 手动下载命令执行出错: {e}")
            return 0
    
    async def _handle_queue_command(self, event, args):
        """处理队列管理命令"""
        if not args:
            await event.respond("""❌ **使用方法：**
`/queue <操作>`

**可用操作：**
• `/queue status` - 查看详细队列状态
• `/queue clear` - 清空队列
• `/queue start` - 启动队列处理
• `/queue stop` - 停止队列处理""")
            return
        
        operation = args[0].lower()
        
        try:
            if operation == "status":
                await self._send_queue_status(event)
            elif operation == "clear":
                count = self.message_queue.clear_queue()
                await event.respond(f"🧹 **队列已清空**\n移除了 {count} 条待发送消息")
            elif operation == "start":
                if not self.message_queue.processing:
                    await self.message_queue.start_processing(self.bot_handler, self.client)
                    await event.respond("🚀 **队列处理器已启动**")
                else:
                    await event.respond("⚠️ 队列处理器已在运行")
            elif operation == "stop":
                if self.message_queue.processing:
                    await self.message_queue.stop_processing()
                    await event.respond("🛑 **队列处理器已停止**")
                else:
                    await event.respond("⚠️ 队列处理器已停止")
            else:
                await event.respond("❌ 未知队列操作，请使用 `/queue` 查看可用操作")
        
        except Exception as e:
            logger.error(f"❌ 队列命令执行失败: {e}")
            await event.respond(f"❌ 操作失败: {str(e)}")
    
    async def _send_queue_status(self, event):
        """发送详细队列状态"""
        queue_status = self.message_queue.get_status()
        
        if not queue_status['enabled']:
            await event.respond("📋 **队列状态：** ❌ 队列模式未启用\n使用 `/mode queue` 启用队列模式")
            return
        
        # 下次发送时间格式化
        next_send_text = "无待发送消息"
        if queue_status['next_send_in_seconds'] is not None:
            total_seconds = int(queue_status['next_send_in_seconds'])
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                next_send_text = f"{hours}时{minutes}分{seconds}秒后"
            elif minutes > 0:
                next_send_text = f"{minutes}分{seconds}秒后"
            else:
                next_send_text = f"{seconds}秒后"
        
        status_text = f"""📋 **详细队列状态：**

🔄 **处理状态：** {'✅ 运行中' if queue_status['processing'] else '❌ 已停止'}
📊 **队列统计：**
  • 待发送消息: {queue_status['pending_count']} 条
  • 可立即发送: {queue_status['ready_count']} 条
  • 队列容量: {queue_status['pending_count']}/{queue_status['queue_size_limit']} 条

📈 **历史统计：**
  • 总入队: {queue_status['total_queued']} 条
  • 已发送: {queue_status['total_sent']} 条
  • 发送失败: {queue_status['total_failed']} 条
  • 成功率: {(queue_status['total_sent']/(queue_status['total_queued']+0.001)*100):.1f}%

⏰ **时间信息：**
  • 下次发送: {next_send_text}
  • 检查间隔: {self.config.queue_check_interval} 秒

🚀 **配置信息：**
  • 发送延迟: {self.config.min_send_delay//60}-{self.config.max_send_delay//60} 分钟
  • 批量模式: {'✅ 启用' if queue_status['batch_mode'] else '❌ 禁用'}"""

        if queue_status['batch_mode']:
            status_text += f"""
  • 批次大小: {self.config.batch_size} 条消息
  • 批次间隔: {self.config.batch_interval//60} 分钟"""

        await event.respond(status_text)
    
    async def _handle_mode_command(self, event, args):
        """处理模式切换命令"""
        if not args:
            current_mode = "队列延迟转发" if self.config.queue_enabled else "立即转发"
            await event.respond(f"""🔄 **当前转发模式：** {current_mode}

**切换模式：**
• `/mode immediate` - 立即转发模式
• `/mode queue` - 队列延迟转发模式

**模式说明：**
• **立即转发：** 收到消息后立即下载并转发（2-15秒延迟）
• **队列转发：** 收到消息后下载并加入队列，延迟一段时间后发送（5分钟-2小时）""")
            return
        
        mode = args[0].lower()
        
        try:
            if mode == "immediate":
                # 切换到立即模式
                if self.config.queue_enabled:
                    # 停止队列处理器
                    await self.message_queue.stop_processing()
                    self.config.queue_enabled = False
                    await event.respond("""⚡ **已切换到立即转发模式**

✅ 消息将在收到后立即处理和转发
⏰ 延迟：2-15秒随机延迟
📋 队列处理器已停止""")
                else:
                    await event.respond("⚠️ 当前已是立即转发模式")
            
            elif mode == "queue":
                # 切换到队列模式
                if not self.config.queue_enabled:
                    self.config.queue_enabled = True
                    # 启动队列处理器
                    await self.message_queue.start_processing(self.bot_handler, self.client)
                    await event.respond(f"""📋 **已切换到队列延迟转发模式**

✅ 消息将下载后加入队列延迟发送
⏰ 延迟：{self.config.min_send_delay//60}-{self.config.max_send_delay//60}分钟随机延迟
🚀 队列处理器已启动
📊 队列容量：{self.config.max_queue_size}条消息""")
                else:
                    await event.respond("⚠️ 当前已是队列延迟转发模式")
            
            else:
                await event.respond("❌ 未知模式，请使用 `immediate` 或 `queue`")
        
        except Exception as e:
            logger.error(f"❌ 模式切换失败: {e}")
            await event.respond(f"❌ 模式切换失败: {str(e)}")
    
    async def run(self):
        """运行用户客户端"""
        try:
            logger.info("🚀 启动 Telegram User Client...")
            
            # 启动客户端
            if not await self.start_client():
                raise RuntimeError("客户端启动失败")
            
            # 设置事件处理器
            await self.setup_handlers()
            
            # 启动消息队列处理器（如果启用）
            if self.config.queue_enabled:
                await self.message_queue.start_processing(self.bot_handler, self.client)
                logger.info("🚀 消息队列处理器已启动")
            else:
                logger.info("⚡ 使用立即转发模式")
            
            logger.info("🎯 User Client 已启动，开始监听消息...")
            logger.info("📋 功能说明:")
            logger.info(f"  • 自动监听 {len(self.config.source_channels)} 个源频道新消息并转发")
            logger.info("  • 支持2GB大文件下载（无20MB限制）")
            logger.info("  • 自动处理媒体组消息")
            logger.info("  • 支持所有媒体类型")
            logger.info("  • 支持历史消息批量下载")
            logger.info(f"  • 转发模式: {'📋 队列延迟转发' if self.config.queue_enabled else '⚡ 立即转发'}")
            
            # 显示所有监听的频道
            logger.info("📡 监听的源频道:")
            for channel in self.config.source_channels:
                logger.info(f"   - {channel}")
            
            # 显示队列配置信息
            if self.config.queue_enabled:
                logger.info("📋 队列配置:")
                logger.info(f"   - 发送延迟: {self.config.min_send_delay//60}-{self.config.max_send_delay//60} 分钟")
                logger.info(f"   - 队列大小: {self.config.max_queue_size} 条消息")
                logger.info(f"   - 批量模式: {'启用' if self.config.batch_send_enabled else '禁用'}")
                if self.config.batch_send_enabled:
                    logger.info(f"   - 批次大小: {self.config.batch_size} 条消息")
                    logger.info(f"   - 批次间隔: {self.config.batch_interval//60} 分钟")
            
            logger.info("🤖 程序将在后台持续运行...")
            logger.info("💬 私聊发送命令控制: /help, /status, /download, /queue")
            
            # 运行客户端直到断开连接（纯后台模式）
            await self.client.run_until_disconnected()
            
        except asyncio.CancelledError:
            logger.info("用户客户端被取消")
            raise
        except Exception as e:
            logger.error(f"用户客户端运行出错: {e}")
            raise
        finally:
            # 停止消息队列处理器
            if self.config.queue_enabled:
                await self.message_queue.stop_processing()
                logger.info("🛑 消息队列处理器已停止")
            
            # 确保客户端被正确关闭
            if self.client and self.client.is_connected():
                try:
                    await self.client.disconnect()
                    logger.info("用户客户端已断开连接")
                except Exception as disconnect_error:
                    logger.error(f"断开客户端连接时出错: {disconnect_error}")


async def main():
    """主函数"""
    user_client = TelegramUserClient()
    await user_client.run()


def handle_signal(signum, frame):
    """信号处理"""
    logger.info(f"收到信号 {signum}，准备退出...")
    sys.exit(0)


if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # 运行用户客户端
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户客户端已停止")
    except asyncio.CancelledError:
        logger.info("用户客户端被取消")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)