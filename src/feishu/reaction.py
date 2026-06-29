# -*- coding: utf-8 -*-
"""飞书 Reaction 模块 - 打字状态指示器。"""

import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from .client import get_feishu_config

logger = logging.getLogger(__name__)

# Emoji 类型
EMOJI_PROCESSING = "PROCESSING"  # 处理中
EMOJI_DONE = "DONE"  # 完成
EMOJI_THUMBSUP = "THUMBSUP"  # 点赞


def _create_client() -> lark.Client:
    """创建飞书客户端。"""
    config = get_feishu_config()
    return lark.Client.builder() \
        .app_id(config["app_id"]) \
        .app_secret(config["app_secret"]) \
        .build()


def add_reaction(message_id: str, emoji_type: str = EMOJI_PROCESSING) -> str:
    """
    添加 emoji reaction

    Args:
        message_id: 消息 ID
        emoji_type: emoji 类型

    Returns:
        reaction ID，失败返回 None
    """
    try:
        client = _create_client()

        request = CreateMessageReactionRequest.builder() \
            .message_id(message_id) \
            .request_body(CreateMessageReactionRequestBody.builder()
                .reaction_type(Reaction.builder()
                    .emoji_type(emoji_type)
                    .build())
                .build()) \
            .build()

        response = client.im.v1.message_reaction.create(request)

        if response.success():
            reaction_id = response.data.reaction_id
            logger.debug(f"添加 reaction 成功: {reaction_id}")
            return reaction_id
        else:
            logger.error(f"添加 reaction 失败: {response.code} - {response.msg}")
            return None

    except Exception as e:
        logger.error(f"添加 reaction 失败: {e}")
        return None


def remove_reaction(message_id: str, reaction_id: str):
    """
    移除 emoji reaction

    Args:
        message_id: 消息 ID
        reaction_id: reaction ID
    """
    try:
        client = _create_client()

        request = DeleteMessageReactionRequest.builder() \
            .message_id(message_id) \
            .reaction_id(reaction_id) \
            .build()

        response = client.im.v1.message_reaction.delete(request)

        if response.success():
            logger.debug(f"移除 reaction 成功: {reaction_id}")
        else:
            logger.error(f"移除 reaction 失败: {response.code} - {response.msg}")

    except Exception as e:
        logger.error(f"移除 reaction 失败: {e}")


class TypingIndicator:
    """打字状态指示器。"""

    def __init__(self, message_id: str):
        self.message_id = message_id
        self.reaction_id = None

    def start(self):
        """开始处理，添加 processing emoji。"""
        self.reaction_id = add_reaction(self.message_id, EMOJI_PROCESSING)

    def stop(self):
        """处理完成，移除 processing emoji。"""
        if self.reaction_id:
            remove_reaction(self.message_id, self.reaction_id)
            self.reaction_id = None

    def done(self):
        """处理完成，添加 done emoji。"""
        self.stop()
        add_reaction(self.message_id, EMOJI_DONE)
