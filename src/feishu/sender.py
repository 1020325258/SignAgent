# -*- coding: utf-8 -*-
"""飞书消息发送模块 — 基于 lark-channel-sdk。

支持两种更新方式：
1. Cardkit-v1 流式文本更新（首选）— 只更新 markdown 元素，支持打字机动画
2. Patch 全量更新（兜底）— 替换整个卡片
"""

import json
import logging
import time
from dataclasses import dataclass

from . import get_channel
from .card_builder import build_card_content, build_post_md_json, build_rich_card_content, preprocess_markdown

logger = logging.getLogger(__name__)

# 飞书限制
MAX_CARD_TABLES = 5
MAIN_TEXT_ELEMENT_ID = "main_text"

# 节流配置（对照 cc-connect）
STREAM_THROTTLE_MS = 200       # cardkit-v1 流式更新最小间隔（毫秒）
STREAM_THROTTLE_CHARS = 20     # cardkit-v1 流式更新最小字符增量
PATCH_THROTTLE_MS = 1500       # Patch 全量更新最小间隔（毫秒）
PATCH_THROTTLE_CHARS = 30      # Patch 全量更新最小字符增量


@dataclass
class PreviewHandle:
    """消息预览句柄，用于流式更新。"""
    message_id: str
    card_id: str = ""           # cardkit-v1 实体 ID（空 = 无流式更新）
    sequence: int = 0           # 流式更新单调递增计数器
    last_update_time: float = 0 # 上次更新时间戳
    last_content_len: int = 0   # 上次更新时的内容长度


def _count_markdown_tables(content: str) -> int:
    """计算 markdown 表格数量。"""
    count = 0
    in_table = False
    for line in content.split('\n'):
        stripped = line.strip()
        is_table_line = len(stripped) > 1 and stripped[0] == '|' and stripped[-1] == '|'
        if is_table_line and not in_table:
            count += 1
            in_table = True
        elif not is_table_line:
            in_table = False
    return count


def _should_throttle(handle: PreviewHandle, content_len: int, throttle_ms: int, throttle_chars: int) -> bool:
    """检查是否应该节流（跳过本次更新）。"""
    now = time.time()
    elapsed_ms = (now - handle.last_update_time) * 1000
    char_delta = content_len - handle.last_content_len
    return elapsed_ms < throttle_ms and char_delta < throttle_chars


# ── Cardkit-v1 操作（channel SDK）──

async def _create_card_instance(card_json: str) -> str:
    """创建卡片实体，返回 card_id。失败返回空字符串。"""
    try:
        card_dict = json.loads(card_json)
        card_id = await get_channel().create_card_instance(card_dict)
        if card_id:
            logger.info(f"创建卡片实体成功: {card_id}")
            return card_id
        logger.warning("创建卡片实体失败: 返回空 card_id")
        return ""
    except Exception as e:
        logger.warning(f"创建卡片实体异常: {e}")
        return ""


async def _stream_card_text(card_id: str, content: str, sequence: int) -> bool:
    """流式更新卡片 markdown 元素。成功返回 True。"""
    try:
        await get_channel().update_card_element_content(card_id, MAIN_TEXT_ELEMENT_ID, content, sequence)
        return True
    except Exception as e:
        logger.warning(f"流式更新异常: {e}")
        return False


async def _finish_streaming(card_id: str, sequence: int) -> bool:
    """完成流式卡片（关闭 streaming_mode）。"""
    try:
        await get_channel().finish_streaming_card(card_id, sequence)
        return True
    except Exception as e:
        logger.warning(f"完成流式卡片异常: {e}")
        return False


# ── 发送消息 ──

