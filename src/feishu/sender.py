# -*- coding: utf-8 -*-
"""飞书消息发送模块。"""

import json
import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from .client import get_feishu_config
from .card_builder import build_card_content

logger = logging.getLogger(__name__)


async def send_reply(message_id: str, content: str, msg_type: str = "text") -> str:
    """
    发送回复消息

    Args:
        message_id: 原始消息 ID
        content: 回复内容
        msg_type: 消息类型，text 或 interactive

    Returns:
        回复消息的 message_id，失败返回 None
    """
    try:
        config = get_feishu_config()

        # 创建 Client
        client = lark.Client.builder() \
            .app_id(config["app_id"]) \
            .app_secret(config["app_secret"]) \
            .build()

        # 根据消息类型构造内容
        if msg_type == "interactive":
            card_content = build_card_content(content, is_thinking=True)
        else:
            card_content = json.dumps({"text": content})

        # 构造回复请求
        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(card_content)
                .msg_type(msg_type)
                .build()) \
            .build()

        # 发送回复
        response = client.im.v1.message.reply(request)

        if response.success():
            reply_message_id = response.data.message_id
            logger.info(f"回复发送成功: {reply_message_id}")
            return reply_message_id
        else:
            logger.error(f"回复发送失败: {response.code} - {response.msg}")

            # 如果是内容过长，尝试截断后重试
            if response.code in (230001, 230099) and msg_type == "interactive":
                logger.info("内容过长，尝试截断后重试")
                truncated_content = _truncate_content(content)
                return await send_reply(message_id, truncated_content, msg_type)

            return None

    except Exception as e:
        logger.error(f"发送回复失败: {e}")
        return None


async def update_message(message_id: str, content: str, is_thinking: bool = True):
    """
    更新消息内容（用于流式输出）

    Args:
        message_id: 要更新的消息 ID
        content: 新的消息内容
        is_thinking: 是否仍在思考中
    """
    try:
        config = get_feishu_config()

        # 创建 Client
        client = lark.Client.builder() \
            .app_id(config["app_id"]) \
            .app_secret(config["app_secret"]) \
            .build()

        # 构建卡片内容
        card_content = build_card_content(content, is_thinking=is_thinking)

        # 构造更新请求
        request = PatchMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(PatchMessageRequestBody.builder()
                .content(card_content)
                .build()) \
            .build()

        # 更新消息
        response = client.im.v1.message.patch(request)

        if response.success():
            logger.debug(f"消息更新成功: {message_id}")
        else:
            logger.error(f"消息更新失败: {response.code} - {response.msg}")

            # 如果是内容过长，尝试截断后重试
            if response.code in (230001, 230099):
                logger.info("内容过长，尝试截断后重试")
                truncated_content = _truncate_content(content)
                await update_message(message_id, truncated_content, is_thinking)

    except Exception as e:
        logger.error(f"更新消息失败: {e}")


def _truncate_content(content: str, max_length: int = 10000) -> str:
    """截断内容到指定长度。

    Args:
        content: 原始内容
        max_length: 最大长度

    Returns:
        截断后的内容
    """
    if len(content) <= max_length:
        return content

    return content[:max_length] + "\n\n... (内容过长，已截断)"
