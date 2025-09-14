#!/usr/bin/env python3
"""
Telegram Bot for downloading media from source channel and forwarding to target channel
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telegram import Update, Message, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

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


class TelegramMediaBot:
    def __init__(self):
        self.config = Config()
        self.bot_handler = TelegramBotHandler(self.config)
        self.media_downloader = MediaDownloader(self.config)
        self.application = None
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        await update.message.reply_text(
            "🤖 Telegram媒体转发机器人已启动！\n\n"
            f"📡 源频道: {self.config.source_channel_id}\n"
            f"📤 目标频道: {self.config.target_channel_id}\n\n"
            "🔄 自动功能:\n"
            "• 自动监听源频道新消息并转发\n\n"
            "🛠️ 手动命令:\n"
            "• /status - 查看机器人状态\n"
            "• /random_download <数量> - 随机下载N条历史消息\n"
            "• /selective_forward keyword <关键词> - 按关键词转发\n"
            "• /selective_forward type <类型> - 按消息类型转发\n"
            "• /selective_forward recent <数量> - 转发最近N条消息\n\n"
            "📝 使用示例:\n"
            "• /random_download 5\n"
            "• /selective_forward keyword 新品\n"
            "• /selective_forward type photo\n"
            "• /selective_forward recent 10"
        )
        
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        try:
            # 检查机器人状态
            bot_info = await context.bot.get_me()
            status_text = f"🤖 机器人状态: 运行中\n"
            status_text += f"机器人名称: {bot_info.first_name}\n"
            status_text += f"用户名: @{bot_info.username}\n"
            status_text += f"源频道: {self.config.source_channel_id}\n"
            status_text += f"目标频道: {self.config.target_channel_id}\n"
            
            # 检查下载目录
            download_path = Path(self.config.download_path)
            if download_path.exists():
                file_count = len(list(download_path.glob('*')))
                status_text += f"下载目录: {download_path.absolute()}\n"
                status_text += f"已下载文件数: {file_count}\n"
            else:
                status_text += "下载目录: 未创建\n"
                
            await update.message.reply_text(status_text)
            
        except Exception as e:
            logger.error(f"获取状态时出错: {e}")
            await update.message.reply_text(f"获取状态时出错: {str(e)}")
    
    async def random_download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /random_download 命令 - 随机下载N个历史消息"""
        try:
            # 获取参数
            if not context.args:
                await update.message.reply_text(
                    "❌ 请指定要下载的消息数量\n"
                    "用法: /random_download <数量>\n"
                    "例如: /random_download 5"
                )
                return
            
            try:
                count = int(context.args[0])
                if count <= 0 or count > 50:
                    await update.message.reply_text("❌ 数量必须在1-50之间")
                    return
            except ValueError:
                await update.message.reply_text("❌ 请输入有效的数字")
                return
            
            await update.message.reply_text(f"🔄 开始随机下载 {count} 条历史消息...")
            
            # 获取源频道的历史消息
            messages = []
            # 使用替代方法获取历史消息
            try:
                # 尝试获取聊天历史
                chat_history = await context.bot.get_chat_history(
                    chat_id=self.config.source_channel_id, 
                    limit=100
                )
                async for message in chat_history:
                    messages.append(message)
            except AttributeError:
                # 如果 get_chat_history 不存在，使用备用方法
                await update.message.reply_text("🔄 使用替代方法获取历史消息...")
                messages = await self._get_recent_messages_alternative(context.bot, 100)
                if not messages:
                    await update.message.reply_text("❌ 无法获取历史消息，请确保机器人有访问权限")
                    return
            
            if not messages:
                await update.message.reply_text("❌ 源频道没有找到历史消息")
                return
            
            # 随机选择N条消息
            import random
            selected_messages = random.sample(messages, min(count, len(messages)))
            
            success_count = 0
            for i, message in enumerate(selected_messages, 1):
                try:
                    await update.message.reply_text(f"📥 正在处理第 {i}/{len(selected_messages)} 条消息...")
                    
                    # 检查消息是否包含媒体
                    if self.bot_handler.has_media(message):
                        # 下载媒体文件
                        downloaded_files = await self.media_downloader.download_media(message, context.bot)
                        
                        if downloaded_files:
                            # 转发消息到目标频道
                            await self.bot_handler.forward_message(message, downloaded_files, context.bot)
                            success_count += 1
                            logger.info(f"成功转发历史消息 {message.message_id} 到目标频道")
                        else:
                            logger.warning(f"历史消息 {message.message_id} 没有可下载的媒体文件")
                    else:
                        # 转发纯文本消息
                        await self.bot_handler.forward_text_message(message, context.bot)
                        success_count += 1
                        logger.info(f"成功转发历史文本消息 {message.message_id} 到目标频道")
                        
                except Exception as e:
                    logger.error(f"处理历史消息 {message.message_id} 时出错: {e}")
                    continue
            
            await update.message.reply_text(
                f"✅ 随机下载完成！\n"
                f"成功处理: {success_count}/{len(selected_messages)} 条消息"
            )
            
        except Exception as e:
            logger.error(f"随机下载命令执行出错: {e}")
            await update.message.reply_text(f"❌ 随机下载失败: {str(e)}")
    
    async def selective_forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /selective_forward 命令 - 选择性转发"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ 请指定转发条件\n"
                    "用法: /selective_forward <条件>\n"
                    "支持的条件:\n"
                    "• 关键词: /selective_forward keyword <关键词>\n"
                    "• 消息类型: /selective_forward type <photo|video|document|text>\n"
                    "• 最近N条: /selective_forward recent <数量>\n"
                    "例如: /selective_forward keyword 新品\n"
                    "例如: /selective_forward type photo\n"
                    "例如: /selective_forward recent 10"
                )
                return
            
            condition_type = context.args[0].lower()
            
            if condition_type == "keyword" and len(context.args) > 1:
                # 关键词过滤
                keyword = " ".join(context.args[1:])
                await self._forward_by_keyword(update, context, keyword)
                
            elif condition_type == "type" and len(context.args) > 1:
                # 消息类型过滤
                msg_type = context.args[1].lower()
                await self._forward_by_type(update, context, msg_type)
                
            elif condition_type == "recent" and len(context.args) > 1:
                # 最近N条消息
                try:
                    count = int(context.args[1])
                    await self._forward_recent_messages(update, context, count)
                except ValueError:
                    await update.message.reply_text("❌ 请输入有效的数量")
                    
            else:
                await update.message.reply_text("❌ 无效的条件类型")
                
        except Exception as e:
            logger.error(f"选择性转发命令执行出错: {e}")
            await update.message.reply_text(f"❌ 选择性转发失败: {str(e)}")
    
    async def _forward_by_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE, keyword: str):
        """根据关键词转发消息"""
        await update.message.reply_text(f"🔍 正在搜索包含关键词 '{keyword}' 的消息...")
        
        matched_messages = []
        try:
            chat_history = await context.bot.get_chat_history(
                chat_id=self.config.source_channel_id, 
                limit=100
            )
            async for message in chat_history:
                # 检查消息文本或说明文字是否包含关键词
                text_content = ""
                if message.text:
                    text_content += message.text
                if message.caption:
                    text_content += message.caption
                
                if keyword.lower() in text_content.lower():
                    matched_messages.append(message)
        except AttributeError:
            # 使用替代方法
            await update.message.reply_text("🔄 使用替代方法搜索消息...")
            all_messages = await self._get_recent_messages_alternative(context.bot, 100)
            for message in all_messages:
                text_content = ""
                if message.text:
                    text_content += message.text
                if message.caption:
                    text_content += message.caption
                
                if keyword.lower() in text_content.lower():
                    matched_messages.append(message)
        
        if not matched_messages:
            await update.message.reply_text(f"❌ 没有找到包含关键词 '{keyword}' 的消息")
            return
        
        await update.message.reply_text(f"📋 找到 {len(matched_messages)} 条匹配的消息，开始转发...")
        
        success_count = 0
        for i, message in enumerate(matched_messages, 1):
            try:
                await update.message.reply_text(f"📤 正在转发第 {i}/{len(matched_messages)} 条消息...")
                
                if self.bot_handler.has_media(message):
                    downloaded_files = await self.media_downloader.download_media(message, context.bot)
                    if downloaded_files:
                        await self.bot_handler.forward_message(message, downloaded_files, context.bot)
                        success_count += 1
                else:
                    await self.bot_handler.forward_text_message(message, context.bot)
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"转发关键词匹配消息时出错: {e}")
                continue
        
        await update.message.reply_text(
            f"✅ 关键词转发完成！\n"
            f"成功转发: {success_count}/{len(matched_messages)} 条消息"
        )
    
    async def _forward_by_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE, msg_type: str):
        """根据消息类型转发"""
        type_mapping = {
            'photo': 'photo',
            'video': 'video', 
            'document': 'document',
            'text': 'text',
            'audio': 'audio',
            'voice': 'voice'
        }
        
        if msg_type not in type_mapping:
            await update.message.reply_text(
                f"❌ 不支持的消息类型: {msg_type}\n"
                f"支持的类型: {', '.join(type_mapping.keys())}"
            )
            return
        
        await update.message.reply_text(f"🔍 正在搜索 {msg_type} 类型的消息...")
        
        matched_messages = []
        try:
            chat_history = await context.bot.get_chat_history(
                chat_id=self.config.source_channel_id, 
                limit=100
            )
            async for message in chat_history:
                if msg_type == 'text' and message.text and not message.photo and not message.video and not message.document:
                    matched_messages.append(message)
                elif msg_type != 'text' and getattr(message, msg_type, None):
                    matched_messages.append(message)
        except AttributeError:
            # 使用替代方法
            await update.message.reply_text("🔄 使用替代方法搜索消息...")
            all_messages = await self._get_recent_messages_alternative(context.bot, 100)
            for message in all_messages:
                if msg_type == 'text' and message.text and not message.photo and not message.video and not message.document:
                    matched_messages.append(message)
                elif msg_type != 'text' and getattr(message, msg_type, None):
                    matched_messages.append(message)
        
        if not matched_messages:
            await update.message.reply_text(f"❌ 没有找到 {msg_type} 类型的消息")
            return
        
        await update.message.reply_text(f"📋 找到 {len(matched_messages)} 条 {msg_type} 类型的消息，开始转发...")
        
        success_count = 0
        for i, message in enumerate(matched_messages, 1):
            try:
                await update.message.reply_text(f"📤 正在转发第 {i}/{len(matched_messages)} 条消息...")
                
                if self.bot_handler.has_media(message):
                    downloaded_files = await self.media_downloader.download_media(message, context.bot)
                    if downloaded_files:
                        await self.bot_handler.forward_message(message, downloaded_files, context.bot)
                        success_count += 1
                else:
                    await self.bot_handler.forward_text_message(message, context.bot)
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"转发类型匹配消息时出错: {e}")
                continue
        
        await update.message.reply_text(
            f"✅ 类型转发完成！\n"
            f"成功转发: {success_count}/{len(matched_messages)} 条消息"
        )
    
    async def _forward_recent_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
        """转发最近N条消息"""
        if count <= 0 or count > 50:
            await update.message.reply_text("❌ 数量必须在1-50之间")
            return
        
        await update.message.reply_text(f"🔍 正在获取最近 {count} 条消息...")
        
        recent_messages = []
        try:
            chat_history = await context.bot.get_chat_history(
                chat_id=self.config.source_channel_id, 
                limit=count
            )
            async for message in chat_history:
                recent_messages.append(message)
        except AttributeError:
            # 使用替代方法
            await update.message.reply_text("🔄 使用替代方法获取消息...")
            recent_messages = await self._get_recent_messages_alternative(context.bot, count)
        
        if not recent_messages:
            await update.message.reply_text("❌ 没有找到历史消息")
            return
        
        await update.message.reply_text(f"📋 找到 {len(recent_messages)} 条最近消息，开始转发...")
        
        success_count = 0
        for i, message in enumerate(recent_messages, 1):
            try:
                await update.message.reply_text(f"📤 正在转发第 {i}/{len(recent_messages)} 条消息...")
                
                if self.bot_handler.has_media(message):
                    downloaded_files = await self.media_downloader.download_media(message, context.bot)
                    if downloaded_files:
                        await self.bot_handler.forward_message(message, downloaded_files, context.bot)
                        success_count += 1
                else:
                    await self.bot_handler.forward_text_message(message, context.bot)
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"转发最近消息时出错: {e}")
                continue
        
        await update.message.reply_text(
            f"✅ 最近消息转发完成！\n"
            f"成功转发: {success_count}/{len(recent_messages)} 条消息"
        )
    
    async def _get_recent_messages_alternative(self, bot, limit: int = 100):
        """使用替代方法获取最近的消息"""
        try:
            # 获取最近的更新
            updates = await bot.get_updates(limit=limit, timeout=1)
            messages = []
            
            for update_obj in updates:
                message = update_obj.message or update_obj.channel_post
                if message and str(message.chat_id) == str(self.config.source_channel_id).lstrip('@-'):
                    messages.append(message)
            
            # 按时间排序，最新的在前
            messages.sort(key=lambda x: x.date, reverse=True)
            return messages[:limit]
            
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return []
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理接收到的消息"""
        # 处理频道消息和普通消息
        message = update.message or update.channel_post
        
        if not message:
            logger.warning("收到没有消息内容的更新")
            return
        
        # 调试信息：记录收到的消息
        logger.info(f"收到消息 - 频道ID: {message.chat_id}, 消息ID: {message.message_id}")
        logger.info(f"配置的源频道ID: {self.config.source_channel_id}")
        
        # 只处理来自源频道的消息
        # 处理不同的频道ID格式
        source_channel_id = self.config.source_channel_id.lstrip('@-')
        message_chat_id = str(message.chat_id)
        
        # 如果配置的频道ID以@开头，需要获取实际的数字ID
        if self.config.source_channel_id.startswith('@'):
            try:
                chat = await context.bot.get_chat(self.config.source_channel_id)
                source_channel_id = str(chat.id)
                logger.info(f"解析的源频道数字ID: {source_channel_id}")
            except Exception as e:
                logger.error(f"无法获取频道信息: {e}")
                return
        
        if message_chat_id != source_channel_id:
            logger.info(f"消息不是来自源频道，跳过处理。消息频道: {message_chat_id}, 源频道: {source_channel_id}")
            return
            
        try:
            logger.info(f"收到来自源频道的消息: {message.message_id}")
            
            # 检查消息是否包含媒体
            if self.bot_handler.has_media(message):
                # 下载媒体文件
                downloaded_files = await self.media_downloader.download_media(message, context.bot)
                
                if downloaded_files:
                    # 转发消息到目标频道
                    await self.bot_handler.forward_message(message, downloaded_files, context.bot)
                    logger.info(f"成功转发消息 {message.message_id} 到目标频道")
                else:
                    logger.warning(f"消息 {message.message_id} 没有可下载的媒体文件")
            else:
                # 转发纯文本消息
                await self.bot_handler.forward_text_message(message, context.bot)
                logger.info(f"成功转发文本消息 {message.message_id} 到目标频道")
                
        except Exception as e:
            logger.error(f"处理消息 {message.message_id} 时出错: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """错误处理"""
        logger.error(f"更新 {update} 导致错误 {context.error}")
    
    def setup_handlers(self):
        """设置消息处理器"""
        # 命令处理器
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("random_download", self.random_download_command))
        self.application.add_handler(CommandHandler("selective_forward", self.selective_forward_command))
        
        # 消息处理器
        self.application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND, 
            self.handle_message
        ))
        
        # 错误处理器
        self.application.add_error_handler(self.error_handler)
    
    
    async def startup_callback(self, application):
        """启动回调函数"""
        try:
            # 获取机器人信息
            bot_info = await application.bot.get_me()
            logger.info(f"机器人信息: {bot_info.first_name} (@{bot_info.username})")
            logger.info("机器人启动完成，开始监听消息...")
        except Exception as e:
            logger.error(f"启动时获取机器人信息失败: {e}")
    
    async def run(self):
        """运行机器人"""
        try:
            # 创建应用
            self.application = Application.builder().token(self.config.bot_token).build()
            
            # 设置处理器
            self.setup_handlers()
            
            # 添加启动回调
            self.application.post_init = self.startup_callback
            
            # 创建下载目录
            download_path = Path(self.config.download_path)
            download_path.mkdir(exist_ok=True)
            
            logger.info("🤖 Telegram媒体转发机器人启动成功！")
            logger.info(f"源频道: {self.config.source_channel_id}")
            logger.info(f"目标频道: {self.config.target_channel_id}")
            logger.info(f"下载目录: {download_path.absolute()}")
            
            # 启动机器人
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except asyncio.CancelledError:
            logger.info("机器人被取消")
            raise
        except Exception as e:
            logger.error(f"机器人运行出错: {e}")
            raise
        finally:
            # 确保应用被正确关闭
            if self.application:
                try:
                    await self.application.shutdown()
                except Exception as shutdown_error:
                    logger.error(f"关闭应用时出错: {shutdown_error}")


async def main():
    """主函数"""
    bot = TelegramMediaBot()
    await bot.run()


if __name__ == "__main__":
    try:
        # 使用最简单的方法，让 PM2 处理事件循环
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.run(main())
    except ImportError:
        # 如果没有 nest_asyncio，使用备用方法
        try:
            asyncio.run(main())
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # 在 PM2 环境中，直接运行而不创建新的事件循环
                loop = asyncio.get_event_loop()
                loop.run_until_complete(main())
            else:
                raise
    except KeyboardInterrupt:
        logger.info("机器人已停止")
    except asyncio.CancelledError:
        logger.info("机器人被取消")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)
