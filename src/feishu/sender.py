# -*- coding: utf-8 -*-
"""飞书消息发送模块 - 对照 cc-connect 实现。

支持两种更新方式：
1. Cardkit-v1 流式文本更新（首选）— 只更新 markdown 元素，支持打字机动画
2. Patch 全量更新（兜底）— 替换整个卡片
"""

import json
import logging
import time
from dataclasses import dataclass, field

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from .client import get_feishu_config
from .card_builder import build_card_content, build_post_md_json, build_rich_card_content, _preprocess_markdown
from .retry import with_retry

logger = logging.getLogger(__name__)

# 飞书限制
MAX_CARD_JSON_BYTES = 28000
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


def _create_client() -> lark.Client:
    """创建飞书客户端。"""
    config = get_feishu_config()
    return lark.Client.builder() \
        .app_id(config["app_id"]) \
        .app_secret(config["app_secret"]) \
        .build()


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


# ── Cardkit-v1 操作 ──

def create_card_entity(client: lark.Client, card_json: str) -> str:
    """创建卡片实体，返回 card_id。失败返回空字符串。"""
    try:
        from lark_oapi.api.cardkit.v1 import CreateCardRequest, CreateCardRequestBody

        request = CreateCardRequest.builder() \
            .request_body(CreateCardRequestBody.builder()
                .type("card_json")
                .data(card_json)
                .build()) \
            .build()

        response = with_retry(client.cardkit.v1.card.create, request)

        if response.success() and response.data and response.data.card_id:
            card_id = response.data.card_id
            logger.info(f"创建卡片实体成功: {card_id}")
            return card_id
        else:
            logger.warning(f"创建卡片实体失败: {getattr(response, 'code', 'unknown')} - {getattr(response, 'msg', 'unknown')}")
            return ""
    except Exception as e:
        logger.warning(f"创建卡片实体异常: {e}")
        return ""


def stream_card_text(client: lark.Client, card_id: str, content: str, sequence: int) -> bool:
    """流式更新卡片 markdown 元素。成功返回 True。"""
    try:
        from lark_oapi.api.cardkit.v1 import ContentCardElementRequest, ContentCardElementRequestBody

        request = ContentCardElementRequest.builder() \
            .card_id(card_id) \
            .element_id(MAIN_TEXT_ELEMENT_ID) \
            .request_body(ContentCardElementRequestBody.builder()
                .content(content)
                .sequence(sequence)
                .build()) \
            .build()

        response = with_retry(client.cardkit.v1.card_element.content, request)

        if response.success():
            return True
        else:
            if getattr(response, 'code', 0) == 99991400:
                logger.debug(f"流式更新速率限制，跳过")
                return True
            logger.warning(f"流式更新失败: {getattr(response, 'code', 'unknown')} - {getattr(response, 'msg', 'unknown')}")
            return False
    except Exception as e:
        logger.warning(f"流式更新异常: {e}")
        return False


# ── 发送消息 ──

def _reply_message(client: lark.Client, message_id: str, msg_type: str, body: str) -> str:
    """发送回复消息。返回 reply_message_id，失败返回 None。"""
    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
            .content(body)
            .msg_type(msg_type)
            .build()) \
        .build()

    response = with_retry(client.im.v1.message.reply, request)

    if response.success():
        reply_message_id = response.data.message_id
        logger.info(f"回复发送成功: {reply_message_id}")
        return reply_message_id
    else:
        if response.code == 99991400:
            logger.debug(f"速率限制，跳过: {response.code}")
            return None
        logger.error(f"回复发送失败: {response.code} - {response.msg}")
        return None


async def send_reply(message_id: str, content: str, msg_type: str = "text", is_card_json: bool = False) -> PreviewHandle:
    """发送回复消息。

    Args:
        message_id: 原始消息 ID
        content: 回复内容
        msg_type: 消息类型
        is_card_json: 如果为 True，content 已经是 card JSON，直接使用

    Returns:
        PreviewHandle（包含 message_id 和 card_id）
    """
    try:
        client = _create_client()

        if msg_type != "interactive":
            body = json.dumps({"text": content}, ensure_ascii=False)
            msg_id = _reply_message(client, message_id, "text", body)
            return PreviewHandle(message_id=msg_id or "")

        if is_card_json:
            card_json = content
        else:
            table_count = _count_markdown_tables(content)
            if table_count > MAX_CARD_TABLES:
                body = build_post_md_json(content)
                msg_id = _reply_message(client, message_id, "post", body)
                return PreviewHandle(message_id=msg_id or "")
            card_json = build_card_content(content, is_thinking=True)

        # 尝试 cardkit-v1 两步流程
        card_id = create_card_entity(client, card_json)

        if card_id:
            send_body = json.dumps({"type": "card", "data": {"card_id": card_id}}, ensure_ascii=False)
            msg_id = _reply_message(client, message_id, "interactive", send_body)
            if msg_id:
                return PreviewHandle(message_id=msg_id, card_id=card_id)

        # 降级：内联 card JSON
        msg_id = _reply_message(client, message_id, "interactive", card_json)
        return PreviewHandle(message_id=msg_id or "")

    except Exception as e:
        logger.error(f"发送回复失败: {e}")
        return PreviewHandle(message_id="")


def _patch_card(client: lark.Client, message_id: str, card_content: str):
    """Patch 全量更新卡片。"""
    request = PatchMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(PatchMessageRequestBody.builder()
            .content(card_content)
            .build()) \
        .build()

    response = with_retry(client.im.v1.message.patch, request)

    if response.success():
        logger.debug(f"消息更新成功: {message_id}")
    else:
        if response.code == 99991400:
            logger.debug(f"速率限制，跳过: {response.code}")
            return
        logger.error(f"消息更新失败: {response.code} - {response.msg}")


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
        client = _create_client()

        # 优先用 cardkit-v1 流式更新（只更新 markdown 正文）
        if handle.card_id:
            handle.sequence += 1
            text = _preprocess_markdown(markdown)
            if stream_card_text(client, handle.card_id, text, handle.sequence):
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
        _patch_card(client, handle.message_id, card_json)
        handle.last_update_time = time.time()
        handle.last_content_len = content_len

    except Exception as e:
        logger.error(f"更新富卡片失败: {e}")


async def update_message(handle: PreviewHandle, content: str, is_thinking: bool = True):
    """更新消息内容（简单卡片，用于非富卡片场景）。"""
    if not handle.message_id:
        return

    try:
        client = _create_client()

        if handle.card_id:
            handle.sequence += 1
            text = _preprocess_markdown(content)
            if is_thinking:
                text = "⏳ **正在思考中...**\n\n---\n\n" + text
            if stream_card_text(client, handle.card_id, text, handle.sequence):
                return
            logger.warning("cardkit-v1 流式更新失败，降级为 Patch")

        card_content = build_card_content(content, is_thinking=is_thinking)
        _patch_card(client, handle.message_id, card_content)

    except Exception as e:
        logger.error(f"更新消息失败: {e}")
