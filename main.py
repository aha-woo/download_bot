#!/usr/bin/env python3
"""
Telegram Bot for downloading media from source channel and forwarding to target channel
"""

import asyncio
import logging
import os
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
            "🤖 Telegram媒体转发机器人已启动！\n"
            f"源频道: {self.config.source_channel_id}\n"
            f"目标频道: {self.config.target_channel_id}\n"
            "机器人将自动监听源频道的消息并转发到目标频道。"
        )
        
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        try:
            # 检查机器人状态
            bot_info = await self.application.bot.get_me()
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理接收到的消息"""
        message = update.message
        
        # 只处理来自源频道的消息
        if str(message.chat_id) != self.config.source_channel_id.lstrip('@-'):
            return
            
        try:
            logger.info(f"收到来自源频道的消息: {message.message_id}")
            
            # 检查消息是否包含媒体
            if self.bot_handler.has_media(message):
                # 下载媒体文件
                downloaded_files = await self.media_downloader.download_media(message)
                
                if downloaded_files:
                    # 转发消息到目标频道
                    await self.bot_handler.forward_message(message, downloaded_files)
                    logger.info(f"成功转发消息 {message.message_id} 到目标频道")
                else:
                    logger.warning(f"消息 {message.message_id} 没有可下载的媒体文件")
            else:
                # 转发纯文本消息
                await self.bot_handler.forward_text_message(message)
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
        
        # 消息处理器
        self.application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND, 
            self.handle_message
        ))
        
        # 错误处理器
        self.application.add_error_handler(self.error_handler)
    
    async def check_bot_permissions(self):
        """检查机器人在频道中的权限"""
        try:
            # 检查源频道权限
            source_chat = await self.application.bot.get_chat(self.config.source_channel_id)
            logger.info(f"源频道信息: {source_chat.title} (ID: {source_chat.id})")
            
            # 检查目标频道权限
            target_chat = await self.application.bot.get_chat(self.config.target_channel_id)
            logger.info(f"目标频道信息: {target_chat.title} (ID: {target_chat.id})")
            
            # 检查机器人在目标频道中的权限
            bot_member = await self.application.bot.get_chat_member(
                self.config.target_channel_id, 
                self.application.bot.id
            )
            
            if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.MEMBER]:
                logger.warning(f"机器人在目标频道 {self.config.target_channel_id} 中权限不足")
                return False
                
            return True
            
        except TelegramError as e:
            logger.error(f"检查权限时出错: {e}")
            return False
    
    async def run(self):
        """运行机器人"""
        try:
            # 创建应用
            self.application = Application.builder().token(self.config.bot_token).build()
            
            # 设置处理器
            self.setup_handlers()
            
            # 检查权限
            if not await self.check_bot_permissions():
                logger.error("机器人权限检查失败，请确保机器人已添加到频道并具有适当权限")
                return
            
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
            
        except Exception as e:
            logger.error(f"机器人运行出错: {e}")
            raise


async def main():
    """主函数"""
    bot = TelegramMediaBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("机器人已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)
