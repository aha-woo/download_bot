"""
消息队列管理器 - 处理延迟发送和批量发送
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from telethon.tl.types import Message

logger = logging.getLogger(__name__)


@dataclass
class QueuedMessage:
    """队列中的消息"""
    message_id: int
    channel_title: str
    files: List[Dict[str, Any]]  # [{'path': str, 'type': str}]
    text_content: str
    send_time: float
    added_time: float
    priority: int = 0  # 优先级，数字越小优先级越高
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> dict:
        """转换为字典格式用于保存"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueuedMessage':
        """从字典创建对象"""
        return cls(**data)


class MessageQueue:
    """消息队列管理器"""
    
    def __init__(self, config):
        self.config = config
        self.queue: List[QueuedMessage] = []
        self.processing = False
        self.queue_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.total_queued = 0
        self.total_sent = 0
        self.total_failed = 0
        
        # 加载已保存的队列
        if self.config.auto_save_queue:
            self._load_queue()
    
    async def add_message(self, message: Message, files: List[Dict[str, Any]], channel_title: str = "Unknown") -> bool:
        """添加消息到队列"""
        try:
            # 检查队列大小限制
            if len(self.queue) >= self.config.max_queue_size:
                logger.warning(f"⚠️ 队列已满（{self.config.max_queue_size}），跳过消息 {message.id}")
                return False
            
            # 计算发送时间
            if self.config.batch_send_enabled:
                # 批量发送模式：按批次间隔发送
                batch_number = len(self.queue) // self.config.batch_size
                send_delay = batch_number * self.config.batch_interval
                send_delay += random.uniform(0, 300)  # 添加0-5分钟的随机延迟
            else:
                # 随机发送模式
                send_delay = random.uniform(self.config.min_send_delay, self.config.max_send_delay)
            
            send_time = asyncio.get_event_loop().time() + send_delay
            
            # 创建队列消息
            queued_msg = QueuedMessage(
                message_id=message.id,
                channel_title=channel_title,
                files=files,
                text_content=message.text or message.caption or "",
                send_time=send_time,
                added_time=asyncio.get_event_loop().time(),
                priority=0
            )
            
            self.queue.append(queued_msg)
            self.total_queued += 1
            
            # 按发送时间排序
            self.queue.sort(key=lambda x: (x.priority, x.send_time))
            
            logger.info(f"📋 消息 {message.id} 已加入队列，将在 {send_delay/60:.1f} 分钟后发送")
            logger.info(f"📊 当前队列长度: {len(self.queue)}")
            
            # 自动保存队列
            if self.config.auto_save_queue:
                self._save_queue()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加消息到队列失败: {e}")
            return False
    
    async def start_processing(self, bot_handler, client):
        """启动队列处理"""
        if self.processing:
            logger.warning("⚠️ 队列处理器已在运行")
            return
        
        self.processing = True
        self.queue_task = asyncio.create_task(self._process_queue(bot_handler, client))
        logger.info(f"🚀 消息队列处理器已启动，检查间隔: {self.config.queue_check_interval}秒")
    
    async def stop_processing(self):
        """停止队列处理"""
        if not self.processing:
            return
        
        self.processing = False
        if self.queue_task:
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 消息队列处理器已停止")
    
    async def _process_queue(self, bot_handler, client):
        """处理队列中的消息"""
        while self.processing:
            try:
                current_time = asyncio.get_event_loop().time()
                messages_to_send = []
                remaining_messages = []
                
                # 分离到期和未到期的消息
                for msg in self.queue:
                    if current_time >= msg.send_time:
                        messages_to_send.append(msg)
                    else:
                        remaining_messages.append(msg)
                
                self.queue = remaining_messages
                
                # 发送到期的消息
                for queued_msg in messages_to_send:
                    success = await self._send_queued_message(queued_msg, bot_handler, client)
                    if success:
                        self.total_sent += 1
                        logger.info(f"✅ 队列消息 {queued_msg.message_id} 发送成功")
                    else:
                        # 重试逻辑
                        if queued_msg.retry_count < queued_msg.max_retries:
                            queued_msg.retry_count += 1
                            # 重新安排发送时间（5-15分钟后重试）
                            retry_delay = random.uniform(300, 900)
                            queued_msg.send_time = current_time + retry_delay
                            self.queue.append(queued_msg)
                            self.queue.sort(key=lambda x: (x.priority, x.send_time))
                            logger.warning(f"⚠️ 队列消息 {queued_msg.message_id} 发送失败，{retry_delay/60:.1f}分钟后重试 ({queued_msg.retry_count}/{queued_msg.max_retries})")
                        else:
                            self.total_failed += 1
                            logger.error(f"❌ 队列消息 {queued_msg.message_id} 发送失败，已达最大重试次数")
                
                # 自动保存队列状态
                if self.config.auto_save_queue and messages_to_send:
                    self._save_queue()
                
                # 等待下次检查
                await asyncio.sleep(self.config.queue_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 队列处理出错: {e}")
                await asyncio.sleep(self.config.queue_check_interval)
    
    async def _send_queued_message(self, queued_msg: QueuedMessage, bot_handler, client) -> bool:
        """发送队列中的消息"""
        try:
            # 创建临时消息对象（用于兼容现有接口）
            class TempMessage:
                def __init__(self, msg_id, text):
                    self.id = msg_id
                    self.text = text
                    self.caption = text
            
            temp_message = TempMessage(queued_msg.message_id, queued_msg.text_content)
            
            # 发送消息
            if queued_msg.files:
                await bot_handler.forward_message(temp_message, queued_msg.files, client)
            else:
                await bot_handler.forward_text_message(temp_message, client)
            
            # 清理文件
            await self._cleanup_files(queued_msg.files)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 发送队列消息 {queued_msg.message_id} 失败: {e}")
            return False
    
    async def _cleanup_files(self, files: List[Dict[str, Any]]):
        """清理已发送的文件"""
        for file_info in files:
            try:
                file_path = Path(file_info['path'])
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"🧹 已清理文件: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ 清理文件失败 {file_info['path']}: {e}")
    
    def get_status(self) -> dict:
        """获取队列状态"""
        current_time = asyncio.get_event_loop().time()
        
        # 计算统计信息
        pending_count = len(self.queue)
        ready_count = len([msg for msg in self.queue if current_time >= msg.send_time])
        
        # 下一条消息发送时间
        next_send_time = None
        if self.queue:
            next_msg = min(self.queue, key=lambda x: x.send_time)
            next_send_time = next_msg.send_time - current_time
        
        return {
            'enabled': self.config.queue_enabled,
            'processing': self.processing,
            'pending_count': pending_count,
            'ready_count': ready_count,
            'total_queued': self.total_queued,
            'total_sent': self.total_sent,
            'total_failed': self.total_failed,
            'next_send_in_seconds': next_send_time,
            'queue_size_limit': self.config.max_queue_size,
            'batch_mode': self.config.batch_send_enabled
        }
    
    def clear_queue(self) -> int:
        """清空队列"""
        count = len(self.queue)
        self.queue.clear()
        if self.config.auto_save_queue:
            self._save_queue()
        logger.info(f"🧹 已清空队列，移除了 {count} 条消息")
        return count
    
    def _save_queue(self):
        """保存队列到文件"""
        try:
            queue_data = {
                'queue': [msg.to_dict() for msg in self.queue],
                'stats': {
                    'total_queued': self.total_queued,
                    'total_sent': self.total_sent,
                    'total_failed': self.total_failed
                },
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.config.queue_save_path, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 队列已保存到 {self.config.queue_save_path}")
            
        except Exception as e:
            logger.error(f"❌ 保存队列失败: {e}")
    
    def _load_queue(self):
        """从文件加载队列"""
        try:
            queue_file = Path(self.config.queue_save_path)
            if not queue_file.exists():
                return
            
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            # 恢复队列
            for msg_data in queue_data.get('queue', []):
                queued_msg = QueuedMessage.from_dict(msg_data)
                self.queue.append(queued_msg)
            
            # 恢复统计信息
            stats = queue_data.get('stats', {})
            self.total_queued = stats.get('total_queued', 0)
            self.total_sent = stats.get('total_sent', 0)
            self.total_failed = stats.get('total_failed', 0)
            
            # 按发送时间排序
            self.queue.sort(key=lambda x: (x.priority, x.send_time))
            
            logger.info(f"📂 已从 {self.config.queue_save_path} 恢复队列，包含 {len(self.queue)} 条消息")
            
        except Exception as e:
            logger.error(f"❌ 加载队列失败: {e}")
            self.queue = []  # 重置队列
