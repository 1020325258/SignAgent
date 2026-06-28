# -*- coding: utf-8 -*-
"""飞书消息处理模块。"""

import os
import json
import logging
import asyncio

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from ..agent import SignAgent
from .sender import send_reply, update_message

logger = logging.getLogger(__name__)


def init_agent() -> SignAgent:
    """初始化 SignAgent。"""
    project_dir = os.getenv("SIGN_AGENT_PROJECT_DIR", ".")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config, debug=debug)
    logger.info(f"✅ SignAgent 初始化完成 (debug={debug})")
    return agent


def handle_message(agent: SignAgent, data: P2ImMessageReceiveV1) -> None:
    """
    处理接收到的消息（同步版本）

    Args:
        agent: SignAgent 实例
        data: 消息事件数据
    """
    try:
        logger.info(f"收到消息事件: {data}")
        message = data.event.message
        sender = data.event.sender

        # 获取消息内容
        message_type = message.message_type
        content = message.content
        message_id = message.message_id

        # 只处理文本消息
        if message_type != "text":
            logger.info(f"忽略非文本消息: {message_type}")
            return

        # 解析消息内容
        try:
            content_data = json.loads(content)
            question = content_data.get("text", "")
        except json.JSONDecodeError:
            question = content

        # 去掉 @机器人 的部分
        if question.startswith("@"):
            question = question.split(" ", 1)[-1].strip()

        if not question:
            return

        logger.info(f"收到消息: {question}")

        # 在新线程中运行异步任务
        import threading
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_message(agent, message_id, question))
            finally:
                loop.close()

        thread = threading.Thread(target=run_async)
        thread.start()

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()


async def process_message(agent: SignAgent, message_id: str, question: str):
    """处理消息并发送回复。"""
    try:
        # 先发送一条卡片消息
        reply_message_id = await send_reply(message_id, "正在分析你的问题...", msg_type="interactive")
        if not reply_message_id:
            logger.error("发送初始消息失败")
            return

        # 收集输出并实时更新
        full_answer = ""
        async for text in agent.chat(question=question):
            full_answer += text
            logger.info(f"收到输出: {text[:100]}...")
            # 每次收到输出就更新卡片
            await update_message(reply_message_id, full_answer, is_thinking=True)

        # 最终更新，去掉思考状态
        await update_message(reply_message_id, full_answer, is_thinking=False)

        logger.info(f"完整回复: {full_answer[:200]}...")

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()
