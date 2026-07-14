# -*- coding: utf-8 -*-
"""飞书集成模块 — 基于 lark-channel-sdk。"""

import logging
import asyncio
from typing import Optional

from lark_channel import FeishuChannel

from .client import FEISHU_APP_ID, FEISHU_APP_SECRET

logger = logging.getLogger(__name__)

# 延迟初始化的全局 channel 实例
_channel: Optional[FeishuChannel] = None


def get_channel() -> FeishuChannel:
    """获取全局 FeishuChannel 实例（延迟初始化，线程不安全但符合单线程 async 场景）。"""
    global _channel
    if _channel is None:
        _channel = FeishuChannel(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
        )
    return _channel


def start_feishu_sdk():
    """启动飞书 SDK 长连接（此函数是进程入口，会阻塞当前线程）。"""
    from .handler import init_agent, handle_message

    agent = init_agent()
    ch = get_channel()

    ch.on("message", lambda msg: handle_message(agent, msg))

    logger.info("""
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  连接方式: lark-channel-sdk (WebSocket 长连接)               ║
║  状态: 正在连接飞书服务器...                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(ch.connect())


__all__ = ["start_feishu_sdk", "get_channel"]
