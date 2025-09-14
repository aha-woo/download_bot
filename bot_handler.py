"""
Telegram Bot 消息处理模块
"""

import logging
from typing import List, Optional
from pathlib import Path

from telegram import Update, Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.error import TelegramError

from config import Config

logger = logging.getLogger(__name__)


class TelegramBotHandler:
    """Telegram Bot 消息处理器"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def has_media(self, message: Message) -> bool:
        """检查消息是否包含媒体文件"""
        return any([
            message.photo,
            message.video,
            message.document,
            message.audio,
            message.voice,
            message.video_note,
            message.animation,
            message.sticker
        ])
    
    def get_media_type(self, message: Message) -> Optional[str]:
        """获取媒体类型"""
        if message.photo:
            return 'photo'
        elif message.video:
            return 'video'
        elif message.document:
            return 'document'
        elif message.audio:
            return 'audio'
        elif message.voice:
            return 'voice'
        elif message.video_note:
            return 'video_note'
        elif message.animation:
            return 'animation'
        elif message.sticker:
            return 'sticker'
        return None
    
    async def forward_text_message(self, message: Message, bot=None):
        """发送纯文本消息（作为原创内容）"""
        try:
            # 获取bot实例
            bot_instance = bot or getattr(message, 'bot', None)
            if not bot_instance:
                raise ValueError("无法获取bot实例")
            
            # 构建消息文本
            forward_text = self._build_forward_text(message)
            
            # 发送到目标频道
            await bot_instance.send_message(
                chat_id=self.config.target_channel_id,
                text=forward_text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            
            logger.info(f"成功转发文本消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发文本消息失败: {e}")
            raise
    
    async def forward_message(self, message: Message, downloaded_files: List[dict], bot=None):
        """发送包含媒体的消息（作为原创内容）"""
        try:
            # 获取bot实例
            bot_instance = bot or getattr(message, 'bot', None)
            if not bot_instance:
                raise ValueError("无法获取bot实例")
            
            # 构建消息文本
            forward_text = self._build_forward_text(message)
            
            # 根据媒体类型和数量选择转发方式
            media_type = self.get_media_type(message)
            
            if len(downloaded_files) == 1:
                # 单个媒体文件
                await self._send_single_media(message, downloaded_files[0], forward_text, bot_instance)
            else:
                # 多个媒体文件
                await self._send_media_group(message, downloaded_files, forward_text, bot_instance)
            
            logger.info(f"成功转发媒体消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发媒体消息失败: {e}")
            raise
    
    async def _send_single_media(self, message: Message, file_info: dict, caption: str, bot):
        """发送单个媒体文件"""
        file_path = file_info['path']
        media_type = file_info['type']
        
        with open(file_path, 'rb') as file:
            if media_type == 'photo':
                await bot.send_photo(
                    chat_id=self.config.target_channel_id,
                    photo=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'video':
                await bot.send_video(
                    chat_id=self.config.target_channel_id,
                    video=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'document':
                await bot.send_document(
                    chat_id=self.config.target_channel_id,
                    document=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'audio':
                await bot.send_audio(
                    chat_id=self.config.target_channel_id,
                    audio=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'voice':
                await bot.send_voice(
                    chat_id=self.config.target_channel_id,
                    voice=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'video_note':
                await bot.send_video_note(
                    chat_id=self.config.target_channel_id,
                    video_note=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'animation':
                await bot.send_animation(
                    chat_id=self.config.target_channel_id,
                    animation=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'sticker':
                await bot.send_sticker(
                    chat_id=self.config.target_channel_id,
                    sticker=file
                )
    
    async def _send_media_group(self, message: Message, file_infos: List[dict], caption: str, bot):
        """发送媒体组"""
        media_list = []
        
        for i, file_info in enumerate(file_infos):
            file_path = file_info['path']
            media_type = file_info['type']
            
            with open(file_path, 'rb') as file:
                # 只在第一个媒体上添加说明文字
                if i == 0 and caption:
                    if media_type == 'photo':
                        media = InputMediaPhoto(media=file, caption=caption, parse_mode='HTML')
                    elif media_type == 'video':
                        media = InputMediaVideo(media=file, caption=caption, parse_mode='HTML')
                    else:
                        media = InputMediaDocument(media=file, caption=caption, parse_mode='HTML')
                else:
                    if media_type == 'photo':
                        media = InputMediaPhoto(media=file)
                    elif media_type == 'video':
                        media = InputMediaVideo(media=file)
                    else:
                        media = InputMediaDocument(media=file)
                
                media_list.append(media)
        
        # 发送媒体组
        await bot.send_media_group(
            chat_id=self.config.target_channel_id,
            media=media_list
        )
    
    def _build_forward_text(self, message: Message) -> str:
        """构建消息文本（不显示转发信息）"""
        text_parts = []
        
        # 添加原始消息文本
        if message.text:
            text_parts.append(message.text)
        elif message.caption:
            text_parts.append(message.caption)
        
        # 不再添加转发信息，让消息看起来像原创内容
        
        return '\n'.join(text_parts) if text_parts else ""
    
    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        if not text:
            return ""
        
        escape_chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        }
        
        for char, escaped in escape_chars.items():
            text = text.replace(char, escaped)
        
        return text
