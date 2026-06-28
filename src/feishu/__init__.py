# -*- coding: utf-8 -*-
"""飞书集成模块。"""

from .handler import init_agent, handle_message
from .client import get_feishu_config


def start_feishu_sdk():
    """启动飞书 SDK 长连接。"""
    import logging
    import lark_oapi as lark

    from .client import FEISHU_APP_ID, FEISHU_APP_SECRET

    logger = logging.getLogger(__name__)

    # 初始化 Agent
    agent = init_agent()

    # 创建事件处理器
    event_handler = lark.EventDispatcherHandler.builder(
        "", ""
    ).register_p2_im_message_receive_v1(lambda data: handle_message(agent, data)) \
     .build()

    # 创建 WebSocket 客户端
    ws_client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG
    )

    logger.info("""
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  连接方式: 飞书 SDK 长连接（无需公网 IP）                    ║
║  状态: 正在连接飞书服务器...                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 启动长连接
    ws_client.start()


__all__ = ["start_feishu_sdk", "init_agent", "handle_message", "get_feishu_config"]
