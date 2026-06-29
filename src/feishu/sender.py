# -*- coding: utf-8 -*-
"""飞书消息发送模块 - 借鉴 cc-connect 的实现。"""

import json
import re
import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from .client import get_feishu_config
from .card_builder import build_card_content
from .retry import with_retry

logger = logging.getLogger(__name__)

# 飞书限制（借鉴 cc-connect）
MAX_CARD_JSON_BYTES = 28000  # 卡片最大大小
MAX_CARD_TABLES = 5  # 卡片最多表格数


def _create_client() -> lark.Client:
    """创建飞书客户端。"""
    config = get_feishu_config()
    return lark.Client.builder() \
        .app_id(config["app_id"]) \
        .app_secret(config["app_secret"]) \
        .build()


def _count_markdown_tables(content: str) -> int:
    """计算 markdown 表格数量（借鉴 cc-connect）。

    Args:
        content: markdown 内容

    Returns:
        表格数量
    """
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


def _build_post_md_json(content: str) -> str:
    """构建 post 消息格式（借鉴 cc-connect）。

    post 格式支持 markdown 表格渲染，不受表格数量限制。

    Args:
        content: markdown 内容

    Returns:
        post 消息 JSON 字符串
    """
    post = {
        "zh_cn": {
            "content": [
                [
                    {"tag": "md", "text": content}
                ]
            ]
        }
    }
    return json.dumps(post, ensure_ascii=False)


def _compress_content(content: str, level: int = 0) -> str:
    """渐进式压缩内容（借鉴 cc-connect）。

    Args:
        content: 原始内容
        level: 压缩级别 (0-3)

    Returns:
        压缩后的内容
    """
    import re

    if level == 0:
        return content

    # 压缩级别配置（借鉴 cc-connect）
    configs = [
        {"max_value_len": 200, "max_rows": 50},  # level 1
        {"max_value_len": 120, "max_rows": 30},   # level 2
        {"max_value_len": 80, "max_rows": 20},    # level 3
    ]

    config = configs[min(level - 1, len(configs) - 1)]

    lines = content.split('\n')
    compressed = []
    row_count = 0

    for line in lines:
        # 截断过长的值
        if len(line) > config["max_value_len"]:
            line = line[:config["max_value_len"]] + "..."

        # 限制行数
        if row_count < config["max_rows"]:
            compressed.append(line)
            row_count += 1

    return '\n'.join(compressed)


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
        client = _create_client()

        # 根据消息类型构造内容
        if msg_type == "interactive":
            # 检测表格数量，超过限制则降级到 post 格式（借鉴 cc-connect）
            table_count = _count_markdown_tables(content)
            if table_count > MAX_CARD_TABLES:
                logger.info(f"表格数量 ({table_count}) 超过限制 ({MAX_CARD_TABLES})，降级到 post 格式")
                card_content = _build_post_md_json(content)
                msg_type = "post"
            else:
                card_content = build_card_content(content, is_thinking=True)
        else:
            card_content = json.dumps({"text": content})

        # 渐进式压缩（借鉴 cc-connect）
        for level in range(4):
            if level > 0:
                compressed_content = _compress_content(content, level)
                card_content = build_card_content(compressed_content, is_thinking=True)
                logger.info(f"内容过大，压缩级别 {level}")

            # 检查大小
            if len(card_content.encode('utf-8')) <= MAX_CARD_JSON_BYTES:
                break

        # 构造回复请求
        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(card_content)
                .msg_type(msg_type)
                .build()) \
            .build()

        # 发送回复（带重试）
        response = with_retry(client.im.v1.message.reply, request)

        if response.success():
            reply_message_id = response.data.message_id
            logger.info(f"回复发送成功: {reply_message_id}")
            return reply_message_id
        else:
            # 速率限制静默跳过（借鉴 cc-connect）
            if response.code == 99991400:
                logger.debug(f"速率限制，跳过: {response.code}")
                return None

            logger.error(f"回复发送失败: {response.code} - {response.msg}")
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
        client = _create_client()

        # 构建卡片内容
        card_content = build_card_content(content, is_thinking=is_thinking)

        # 渐进式压缩（借鉴 cc-connect）
        for level in range(4):
            if level > 0:
                compressed_content = _compress_content(content, level)
                card_content = build_card_content(compressed_content, is_thinking=is_thinking)
                logger.info(f"内容过大，压缩级别 {level}")

            # 检查大小
            if len(card_content.encode('utf-8')) <= MAX_CARD_JSON_BYTES:
                break

        # 构造更新请求
        request = PatchMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(PatchMessageRequestBody.builder()
                .content(card_content)
                .build()) \
            .build()

        # 更新消息（带重试）
        response = with_retry(client.im.v1.message.patch, request)

        if response.success():
            logger.debug(f"消息更新成功: {message_id}")
        else:
            # 速率限制静默跳过（借鉴 cc-connect）
            if response.code == 99991400:
                logger.debug(f"速率限制，跳过: {response.code}")
                return

            logger.error(f"消息更新失败: {response.code} - {response.msg}")

    except Exception as e:
        logger.error(f"更新消息失败: {e}")
