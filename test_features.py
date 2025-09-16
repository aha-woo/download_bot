#!/usr/bin/env python3
"""
测试User Client新功能的脚本
"""

import asyncio
import logging
from main import TelegramUserClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_history_download():
    """测试历史消息下载功能"""
    client = TelegramUserClient()
    
    try:
        # 启动客户端
        if await client.start_client():
            logger.info("🧪 开始测试历史消息下载功能...")
            
            # 测试1: 下载最近10条消息
            logger.info("📋 测试1: 下载最近10条历史消息")
            count1 = await client.download_history_messages(limit=10)
            logger.info(f"✅ 测试1完成，处理了 {count1} 条消息")
            
            # 测试2: 下载3天前的消息
            logger.info("📋 测试2: 下载3天前的历史消息")
            count2 = await client.download_history_messages(limit=20, offset_days=3)
            logger.info(f"✅ 测试2完成，处理了 {count2} 条消息")
            
            logger.info("🎉 历史消息下载功能测试完成！")
        else:
            logger.error("❌ 客户端启动失败")
            
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}")
    finally:
        if client.client and client.client.is_connected():
            await client.client.disconnect()

async def main():
    """主测试函数"""
    logger.info("🚀 开始测试User Client新功能...")
    await test_history_download()
    logger.info("✅ 所有测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
