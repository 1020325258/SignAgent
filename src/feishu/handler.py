# -*- coding: utf-8 -*-
"""飞书消息处理模块。"""

import os
import json
import logging
import asyncio
import time

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from ..agent import SignAgent
from .sender import send_reply, update_message, update_rich_card, PreviewHandle
from .card_builder import build_rich_card_content

logger = logging.getLogger(__name__)

# 清除记忆的命令
CLEAR_MEMORY_COMMANDS = ["清除记忆", "清除会话", "重新开始", "重置对话"]


def init_agent() -> SignAgent:
    """初始化 SignAgent。"""
    project_dir = os.getenv("SIGN_AGENT_PROJECT_DIR", ".")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    session_dir = os.getenv("SESSION_DIR", "./sessions")

    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(
        project_dir=project_dir,
        api_config=api_config,
        debug=debug,
        session_dir=session_dir,
    )
    logger.info(f"✅ SignAgent 初始化完成 (debug={debug})")
    return agent


def handle_message(agent: SignAgent, data: P2ImMessageReceiveV1) -> None:
    """处理接收到的消息（同步版本）。"""
    try:
        logger.info(f"收到消息事件: {data}")
        message = data.event.message
        sender = data.event.sender

        message_type = message.message_type
        content = message.content
        message_id = message.message_id
        user_id = sender.sender_id.open_id

        if message_type != "text":
            logger.info(f"忽略非文本消息: {message_type}")
            return

        try:
            content_data = json.loads(content)
            question = content_data.get("text", "")
        except json.JSONDecodeError:
            question = content

        if question.startswith("@"):
            question = question.split(" ", 1)[-1].strip()

        if not question:
            return

        logger.info(f"收到消息: {question}, 用户: {user_id}")

        import threading
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_message(agent, message_id, question, user_id))
            finally:
                loop.close()

        thread = threading.Thread(target=run_async)
        thread.start()

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()


async def process_message(agent: SignAgent, message_id: str, question: str, user_id: str):
    """处理消息并发送回复。"""
    try:
        if question.strip() in CLEAR_MEMORY_COMMANDS:
            await agent.clear_memory(user_id)
            await send_reply(message_id, "✅ 记忆已清除，我们重新开始吧！")
            return

        # 发送初始卡片（富卡片，带折叠面板）
        thinking_steps = [{"text": "正在分析你的问题...", "icon": "chat-forbidden", "color": "grey"}]
        tool_steps = []
        markdown = " "
        turn_start = time.time()

        initial_card = build_rich_card_content(thinking_steps, tool_steps, markdown, is_streaming=True)
        handle = await send_reply(message_id, initial_card, msg_type="interactive", is_card_json=True)
        if not handle.message_id:
            logger.error("发送初始消息失败")
            return

        # 收集输出并实时更新
        full_answer = ""
        thinking_steps = []
        tool_steps = []

        async for event in agent.chat(question=question, user_id=user_id):
            event_type = event.get("type")
            elapsed = time.time() - turn_start

            if event_type == "text":
                full_answer += event["content"]
                await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                                       is_streaming=True, elapsed_seconds=elapsed)

            elif event_type == "thinking":
                content = event["content"]
                if len(content) > 500:
                    content = content[:500] + "..."
                thinking_steps.append({
                    "text": content,
                    "icon": "chat-forbidden",
                    "color": "grey",
                })
                await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                                       is_streaming=True, elapsed_seconds=elapsed)

            elif event_type == "tool_use":
                name = event.get("name", "unknown")
                inp = event.get("input", "")
                tool_steps.append({
                    "text": f"{name}\n{inp}",
                    "icon": "chat-forbidden",
                    "color": "grey",
                    "done": False,
                })
                await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                                       is_streaming=True, elapsed_seconds=elapsed)

            elif event_type == "tool_result":
                if tool_steps:
                    tool_steps[-1]["done"] = True
                    is_error = event.get("is_error", False)
                    tool_steps[-1]["color"] = "red" if is_error else "green"
                await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                                       is_streaming=True, elapsed_seconds=elapsed)

        # 最终更新（force=True 跳过节流，状态改为完成）
        elapsed = time.time() - turn_start
        await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                               is_streaming=False, force=True, status="done", elapsed_seconds=elapsed)

        logger.info(f"完整回复: {full_answer[:200]}...")

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()
