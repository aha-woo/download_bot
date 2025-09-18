"""
配置文件管理
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """配置类"""
    
    def __init__(self):
        # User API 配置 (必需)
        self.api_id = self._get_required_env('API_ID', int)
        self.api_hash = self._get_required_env('API_HASH')
        self.phone_number = self._get_required_env('PHONE_NUMBER')
        
        # 频道配置
        self.source_channel_id = self._get_required_env('SOURCE_CHANNEL_ID')
        self.target_channel_id = self._get_required_env('TARGET_CHANNEL_ID')
        
        # 多源频道配置 (可选)
        source_channels_str = os.getenv('SOURCE_CHANNELS', '')
        if source_channels_str:
            self.source_channels = [ch.strip() for ch in source_channels_str.split(',') if ch.strip()]
        else:
            self.source_channels = [self.source_channel_id]  # 默认使用单个源频道
        
        # 会话设置
        self.session_name = os.getenv('SESSION_NAME', 'telegram_session')
        self.session_path = Path(os.getenv('SESSION_PATH', './'))
        
        # 下载设置
        self.download_path = os.getenv('DOWNLOAD_PATH', './downloads')
        self.max_file_size = self._parse_file_size(os.getenv('MAX_FILE_SIZE', '2GB'))  # User API 支持 2GB
        
        # 随机延迟设置
        self.random_delay_min = int(os.getenv('RANDOM_DELAY_MIN', '2'))
        self.random_delay_max = int(os.getenv('RANDOM_DELAY_MAX', '15'))
        self.batch_delay_min = int(os.getenv('BATCH_DELAY_MIN', '30'))
        self.batch_delay_max = int(os.getenv('BATCH_DELAY_MAX', '120'))
        
        # 消息队列设置
        self.queue_enabled = os.getenv('QUEUE_ENABLED', 'false').lower() == 'true'
        self.min_send_delay = int(os.getenv('MIN_SEND_DELAY', '300'))  # 5分钟
        self.max_send_delay = int(os.getenv('MAX_SEND_DELAY', '7200'))  # 2小时
        self.queue_check_interval = int(os.getenv('QUEUE_CHECK_INTERVAL', '30'))  # 30秒
        self.max_queue_size = int(os.getenv('MAX_QUEUE_SIZE', '100'))
        
        # 分批发送设置
        self.batch_send_enabled = os.getenv('BATCH_SEND_ENABLED', 'false').lower() == 'true'
        self.batch_size = int(os.getenv('BATCH_SIZE', '5'))
        self.batch_interval = int(os.getenv('BATCH_INTERVAL', '1800'))  # 30分钟
        
        # 队列持久化设置
        self.queue_save_path = os.getenv('QUEUE_SAVE_PATH', './queue_data.json')
        self.auto_save_queue = os.getenv('AUTO_SAVE_QUEUE', 'true').lower() == 'true'
        
        # 代理设置
        self.proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
        self.proxy_type = os.getenv('PROXY_TYPE', 'socks5')  # socks5, socks4, http
        self.proxy_host = os.getenv('PROXY_HOST', '')
        self.proxy_port = int(os.getenv('PROXY_PORT', '1080'))
        self.proxy_username = os.getenv('PROXY_USERNAME', '')
        self.proxy_password = os.getenv('PROXY_PASSWORD', '')
        self.proxy_rdns = os.getenv('PROXY_RDNS', 'true').lower() == 'true'
        
        # 代理轮换设置 (高级功能)
        self.proxy_rotation_enabled = os.getenv('PROXY_ROTATION_ENABLED', 'false').lower() == 'true'
        self.proxy_rotation_interval = int(os.getenv('PROXY_ROTATION_INTERVAL', '3600'))  # 1小时
        self.proxy_list_file = os.getenv('PROXY_LIST_FILE', './proxy_list.txt')
        
        # 代理测试设置
        self.proxy_test_enabled = os.getenv('PROXY_TEST_ENABLED', 'true').lower() == 'true'
        self.proxy_test_timeout = int(os.getenv('PROXY_TEST_TIMEOUT', '10'))  # 10秒
        
        # 验证配置
        self._validate_config()
    
    def _get_required_env(self, key: str, value_type=str):
        """获取必需的环境变量"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"必需的环境变量 {key} 未设置")
        
        if value_type == int:
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"环境变量 {key} 必须是数字")
        return value
    
    def _get_optional_env(self, key: str) -> Optional[str]:
        """获取可选的环境变量"""
        return os.getenv(key)
    
    def _parse_file_size(self, size_str: str) -> int:
        """解析文件大小字符串为字节数"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            # 假设是字节数
            return int(size_str)
    
    def _validate_config(self):
        """验证配置"""
        # 验证API配置
        if not isinstance(self.api_id, int) or self.api_id <= 0:
            raise ValueError("API_ID 必须是有效的正整数")
        
        if not self.api_hash or len(self.api_hash) < 32:
            raise ValueError("API_HASH 必须是有效的32位字符串")
        
        if not self.phone_number.startswith('+'):
            raise ValueError("PHONE_NUMBER 必须以+开头（国际格式）")
        
        # 验证频道ID格式（允许更灵活的格式）
        if not (self.source_channel_id.startswith('@') or 
                self.source_channel_id.startswith('-') or
                self.source_channel_id.isdigit()):
            raise ValueError("源频道ID必须以@、-开头或为纯数字")
        
        if not (self.target_channel_id.startswith('@') or 
                self.target_channel_id.startswith('-') or
                self.target_channel_id.isdigit()):
            raise ValueError("目标频道ID必须以@、-开头或为纯数字")
        
        # 验证下载路径
        download_path = Path(self.download_path)
        if not download_path.exists():
            download_path.mkdir(parents=True, exist_ok=True)
        
        # 验证会话路径
        if not self.session_path.exists():
            self.session_path.mkdir(parents=True, exist_ok=True)
        
        # 验证文件大小限制
        if self.max_file_size <= 0:
            raise ValueError("最大文件大小必须大于0")
        
        # 验证代理配置
        if self.proxy_enabled:
            if not self.proxy_host:
                raise ValueError("启用代理时必须设置 PROXY_HOST")
            
            if self.proxy_type not in ['socks5', 'socks4', 'http']:
                raise ValueError("PROXY_TYPE 必须是 socks5、socks4 或 http")
            
            if not (1 <= self.proxy_port <= 65535):
                raise ValueError("PROXY_PORT 必须在 1-65535 范围内")
    
    def get_proxy_config(self):
        """获取代理配置字典，供Telethon使用"""
        if not self.proxy_enabled:
            return None
        
        # 导入socks模块来获取代理类型常量
        try:
            import socks
        except ImportError:
            raise ImportError("需要安装 PySocks: pip install PySocks")
        
        # 映射代理类型
        proxy_type_map = {
            'socks5': socks.SOCKS5,
            'socks4': socks.SOCKS4,
            'http': socks.HTTP
        }
        
        proxy_config = {
            'proxy_type': proxy_type_map[self.proxy_type],
            'addr': self.proxy_host,
            'port': self.proxy_port,
            'rdns': self.proxy_rdns
        }
        
        # 如果有用户名和密码，添加认证信息
        if self.proxy_username and self.proxy_password:
            proxy_config['username'] = self.proxy_username
            proxy_config['password'] = self.proxy_password
        
        return proxy_config
    
    def get_proxy_info_string(self):
        """获取代理信息的字符串表示（用于日志）"""
        if not self.proxy_enabled:
            return "🚫 代理未启用"
        
        auth_info = ""
        if self.proxy_username:
            auth_info = f" (认证: {self.proxy_username})"
        
        return f"🔗 代理: {self.proxy_type}://{self.proxy_host}:{self.proxy_port}{auth_info}"
    
    def __str__(self):
        """返回配置信息的字符串表示"""
        proxy_info = self.get_proxy_info_string()
        
        return f"""
配置信息:
- API ID: {self.api_id}
- API Hash: {self.api_hash[:8]}...
- 手机号: {self.phone_number[:5]}***
- 源频道: {self.source_channel_id}
- 目标频道: {self.target_channel_id}
- 下载路径: {self.download_path}
- 会话文件: {self.session_path / self.session_name}.session
- 最大文件大小: {self.max_file_size / (1024*1024*1024):.1f}GB
- {proxy_info}
- 队列模式: {'✅ 启用' if self.queue_enabled else '❌ 禁用'}
"""