async def send_reply(message_id: str, chat_id: str, content: str, msg_type: str = "text", is_card_json: bool = False) -> PreviewHandle:
    """发送回复消息。

    Args:
        message_id: 原始消息 ID
        chat_id: 会话 ID
        content: 回复内容
        msg_type: 消息类型
        is_card_json: 如果为 True，content 已经是 card JSON，直接使用

    Returns:
        PreviewHandle（包含 message_id 和 card_id）
    """
    try:
        if msg_type != "interactive":
            result = await get_channel().send(chat_id, {"text": content}, {"reply_to": message_id})
            msg_id = result.message_id if result and result.success else ""
            return PreviewHandle(message_id=msg_id or "")

        if is_card_json:
            card_json = content
        else:
            table_count = _count_markdown_tables(content)
            if table_count > MAX_CARD_TABLES:
                post_body = build_post_md_json(content)
                result = await get_channel().send(chat_id, {"post": json.loads(post_body)}, {"reply_to": message_id})
                msg_id = result.message_id if result and result.success else ""
                return PreviewHandle(message_id=msg_id or "")
            card_json = build_card_content(content, is_thinking=True)

        # 尝试 cardkit-v1 两步流程
        card_id = await _create_card_instance(card_json)

        if card_id:
            result = await get_channel().send_card_by_reference(chat_id, card_id, reply_to=message_id)
            if result and result.success:
                msg_id = result.message_id
                return PreviewHandle(message_id=msg_id, card_id=card_id)

        # 降级：内联 card JSON
        card_dict = json.loads(card_json)
        result = await get_channel().send(chat_id, {"card": card_dict}, {"reply_to": message_id})
        msg_id = result.message_id if result and result.success else ""
        return PreviewHandle(message_id=msg_id or "")

    except Exception as e:
        logger.error(f"发送回复失败: {e}")
        return PreviewHandle(message_id="")


async def _patch_card(message_id: str, card_content: str):
    """Patch 全量更新卡片。"""
    try:
        card_dict = json.loads(card_content)
        await get_channel().update_card(message_id, card_dict)
        logger.debug(f"消息更新成功: {message_id}")
    except Exception as e:
        logger.warning(f"消息更新失败: {e}")


async def update_rich_card(
    handle: PreviewHandle,
    thinking_steps: list,
    tool_steps: list,
    markdown: str,
    is_streaming: bool = True,
    force: bool = False,
    status: str = "working",
    elapsed_seconds: float = 0,
    model: str = "",
):
    """更新富卡片（带折叠面板）。

    对照 cc-connect 的节流逻辑：
    - cardkit-v1 流式更新：200ms 间隔 或 20 字符增量
    - Patch 全量更新：1500ms 间隔 或 30 字符增量

    Args:
        force: 强制更新（跳过节流，用于最终更新）
        status: 状态（thinking/working/done/error）
        elapsed_seconds: 已用时间（秒）
        model: 模型名称
    """
    if not handle.message_id:
        return

    content_len = len(markdown)

    # 节流检查
    if not force:
        if handle.card_id:
            if _should_throttle(handle, content_len, STREAM_THROTTLE_MS, STREAM_THROTTLE_CHARS):
                return
        else:
            if _should_throttle(handle, content_len, PATCH_THROTTLE_MS, PATCH_THROTTLE_CHARS):
                return

    try:
        # 流式中：优先用 cardkit-v1 流式更新（只更新 markdown 正文）
        # 最终更新：走 Patch 路径更新整张卡片（header + 面板 + 正文 + footer）
        if handle.card_id and is_streaming:
            handle.sequence += 1
            text = preprocess_markdown(markdown)
            if await _stream_card_text(handle.card_id, text, handle.sequence):
                handle.last_update_time = time.time()
                handle.last_content_len = content_len
                return
            logger.warning("cardkit-v1 流式更新失败，降级为 Patch")

        # 降级：Patch 全量更新（包含折叠面板 + markdown 正文）
        card_json = build_rich_card_content(
            thinking_steps, tool_steps, markdown,
            is_streaming=is_streaming, status=status,
            elapsed_seconds=elapsed_seconds, model=model,
        )
        await _patch_card(handle.message_id, card_json)
        handle.last_update_time = time.time()
        handle.last_content_len = content_len

    except Exception as e:
        logger.error(f"更新富卡片失败: {e}")
