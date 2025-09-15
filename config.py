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
        
        # 会话设置
        self.session_name = os.getenv('SESSION_NAME', 'telegram_session')
        self.session_path = Path(os.getenv('SESSION_PATH', './'))
        
        # 下载设置
        self.download_path = os.getenv('DOWNLOAD_PATH', './downloads')
        self.max_file_size = self._parse_file_size(os.getenv('MAX_FILE_SIZE', '2GB'))  # User API 支持 2GB
        
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
    
    def __str__(self):
        """返回配置信息的字符串表示"""
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
"""
