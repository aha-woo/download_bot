"""
配置文件管理
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """配置类"""
    
    def __init__(self):
        self.bot_token = self._get_required_env('BOT_TOKEN')
        self.source_channel_id = self._get_required_env('SOURCE_CHANNEL_ID')
        self.target_channel_id = self._get_required_env('TARGET_CHANNEL_ID')
        
        # 可选配置
        self.api_id = self._get_optional_env('API_ID')
        self.api_hash = self._get_optional_env('API_HASH')
        
        # 下载设置
        self.download_path = os.getenv('DOWNLOAD_PATH', './downloads')
        self.max_file_size = self._parse_file_size(os.getenv('MAX_FILE_SIZE', '50MB'))
        
        # 验证配置
        self._validate_config()
    
    def _get_required_env(self, key: str) -> str:
        """获取必需的环境变量"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"必需的环境变量 {key} 未设置")
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
        # 验证频道ID格式
        if not (self.source_channel_id.startswith('@') or self.source_channel_id.startswith('-')):
            raise ValueError("源频道ID必须以@或-开头")
        
        if not (self.target_channel_id.startswith('@') or self.target_channel_id.startswith('-')):
            raise ValueError("目标频道ID必须以@或-开头")
        
        # 验证下载路径
        download_path = Path(self.download_path)
        if not download_path.exists():
            download_path.mkdir(parents=True, exist_ok=True)
        
        # 验证文件大小限制
        if self.max_file_size <= 0:
            raise ValueError("最大文件大小必须大于0")
    
    def __str__(self):
        """返回配置信息的字符串表示"""
        return f"""
配置信息:
- Bot Token: {self.bot_token[:10]}...
- 源频道: {self.source_channel_id}
- 目标频道: {self.target_channel_id}
- 下载路径: {self.download_path}
- 最大文件大小: {self.max_file_size / (1024*1024):.1f}MB
"""
