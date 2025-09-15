"""
Telegram User Client 消息处理模块 (Telethon版本)
"""

import logging
from typing import List, Optional
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from telethon.errors import TelegramError

from config import Config

logger = logging.getLogger(__name__)


class TelegramBotHandler:
    """Telegram User Client 消息处理器 (使用 Telethon)"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def has_media(self, message: Message) -> bool:
        """检查消息是否包含媒体文件"""
        return message.media is not None and not isinstance(message.media, type(None))
    
    def get_media_type(self, message: Message) -> Optional[str]:
        """获取媒体类型"""
        if not message.media:
            return None
        
        if isinstance(message.media, MessageMediaPhoto):
            return 'photo'
        elif isinstance(message.media, MessageMediaDocument):
            document = message.media.document
            if document and document.mime_type:
                mime_type = document.mime_type
                if mime_type.startswith('image/'):
                    return 'photo'
                elif mime_type.startswith('video/'):
                    return 'video'
                elif mime_type.startswith('audio/'):
                    return 'audio'
                elif 'gif' in mime_type.lower():
                    return 'animation'
            return 'document'
        
        return 'unknown'
    
    async def forward_text_message(self, message: Message, client: TelegramClient):
        """发送纯文本消息（作为原创内容）"""
        try:
            # 构建消息文本
            forward_text = self._build_forward_text(message)
            
            if not forward_text.strip():
                forward_text = "📝 转发的消息"  # 如果没有文本内容，添加默认提示
            
            # 发送到目标频道
            await client.send_message(
                entity=self.config.target_channel_id,
                message=forward_text,
                parse_mode='html'
            )
            
            logger.info(f"成功转发文本消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发文本消息失败: {e}")
            raise
    
    async def forward_message(self, message: Message, downloaded_files: List[dict], client: TelegramClient):
        """发送包含媒体的消息（作为原创内容）"""
        try:
            # 构建消息文本
            forward_text = self._build_forward_text(message)
            
            # 根据媒体数量选择发送方式
            if len(downloaded_files) == 1:
                # 单个媒体文件
                await self._send_single_media(message, downloaded_files[0], forward_text, client)
            else:
                # 多个媒体文件 - 发送为媒体组
                await self._send_media_group(message, downloaded_files, forward_text, client)
            
            logger.info(f"成功转发媒体消息到目标频道")
            
        except TelegramError as e:
            logger.error(f"转发媒体消息失败: {e}")
            raise
    
    async def _send_single_media(self, message: Message, file_info: dict, caption: str, client: TelegramClient):
        """发送单个媒体文件"""
        file_path = file_info['path']
        media_type = file_info['type']
        
        try:
            # 根据媒体类型发送
            if media_type == 'photo':
                await client.send_file(
                    entity=self.config.target_channel_id,
                    file=str(file_path),
                    caption=caption,
                    parse_mode='html'
                )
            elif media_type in ['video', 'animation']:
                # 视频和动画
                await client.send_file(
                    entity=self.config.target_channel_id,
                    file=str(file_path),
                    caption=caption,
                    parse_mode='html',
                    supports_streaming=True  # 支持流媒体
                )
            elif media_type == 'audio':
                # 音频
                await client.send_file(
                    entity=self.config.target_channel_id,
                    file=str(file_path),
                    caption=caption,
                    parse_mode='html',
                    voice_note=False  # 作为音频文件而不是语音消息
                )
            else:
                # 其他文档类型
                await client.send_file(
                    entity=self.config.target_channel_id,
                    file=str(file_path),
                    caption=caption,
                    parse_mode='html'
                )
                
        except Exception as e:
            logger.error(f"发送单个媒体文件失败: {file_path}, 错误: {e}")
            raise
    
    async def _send_media_group(self, message: Message, file_infos: List[dict], caption: str, client: TelegramClient):
        """发送媒体组"""
        try:
            # 准备文件列表
            files = []
            for file_info in file_infos:
                files.append(str(file_info['path']))
            
            # Telethon 的 send_file 可以接受文件列表，自动作为媒体组发送
            await client.send_file(
                entity=self.config.target_channel_id,
                file=files,
                caption=caption,
                parse_mode='html'
            )
            
            logger.info(f"成功发送媒体组，包含 {len(files)} 个文件")
            
        except Exception as e:
            logger.error(f"发送媒体组失败: {e}")
            # 如果媒体组发送失败，尝试逐个发送
            logger.info("尝试逐个发送媒体文件...")
            for i, file_info in enumerate(file_infos):
                try:
                    # 只在第一个文件上添加说明文字
                    file_caption = caption if i == 0 else ""
                    await self._send_single_media(message, file_info, file_caption, client)
                    logger.info(f"成功发送第 {i+1}/{len(file_infos)} 个文件")
                except Exception as single_error:
                    logger.error(f"发送第 {i+1} 个文件失败: {single_error}")
    
    def _build_forward_text(self, message: Message) -> str:
        """构建消息文本（不显示转发信息）"""
        text_parts = []
        
        # 添加原始消息文本
        if message.text:
            text_parts.append(message.text)
        
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
    
    async def get_channel_info(self, client: TelegramClient, channel_id: str):
        """获取频道信息"""
        try:
            entity = await client.get_entity(channel_id)
            return {
                'id': entity.id,
                'title': getattr(entity, 'title', 'Unknown'),
                'username': getattr(entity, 'username', None),
                'type': 'channel' if hasattr(entity, 'broadcast') else 'group'
            }
        except Exception as e:
            logger.error(f"获取频道信息失败 {channel_id}: {e}")
            return None
    
    async def check_permissions(self, client: TelegramClient):
        """检查频道权限"""
        try:
            # 检查源频道权限
            source_info = await self.get_channel_info(client, self.config.source_channel_id)
            if not source_info:
                raise ValueError(f"无法访问源频道: {self.config.source_channel_id}")
            
            # 检查目标频道权限
            target_info = await self.get_channel_info(client, self.config.target_channel_id)
            if not target_info:
                raise ValueError(f"无法访问目标频道: {self.config.target_channel_id}")
            
            logger.info(f"源频道: {source_info['title']} (ID: {source_info['id']})")
            logger.info(f"目标频道: {target_info['title']} (ID: {target_info['id']})")
            
            return True
            
        except Exception as e:
            logger.error(f"检查频道权限失败: {e}")
            return False