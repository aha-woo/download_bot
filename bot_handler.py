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
    
    async def forward_text_message(self, message: Message):
        """转发纯文本消息"""
        try:
            # 构建转发消息的文本
            forward_text = self._build_forward_text(message)
            
            # 发送到目标频道
            await message.bot.send_message(
                chat_id=self.config.target_channel_id,
                text=forward_text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            
            logger.info(f"成功转发文本消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发文本消息失败: {e}")
            raise
    
    async def forward_message(self, message: Message, downloaded_files: List[Path]):
        """转发包含媒体的消息"""
        try:
            # 构建转发消息的文本
            forward_text = self._build_forward_text(message)
            
            # 根据媒体类型和数量选择转发方式
            media_type = self.get_media_type(message)
            
            if len(downloaded_files) == 1:
                # 单个媒体文件
                await self._send_single_media(message, downloaded_files[0], forward_text)
            else:
                # 多个媒体文件
                await self._send_media_group(message, downloaded_files, forward_text)
            
            logger.info(f"成功转发媒体消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发媒体消息失败: {e}")
            raise
    
    async def _send_single_media(self, message: Message, file_path: Path, caption: str):
        """发送单个媒体文件"""
        media_type = self.get_media_type(message)
        
        with open(file_path, 'rb') as file:
            if media_type == 'photo':
                await message.bot.send_photo(
                    chat_id=self.config.target_channel_id,
                    photo=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'video':
                await message.bot.send_video(
                    chat_id=self.config.target_channel_id,
                    video=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'document':
                await message.bot.send_document(
                    chat_id=self.config.target_channel_id,
                    document=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'audio':
                await message.bot.send_audio(
                    chat_id=self.config.target_channel_id,
                    audio=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'voice':
                await message.bot.send_voice(
                    chat_id=self.config.target_channel_id,
                    voice=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'video_note':
                await message.bot.send_video_note(
                    chat_id=self.config.target_channel_id,
                    video_note=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'animation':
                await message.bot.send_animation(
                    chat_id=self.config.target_channel_id,
                    animation=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == 'sticker':
                await message.bot.send_sticker(
                    chat_id=self.config.target_channel_id,
                    sticker=file
                )
    
    async def _send_media_group(self, message: Message, file_paths: List[Path], caption: str):
        """发送媒体组"""
        media_list = []
        
        for i, file_path in enumerate(file_paths):
            media_type = self.get_media_type(message)
            
            with open(file_path, 'rb') as file:
                if media_type == 'photo':
                    media = InputMediaPhoto(media=file)
                elif media_type == 'video':
                    media = InputMediaVideo(media=file)
                else:
                    media = InputMediaDocument(media=file)
                
                # 只在第一个媒体上添加说明文字
                if i == 0 and caption:
                    media.caption = caption
                    media.parse_mode = 'HTML'
                
                media_list.append(media)
        
        # 发送媒体组
        await message.bot.send_media_group(
            chat_id=self.config.target_channel_id,
            media=media_list
        )
    
    def _build_forward_text(self, message: Message) -> str:
        """构建转发消息的文本"""
        text_parts = []
        
        # 添加原始消息文本
        if message.text:
            text_parts.append(message.text)
        elif message.caption:
            text_parts.append(message.caption)
        
        # 添加转发信息
        forward_info = f"\n\n📤 转发自: {message.chat.title or '未知频道'}"
        if message.from_user:
            forward_info += f" (由 @{message.from_user.username or message.from_user.first_name} 发布)"
        
        text_parts.append(forward_info)
        
        return '\n'.join(text_parts)
    
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
