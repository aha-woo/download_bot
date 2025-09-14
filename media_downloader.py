"""
媒体文件下载模块
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from telegram import Message
from telegram.error import TelegramError

from config import Config

logger = logging.getLogger(__name__)


class MediaDownloader:
    """媒体文件下载器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.download_path = Path(config.download_path)
        self.download_path.mkdir(exist_ok=True)
    
    async def download_media(self, message: Message, bot=None) -> List[dict]:
        """下载消息中的媒体文件，返回文件路径和类型信息"""
        downloaded_files = []
        
        try:
            # 检查消息是否包含媒体
            if not self._has_media(message):
                logger.info(f"消息 {message.message_id} 不包含媒体文件")
                return downloaded_files
            
            # 获取所有媒体文件信息
            media_info_list = self._get_all_media_info(message)
            if not media_info_list:
                logger.warning(f"无法获取消息 {message.message_id} 的媒体信息")
                return downloaded_files
            
            # 下载所有媒体文件
            for i, media_info in enumerate(media_info_list):
                # 检查文件大小
                file_size_mb = media_info['file_size'] / (1024 * 1024)
                max_size_mb = self.config.max_file_size / (1024 * 1024)
                
                if media_info['file_size'] > self.config.max_file_size:
                    logger.warning(f"⚠️ 文件 {media_info['file_name']} 超过大小限制 ({file_size_mb:.1f}MB > {max_size_mb:.1f}MB)，跳过下载")
                    continue
                elif media_info['file_size'] > 20 * 1024 * 1024:  # 20MB
                    logger.warning(f"⚠️ 文件 {media_info['file_name']} 超过Bot API限制 ({file_size_mb:.1f}MB > 20MB)，可能下载失败")
                    logger.info("💡 建议：搭建本地Bot API服务器以支持大文件下载")
                
                # 生成文件名
                file_name = self._generate_file_name(message, media_info, i)
                file_path = self.download_path / file_name
                
                # 下载文件
                logger.info(f"开始下载文件: {file_name}")
                await self._download_file(message, media_info, file_path, bot)
                
                if file_path.exists() and file_path.stat().st_size > 0:
                    downloaded_files.append({
                        'path': file_path,
                        'type': media_info['media_type']
                    })
                    logger.info(f"成功下载文件: {file_path}")
                else:
                    logger.error(f"文件下载失败或文件为空: {file_path}")
            
        except Exception as e:
            logger.error(f"下载媒体文件时出错: {e}")
        
        return downloaded_files
    
    def _has_media(self, message: Message) -> bool:
        """检查消息是否包含媒体"""
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
    
    def _get_all_media_info(self, message: Message) -> List[dict]:
        """获取所有媒体文件信息"""
        media_info_list = []
        
        if message.photo:
            # 对于照片，只选择最高分辨率的一张
            photo = max(message.photo, key=lambda p: p.file_size)
            media_info_list.append({
                'file_id': photo.file_id,
                'file_name': f"photo_{message.message_id}.jpg",
                'file_size': photo.file_size or 0,
                'media_type': 'photo'
            })
        elif message.video:
            media_info_list.append({
                'file_id': message.video.file_id,
                'file_name': message.video.file_name or f"video_{message.message_id}.mp4",
                'file_size': message.video.file_size or 0,
                'media_type': 'video'
            })
        elif message.document:
            media_info_list.append({
                'file_id': message.document.file_id,
                'file_name': message.document.file_name or f"document_{message.message_id}",
                'file_size': message.document.file_size or 0,
                'media_type': 'document'
            })
        elif message.audio:
            media_info_list.append({
                'file_id': message.audio.file_id,
                'file_name': message.audio.file_name or f"audio_{message.message_id}.mp3",
                'file_size': message.audio.file_size or 0,
                'media_type': 'audio'
            })
        elif message.voice:
            media_info_list.append({
                'file_id': message.voice.file_id,
                'file_name': f"voice_{message.message_id}.ogg",
                'file_size': message.voice.file_size or 0,
                'media_type': 'voice'
            })
        elif message.video_note:
            media_info_list.append({
                'file_id': message.video_note.file_id,
                'file_name': f"video_note_{message.message_id}.mp4",
                'file_size': message.video_note.file_size or 0,
                'media_type': 'video_note'
            })
        elif message.animation:
            media_info_list.append({
                'file_id': message.animation.file_id,
                'file_name': message.animation.file_name or f"animation_{message.message_id}.gif",
                'file_size': message.animation.file_size or 0,
                'media_type': 'animation'
            })
        elif message.sticker:
            media_info_list.append({
                'file_id': message.sticker.file_id,
                'file_name': f"sticker_{message.message_id}.webp",
                'file_size': message.sticker.file_size or 0,
                'media_type': 'sticker'
            })
        
        return media_info_list
    
    def _get_media_info(self, message: Message) -> Optional[dict]:
        """获取媒体文件信息（保持向后兼容）"""
        media_info_list = self._get_all_media_info(message)
        return media_info_list[0] if media_info_list else None
    
    def _generate_file_name(self, message: Message, media_info: dict, index: int = 0) -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        message_id = message.message_id
        
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
    
    async def _download_file(self, message: Message, media_info: dict, file_path: Path, bot=None):
        """下载文件"""
        try:
            # 获取bot实例
            bot_instance = bot or getattr(message, 'bot', None)
            if not bot_instance:
                raise ValueError("无法获取bot实例")
            
            # 获取文件对象
            file = await bot_instance.get_file(media_info['file_id'])
            
            # 下载文件
            await file.download_to_drive(file_path)
            
            logger.info(f"文件下载完成: {file_path}")
            
        except TelegramError as e:
            logger.error(f"下载文件失败: {e}")
            raise
        except Exception as e:
            logger.error(f"下载文件时发生未知错误: {e}")
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
                'total_size_mb': total_size / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"获取下载统计时出错: {e}")
            return {'total_files': 0, 'total_size': 0, 'total_size_mb': 0}
