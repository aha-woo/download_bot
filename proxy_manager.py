"""
代理管理器 - 处理代理连接、轮换和故障转移
"""

import asyncio
import logging
import random
import socket
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
import json

logger = logging.getLogger(__name__)


class ProxyManager:
    """代理管理器类"""
    
    def __init__(self, config):
        self.config = config
        self.current_proxy_index = 0
        self.proxy_list = []
        self.last_rotation_time = 0
        self.failed_proxies = set()
        
        # 加载代理列表
        self._load_proxy_list()
    
    def _load_proxy_list(self):
        """加载代理列表"""
        if not self.config.proxy_rotation_enabled:
            # 如果没有启用轮换，只使用主代理
            if self.config.proxy_enabled:
                main_proxy = {
                    'type': self.config.proxy_type,
                    'host': self.config.proxy_host,
                    'port': self.config.proxy_port,
                    'username': self.config.proxy_username,
                    'password': self.config.proxy_password,
                    'name': 'main_proxy'
                }
                self.proxy_list = [main_proxy]
            return
        
        # 从文件加载代理列表
        proxy_file = Path(self.config.proxy_list_file)
        if not proxy_file.exists():
            logger.warning(f"⚠️ 代理列表文件不存在: {proxy_file}")
            logger.info("📝 创建示例代理列表文件...")
            self._create_example_proxy_file(proxy_file)
            return
        
        try:
            with open(proxy_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
                if content.startswith('[') or content.startswith('{'):
                    # JSON格式
                    proxy_data = json.loads(content)
                    if isinstance(proxy_data, list):
                        self.proxy_list = proxy_data
                    else:
                        self.proxy_list = [proxy_data]
                else:
                    # 纯文本格式: type://host:port@username:password
                    self.proxy_list = self._parse_text_proxy_list(content)
            
            logger.info(f"📋 加载了 {len(self.proxy_list)} 个代理")
            
        except Exception as e:
            logger.error(f"❌ 加载代理列表失败: {e}")
            self.proxy_list = []
    
    def _create_example_proxy_file(self, proxy_file: Path):
        """创建示例代理文件"""
        example_proxies = [
            {
                "type": "socks5",
                "host": "proxy1.example.com",
                "port": 1080,
                "username": "user1",
                "password": "pass1",
                "name": "residential_proxy_1"
            },
            {
                "type": "socks5", 
                "host": "proxy2.example.com",
                "port": 1080,
                "username": "user2",
                "password": "pass2",
                "name": "residential_proxy_2"
            }
        ]
        
        try:
            with open(proxy_file, 'w', encoding='utf-8') as f:
                json.dump(example_proxies, f, indent=2, ensure_ascii=False)
            logger.info(f"📝 已创建示例代理文件: {proxy_file}")
            logger.info("💡 请编辑此文件添加您的实际代理信息")
        except Exception as e:
            logger.error(f"❌ 创建示例代理文件失败: {e}")
    
    def _parse_text_proxy_list(self, content: str) -> List[Dict]:
        """解析文本格式的代理列表"""
        proxies = []
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                # 格式: socks5://host:port@username:password
                if '://' in line:
                    parts = line.split('://')
                    proxy_type = parts[0]
                    rest = parts[1]
                    
                    if '@' in rest:
                        auth_part, host_part = rest.split('@')
                        username, password = auth_part.split(':', 1)
                    else:
                        username = password = ''
                        host_part = rest
                    
                    host, port = host_part.split(':')
                    
                    proxy = {
                        'type': proxy_type,
                        'host': host,
                        'port': int(port),
                        'username': username,
                        'password': password,
                        'name': f"{host}:{port}"
                    }
                    proxies.append(proxy)
                    
            except Exception as e:
                logger.warning(f"⚠️ 解析代理行失败: {line} - {e}")
        
        return proxies
    
    async def get_current_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取当前代理配置"""
        if not self.proxy_list:
            return None
        
        # 检查是否需要轮换
        if self._should_rotate_proxy():
            await self._rotate_to_next_proxy()
        
        current_proxy = self.proxy_list[self.current_proxy_index]
        return self._proxy_to_telethon_config(current_proxy)
    
    def _should_rotate_proxy(self) -> bool:
        """检查是否应该轮换代理"""
        if not self.config.proxy_rotation_enabled:
            return False
        
        if len(self.proxy_list) <= 1:
            return False
        
        current_time = time.time()
        return (current_time - self.last_rotation_time) >= self.config.proxy_rotation_interval
    
    async def _rotate_to_next_proxy(self):
        """轮换到下一个代理"""
        old_index = self.current_proxy_index
        attempts = 0
        max_attempts = len(self.proxy_list)
        
        while attempts < max_attempts:
            # 选择下一个代理
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
            current_proxy = self.proxy_list[self.current_proxy_index]
            
            # 跳过已失败的代理
            proxy_key = f"{current_proxy['host']}:{current_proxy['port']}"
            if proxy_key in self.failed_proxies:
                attempts += 1
                continue
            
            # 测试新代理
            if await self._test_proxy(current_proxy):
                self.last_rotation_time = time.time()
                old_proxy = self.proxy_list[old_index]
                logger.info(f"🔄 代理已轮换: {old_proxy['name']} → {current_proxy['name']}")
                return
            else:
                # 标记为失败
                self.failed_proxies.add(proxy_key)
                attempts += 1
        
        # 所有代理都失败了，重置失败列表并使用原代理
        logger.warning("⚠️ 所有代理都不可用，重置失败列表")
        self.failed_proxies.clear()
        self.current_proxy_index = old_index
    
    async def _test_proxy(self, proxy_config: Dict) -> bool:
        """测试单个代理"""
        try:
            import socks
            
            sock = socks.socksocket()
            
            # 设置代理类型
            proxy_type_map = {
                'socks5': socks.SOCKS5,
                'socks4': socks.SOCKS4,
                'http': socks.HTTP
            }
            
            proxy_type = proxy_type_map.get(proxy_config['type'], socks.SOCKS5)
            
            # 设置代理
            if proxy_config.get('username') and proxy_config.get('password'):
                sock.set_proxy(
                    proxy_type,
                    proxy_config['host'],
                    proxy_config['port'],
                    username=proxy_config['username'],
                    password=proxy_config['password']
                )
            else:
                sock.set_proxy(
                    proxy_type,
                    proxy_config['host'],
                    proxy_config['port']
                )
            
            # 设置超时
            sock.settimeout(self.config.proxy_test_timeout)
            
            # 测试连接
            sock.connect(('149.154.167.50', 443))  # Telegram DC1
            sock.close()
            
            return True
            
        except Exception as e:
            logger.debug(f"代理测试失败 {proxy_config['name']}: {e}")
            return False
    
    def _proxy_to_telethon_config(self, proxy_config: Dict) -> Dict[str, Any]:
        """将代理配置转换为Telethon格式"""
        try:
            import socks
        except ImportError:
            raise ImportError("需要安装 PySocks: pip install PySocks")
        
        proxy_type_map = {
            'socks5': socks.SOCKS5,
            'socks4': socks.SOCKS4,
            'http': socks.HTTP
        }
        
        telethon_config = {
            'proxy_type': proxy_type_map[proxy_config['type']],
            'addr': proxy_config['host'],
            'port': proxy_config['port'],
            'rdns': True
        }
        
        if proxy_config.get('username') and proxy_config.get('password'):
            telethon_config['username'] = proxy_config['username']
            telethon_config['password'] = proxy_config['password']
        
        return telethon_config
    
    def get_current_proxy_info(self) -> str:
        """获取当前代理信息字符串"""
        if not self.proxy_list:
            return "🚫 未配置代理"
        
        current_proxy = self.proxy_list[self.current_proxy_index]
        auth_info = ""
        if current_proxy.get('username'):
            auth_info = f" (认证: {current_proxy['username']})"
        
        rotation_info = ""
        if self.config.proxy_rotation_enabled and len(self.proxy_list) > 1:
            rotation_info = f" [轮换: {self.current_proxy_index + 1}/{len(self.proxy_list)}]"
        
        return f"🔗 {current_proxy['type']}://{current_proxy['host']}:{current_proxy['port']}{auth_info}{rotation_info}"
    
    async def test_all_proxies(self) -> Dict[str, bool]:
        """测试所有代理的连通性"""
        results = {}
        
        logger.info("🔍 测试所有代理连通性...")
        
        for i, proxy in enumerate(self.proxy_list):
            proxy_name = proxy.get('name', f"proxy_{i}")
            logger.info(f"测试代理 {i+1}/{len(self.proxy_list)}: {proxy_name}")
            
            result = await self._test_proxy(proxy)
            results[proxy_name] = result
            
            status = "✅ 成功" if result else "❌ 失败"
            logger.info(f"  {status}")
        
        # 统计结果
        success_count = sum(1 for r in results.values() if r)
        total_count = len(results)
        
        logger.info(f"📊 代理测试完成: {success_count}/{total_count} 可用")
        
        return results
    
    async def force_rotate_proxy(self) -> bool:
        """强制轮换到下一个可用代理"""
        if len(self.proxy_list) <= 1:
            logger.warning("⚠️ 代理列表中只有一个代理，无法轮换")
            return False
        
        await self._rotate_to_next_proxy()
        return True
    
    def get_proxy_statistics(self) -> Dict[str, Any]:
        """获取代理统计信息"""
        stats = {
            'total_proxies': len(self.proxy_list),
            'current_proxy_index': self.current_proxy_index,
            'failed_proxies_count': len(self.failed_proxies),
            'rotation_enabled': self.config.proxy_rotation_enabled,
            'last_rotation_time': self.last_rotation_time
        }
        
        if self.proxy_list:
            current_proxy = self.proxy_list[self.current_proxy_index]
            stats['current_proxy_name'] = current_proxy.get('name', 'unnamed')
            stats['current_proxy_host'] = current_proxy['host']
            stats['current_proxy_port'] = current_proxy['port']
        
        return stats
