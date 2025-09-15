"""
媒体文件下载模块 (Telethon User API版本)
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from telethon.errors import RPCError

from config import Config

logger = logging.getLogger(__name__)


class MediaDownloader:
    """媒体文件下载器 (使用 Telethon User API)"""
    
    def __init__(self, config: Config):
        self.config = config
        self.download_path = Path(config.download_path)
        self.download_path.mkdir(exist_ok=True)
    
    async def download_media(self, message: Message, client: TelegramClient) -> List[dict]:
        """下载消息中的媒体文件，返回文件路径和类型信息"""
        downloaded_files = []
        
        try:
            # 检查消息是否包含媒体
            if not self._has_media(message):
                logger.info(f"消息 {message.id} 不包含媒体文件")
                return downloaded_files
            
            # 获取所有媒体文件信息
            media_info_list = self._get_all_media_info(message)
            if not media_info_list:
                logger.warning(f"无法获取消息 {message.id} 的媒体信息")
                return downloaded_files
            
            # 下载所有媒体文件
            for i, media_info in enumerate(media_info_list):
                # 检查文件大小（User API 支持 2GB，但仍要检查配置限制）
                file_size_mb = media_info['file_size'] / (1024 * 1024)
                max_size_gb = self.config.max_file_size / (1024 * 1024 * 1024)
                
                if media_info['file_size'] > self.config.max_file_size:
                    logger.warning(f"⚠️ 文件 {media_info['file_name']} 超过配置的大小限制 ({file_size_mb:.1f}MB > {max_size_gb:.1f}GB)，跳过下载")
                    continue
                
                # User API 支持 2GB 文件，无需特殊警告
                if media_info['file_size'] > 1024 * 1024 * 1024:  # 1GB
                    logger.info(f"📥 准备下载大文件: {media_info['file_name']} ({file_size_mb:.1f}MB)")
                
                # 生成文件名
                file_name = self._generate_file_name(message, media_info, i)
                file_path = self.download_path / file_name
                
                # 下载文件
                logger.info(f"开始下载文件: {file_name}")
                await self._download_file(message, media_info, file_path, client)
                
                if file_path.exists() and file_path.stat().st_size > 0:
                    downloaded_files.append({
                        'path': file_path,
                        'type': media_info['media_type']
                    })
                    logger.info(f"成功下载文件: {file_path} ({file_size_mb:.1f}MB)")
                else:
                    logger.error(f"文件下载失败或文件为空: {file_path}")
            
        except Exception as e:
            logger.error(f"下载媒体文件时出错: {e}")
        
        return downloaded_files
    
    def _has_media(self, message: Message) -> bool:
        """检查消息是否包含媒体"""
        return message.media is not None and not isinstance(message.media, type(None))
    
    def _get_all_media_info(self, message: Message) -> List[dict]:
        """获取所有媒体文件信息"""
        media_info_list = []
        
        if not message.media:
            return media_info_list
        
        # 根据媒体类型获取信息
        if isinstance(message.media, MessageMediaPhoto):
            # 照片
            photo = message.media.photo
            media_info_list.append({
                'file_id': None,  # Telethon 不使用 file_id
                'file_name': f"photo_{message.id}.jpg",
                'file_size': getattr(photo, 'size', 0) or self._estimate_photo_size(photo),
                'media_type': 'photo',
                'media_obj': message.media
            })
        elif isinstance(message.media, MessageMediaDocument):
            # 文档（包括视频、音频、文件等）
            document = message.media.document
            if document:
                # 根据 MIME 类型判断媒体类型
                mime_type = document.mime_type or ""
                media_type = self._get_media_type_from_mime(mime_type)
                
                # 生成文件名
                file_name = self._get_document_filename(document, message.id, media_type)
                
                media_info_list.append({
                    'file_id': None,
                    'file_name': file_name,
                    'file_size': document.size or 0,
                    'media_type': media_type,
                    'media_obj': message.media,
                    'mime_type': mime_type
                })
        
        return media_info_list
    
    def _get_media_type_from_mime(self, mime_type: str) -> str:
        """根据 MIME 类型判断媒体类型"""
        if mime_type.startswith('image/'):
            return 'photo'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif 'gif' in mime_type.lower():
            return 'animation'
        else:
            return 'document'
    
    def _get_document_filename(self, document, message_id: int, media_type: str) -> str:
        """获取文档文件名"""
        # 尝试从文档属性中获取文件名
        for attr in document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                return attr.file_name
        
        # 如果没有文件名，根据类型生成
        extensions = {
            'photo': 'jpg',
            'video': 'mp4',
            'audio': 'mp3',
            'animation': 'gif',
            'document': 'bin'
        }
        ext = extensions.get(media_type, 'bin')
        return f"{media_type}_{message_id}.{ext}"
    
    def _estimate_photo_size(self, photo) -> int:
        """估算照片文件大小"""
        # 简单估算：根据最大尺寸估算
        try:
            if hasattr(photo, 'sizes') and photo.sizes:
                largest_size = max(photo.sizes, key=lambda s: getattr(s, 'size', 0))
                return getattr(largest_size, 'size', 0) or 1024 * 1024  # 默认 1MB
        except:
            pass
        return 1024 * 1024  # 默认 1MB
    
    def _generate_file_name(self, message: Message, media_info: dict, index: int = 0) -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        message_id = message.id
        
        # 获取原始文件名和扩展名
        original_name = media_info['file_name']
        if '.' in original_name:
            name, ext = original_name.rsplit('.', 1)
        else:
            name = original_name
            ext = self._get_default_extension(media_info['media_type'])
        
        # 生成新文件名，如果有多个文件则添加索引
        if index > 0:
            new_name = f"{timestamp}_{message_id}_{name}_{index}.{ext}"
        else:
            new_name = f"{timestamp}_{message_id}_{name}.{ext}"
        
        # 确保文件名安全
        safe_name = self._sanitize_filename(new_name)
        
        return safe_name
    
    def _get_default_extension(self, media_type: str) -> str:
        """获取默认文件扩展名"""
        extensions = {
            'photo': 'jpg',
            'video': 'mp4',
            'document': 'bin',
            'audio': 'mp3',
            'voice': 'ogg',
            'video_note': 'mp4',
            'animation': 'gif',
            'sticker': 'webp'
        }
        return extensions.get(media_type, 'bin')
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除不安全字符"""
        import re
        # 移除或替换不安全字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制文件名长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1)
            filename = name[:250] + '.' + ext
        return filename
    
    async def _download_file(self, message: Message, media_info: dict, file_path: Path, client: TelegramClient):
        """下载文件 (使用 Telethon)"""
        file_name = media_info.get('file_name', 'unknown')
        file_size_mb = media_info.get('file_size', 0) / (1024 * 1024)
        
        try:
            logger.info(f"🔄 开始下载文件: {file_name} ({file_size_mb:.1f}MB)")
            
            # 使用 Telethon 下载媒体
            await client.download_media(message, file=str(file_path))
            
            logger.info(f"✅ 文件下载完成: {file_path}")
            
        except RPCError as e:
            # 详细记录Telegram API错误
            error_code = getattr(e, 'code', 'Unknown')
            error_message = str(e)
            
            logger.error(f"❌ Telegram API错误 - 文件: {file_name} ({file_size_mb:.1f}MB)")
            logger.error(f"   错误代码: {error_code}")
            logger.error(f"   错误信息: {error_message}")
            
            # User API 通常不会有20MB限制，但记录其他错误
            if "file is too big" in error_message.lower():
                logger.error(f"   🚫 文件过大错误（不应该出现在User API中）")
            elif "flood" in error_message.lower():
                logger.error(f"   🚫 请求频率限制，请稍后重试")
            elif "not found" in error_message.lower():
                logger.error(f"   🚫 文件未找到，可能已被删除")
            else:
                logger.error(f"   🚫 其他API错误")
            
            raise
            
        except Exception as e:
            logger.error(f"❌ 下载文件时发生未知错误: {file_name} ({file_size_mb:.1f}MB)")
            logger.error(f"   错误详情: {type(e).__name__}: {e}")
            raise
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """清理旧文件"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for file_path in self.download_path.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        logger.info(f"删除旧文件: {file_path}")
            
        except Exception as e:
            logger.error(f"清理旧文件时出错: {e}")
    
    def get_download_stats(self) -> dict:
        """获取下载统计信息"""
        try:
            total_files = 0
            total_size = 0
            
            for file_path in self.download_path.iterdir():
                if file_path.is_file():
                    total_files += 1
                    total_size += file_path.stat().st_size
            
            return {
                'total_files': total_files,
                'total_size': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'total_size_gb': total_size / (1024 * 1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"获取下载统计时出错: {e}")
            return {'total_files': 0, 'total_size': 0, 'total_size_mb': 0, 'total_size_gb': 0}