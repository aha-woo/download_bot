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

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import TelegramError

from bot_handler import TelegramBotHandler
from media_downloader import MediaDownloader
from config import Config

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
        
        # 媒体组缓存 (复用原有逻辑)
        self.media_groups = {}  # {media_group_id: {'messages': [], 'timer': asyncio.Task, 'last_message_time': float, 'status': str, 'download_start_time': float}}
        self.media_group_timeout = 3  # 秒 - 等待更多消息的时间
        self.media_group_max_wait = 60  # 秒 - 等待新消息的最大时间
        self.download_timeout = 3600  # 秒 - 下载超时时间（1小时）
        self.download_progress_check_interval = 60  # 秒 - 下载进度检查间隔（1分钟）
        
    async def start_client(self):
        """启动 Telethon 客户端"""
        try:
            # 创建客户端实例
            session_path = self.config.session_path / f"{self.config.session_name}.session"
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
        """设置事件处理器"""
        try:
            # 获取源频道实体
            source_entity = await self.client.get_entity(self.config.source_channel_id)
            logger.info(f"✅ 已连接到源频道: {getattr(source_entity, 'title', 'Unknown')}")
            
            # 新消息事件处理器
            @self.client.on(events.NewMessage(chats=source_entity))
            async def handle_new_message(event):
                await self._handle_message(event.message)
            
            logger.info("✅ 事件处理器已设置，开始监听新消息...")
            
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
        """处理单独的消息 (复用原有逻辑)"""
        logger.info(f"🔄 开始处理单独消息 {message.id}")
        
        # 添加随机延迟（1-10秒）
        delay = random.uniform(1, 10)
        logger.info(f"⏰ 消息 {message.id} 将在 {delay:.1f} 秒后发布")
        await asyncio.sleep(delay)
            
            # 检查消息是否包含媒体
        if self.bot_handler.has_media(message):
            logger.info(f"📥 消息 {message.id} 包含媒体，开始下载...")
            
                # 下载媒体文件
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
            
            # 添加随机延迟（1-10秒）
            delay = random.uniform(1, 10)
            logger.info(f"媒体组 {media_group_id} 将在 {delay:.1f} 秒后开始下载")
            await asyncio.sleep(delay)
            
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
    
    async def manual_download_command(self, count: int = 5):
        """手动下载命令 - 随机下载N个历史消息"""
        try:
            logger.info(f"🔄 开始手动随机下载 {count} 条历史消息...")
            
            # 获取源频道实体
            source_entity = await self.client.get_entity(self.config.source_channel_id)
            
            # 获取历史消息
            messages = []
            async for message in self.client.iter_messages(source_entity, limit=100):
                if self.bot_handler.has_media(message) or message.text:
                    messages.append(message)
            
            if not messages:
                logger.warning("❌ 源频道没有找到历史消息")
                return 0
            
            # 随机选择N条消息
            selected_messages = random.sample(messages, min(count, len(messages)))
            
            success_count = 0
            for i, message in enumerate(selected_messages, 1):
                try:
                    logger.info(f"📥 正在处理第 {i}/{len(selected_messages)} 条消息...")
                    
                    # 检查消息是否包含媒体
                    if self.bot_handler.has_media(message):
                        # 下载媒体文件
                        downloaded_files = await self.media_downloader.download_media(message, self.client)
                        
                        if downloaded_files:
                            # 转发消息到目标频道
                            await self.bot_handler.forward_message(message, downloaded_files, self.client)
                            success_count += 1
                            logger.info(f"成功转发历史消息 {message.id} 到目标频道")
                            
                            # 自动清理已成功发布的文件
                            await self._cleanup_files(downloaded_files)
                        else:
                            logger.warning(f"历史消息 {message.id} 没有可下载的媒体文件")
                    else:
                        # 转发纯文本消息
                        await self.bot_handler.forward_text_message(message, self.client)
                        success_count += 1
                        logger.info(f"成功转发历史文本消息 {message.id} 到目标频道")
                        
                except Exception as e:
                    logger.error(f"处理历史消息 {message.id} 时出错: {e}")
                    continue
            
            logger.info(f"✅ 手动下载完成！成功处理: {success_count}/{len(selected_messages)} 条消息")
            return success_count
            
        except Exception as e:
            logger.error(f"手动下载命令执行出错: {e}")
            return 0
    
    async def run(self):
        """运行用户客户端"""
        try:
            logger.info("🚀 启动 Telegram User Client...")
            
            # 启动客户端
            if not await self.start_client():
                raise RuntimeError("客户端启动失败")
            
            # 设置事件处理器
            await self.setup_handlers()
            
            logger.info("🎯 User Client 已启动，开始监听消息...")
            logger.info("📋 功能说明:")
            logger.info("  • 自动监听源频道新消息并转发")
            logger.info("  • 支持2GB大文件下载（无20MB限制）")
            logger.info("  • 自动处理媒体组消息")
            logger.info("  • 支持所有媒体类型")
            
            # 运行客户端直到断开连接
            await self.client.run_until_disconnected()
            
        except asyncio.CancelledError:
            logger.info("用户客户端被取消")
            raise
        except Exception as e:
            logger.error(f"用户客户端运行出错: {e}")
            raise
        finally:
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