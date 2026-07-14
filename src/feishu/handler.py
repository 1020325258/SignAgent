# -*- coding: utf-8 -*-
"""飞书消息处理模块 — 基于 lark-channel-sdk。"""

import os
import logging
import time

from . import get_channel
from ..agent import SignAgent
from .sender import send_reply, update_rich_card, _finish_streaming, PreviewHandle
from .card_builder import build_rich_card_content

logger = logging.getLogger(__name__)

# 清除记忆的命令
CLEAR_MEMORY_COMMANDS = ["清除记忆", "清除会话", "重新开始", "重置对话"]

# Agent 事件类型 → 处理函数映射（Open/Closed：新增事件类型只需添加映射）
EVENT_HANDLERS = {}


def _register_handler(event_type: str):
    """注册事件处理函数的装饰器。"""
    def decorator(func):
        EVENT_HANDLERS[event_type] = func
        return func
    return decorator


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


async def handle_message(agent: SignAgent, msg) -> None:
    """处理接收到的消息（async，由 channel SDK 的 _invoke 直接 await）。

    Args:
        agent: SignAgent 实例
        msg: lark-channel-sdk 的 InboundMessage 对象
    """
    try:
        message_id = msg.message_id
        chat_id = msg.chat_id
        user_id = msg.sender_id
        question = msg.body_text  # 自动解析 content + 去掉 @提及

        if not question or not question.strip():
            logger.info("忽略空消息")
            return

        question = question.strip()
        logger.info(f"收到消息: {question}, 用户: {user_id}, chat: {chat_id}")

        await process_message(agent, message_id, chat_id, question, user_id)

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)


async def process_message(agent: SignAgent, message_id: str, chat_id: str, question: str, user_id: str):
    """处理消息并发送回复。"""
    ch = get_channel()
    handle = PreviewHandle(message_id="")

    try:
        if question.strip() in CLEAR_MEMORY_COMMANDS:
            await agent.clear_memory(user_id)
            await send_reply(message_id, chat_id, "✅ 记忆已清除，我们重新开始吧！")
            return

        # 发送初始卡片（富卡片，带折叠面板）
        thinking_steps = [{"text": "正在分析你的问题...", "icon": "chat-forbidden", "color": "grey"}]
        tool_steps = []
        markdown = " "
        turn_start = time.time()

        initial_card = build_rich_card_content(thinking_steps, tool_steps, markdown, is_streaming=True)
        handle = await send_reply(message_id, chat_id, initial_card, msg_type="interactive", is_card_json=True)
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

            handler = EVENT_HANDLERS.get(event_type)
            if handler:
                await handler(handle, event, thinking_steps, tool_steps)
            else:
                logger.debug(f"忽略未知事件类型: {event_type}")

            # 每次事件后更新卡片
            if event_type == "text":
                full_answer += event["content"]
            await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                                   is_streaming=True, elapsed_seconds=elapsed)

        # 最终更新（force=True 跳过节流，状态改为完成）
        elapsed = time.time() - turn_start
        await update_rich_card(handle, thinking_steps, tool_steps, full_answer,
                               is_streaming=False, force=True, status="done", elapsed_seconds=elapsed)

        # 关闭 streaming_mode
        if handle.card_id:
            handle.sequence += 1
            await _finish_streaming(handle.card_id, handle.sequence)

        logger.info(f"完整回复: {full_answer[:200]}...")

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        # 异常时也要关闭 streaming_mode，避免卡片卡在 loading 状态
        if handle.card_id:
            handle.sequence += 1
            await _finish_streaming(handle.card_id, handle.sequence)


# ── 事件处理函数（通过 EVENT_HANDLERS 映射分发）──

@_register_handler("text")
async def _handle_text(handle, event, thinking_steps, tool_steps):
    """处理文本事件 — 文本累加在外层 update_rich_card 中处理，此处无需额外操作。"""
    pass


@_register_handler("thinking")
async def _handle_thinking(handle, event, thinking_steps, tool_steps):
    """处理思考事件。"""
    content = event["content"]
    if len(content) > 500:
        content = content[:500] + "..."
    thinking_steps.append({
        "text": content,
        "icon": "chat-forbidden",
        "color": "grey",
    })


@_register_handler("tool_use")
async def _handle_tool_use(handle, event, thinking_steps, tool_steps):
    """处理工具调用开始事件。"""
    name = event.get("name", "unknown")
    inp = event.get("input", "")
    tool_steps.append({
        "text": f"{name}\n{inp}",
        "icon": "chat-forbidden",
        "color": "grey",
        "done": False,
    })


@_register_handler("tool_result")
async def _handle_tool_result(handle, event, thinking_steps, tool_steps):
    """处理工具调用结果事件。"""
    if tool_steps:
        tool_steps[-1]["done"] = True
        is_error = event.get("is_error", False)
        tool_steps[-1]["color"] = "red" if is_error else "green"
