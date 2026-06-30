# -*- coding: utf-8 -*-
"""飞书 API 集成测试。

实际调用飞书 API 发送消息，验证 sender.py 的格式选择和内容构建是否正确。

使用方式:
    # 设置环境变量后运行
    FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx python3 -m pytest tests/test_feishu_api.py -v

    # 跳过（CI 等无凭证环境自动 skip）
    python3 -m pytest tests/test_feishu_api.py -v
"""

import json
import os
import sys
import pytest

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 检查凭证
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
TEST_CHAT_ID = os.getenv("FEISHU_TEST_CHAT_ID", "")  # 测试群 chat_id
TEST_MESSAGE_ID = os.getenv("FEISHU_TEST_MESSAGE_ID", "")  # 要回复的消息 message_id

HAS_CREDENTIALS = bool(APP_ID and APP_SECRET and TEST_CHAT_ID)

pytestmark = pytest.mark.skipif(
    not HAS_CREDENTIALS,
    reason="需要 FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_TEST_CHAT_ID 环境变量"
)


def _create_client():
    from src.feishu.client import get_feishu_config
    config = get_feishu_config()
    return lark.Client.builder() \
        .app_id(config["app_id"]) \
        .app_secret(config["app_secret"]) \
        .build()


class TestSendText:
    """测试发送纯文本消息。"""

    def test_send_text_message(self):
        """发送纯文本消息到群聊。"""
        client = _create_client()
        body = json.dumps({"text": "🤖 测试消息：纯文本格式"}, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("text")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"


class TestSendCard:
    """测试发送卡片消息。"""

    def test_send_card_legacy_format(self):
        """发送旧版卡片格式。"""
        client = _create_client()
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "markdown",
                    "content": "🤖 测试消息：**旧版卡片格式**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"
                }
            ]
        }
        body = json.dumps(card, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("interactive")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"

    def test_send_card_schema_2_0(self):
        """发送 schema 2.0 卡片格式。"""
        client = _create_client()
        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": "🤖 测试消息：**Schema 2.0 卡片**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"
                    }
                ]
            }
        }
        body = json.dumps(card, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("interactive")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"

    def test_send_card_many_markdown_tables(self):
        """发送包含多个 markdown 表格的卡片（不转 Table 组件）。"""
        client = _create_client()
        tables = []
        for i in range(3):
            tables.append(f"### 表格 {i+1}\n\n| 配置项 | 值 |\n|------|----|\n| key_{i} | value_{i} |")
        content = "🤖 测试消息：**多表格卡片**\n\n" + "\n\n".join(tables)

        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "elements": [
                    {"tag": "markdown", "content": content}
                ]
            }
        }
        body = json.dumps(card, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("interactive")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"


class TestSendPost:
    """测试发送 post 消息。"""

    def test_send_post_with_md_tag(self):
        """发送 post 格式（md 标签）。"""
        client = _create_client()
        post = {
            "zh_cn": {
                "content": [
                    [
                        {"tag": "md", "text": "🤖 测试消息：**Post 格式 (md 标签)**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"}
                    ]
                ]
            }
        }
        body = json.dumps(post, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("post")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"

    def test_send_post_many_tables(self):
        """发送包含多个表格的 post 消息（超过 5 个表格的场景）。"""
        client = _create_client()
        tables = []
        for i in range(8):
            tables.append(f"### 表格 {i+1}\n\n| 配置项 | 值 |\n|------|----|\n| key_{i} | value_{i} |")
        content = "🤖 测试消息：**Post 格式多表格**\n\n" + "\n\n".join(tables)

        post = {
            "zh_cn": {
                "content": [
                    [{"tag": "md", "text": content}]
                ]
            }
        }
        body = json.dumps(post, ensure_ascii=False)

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("post")
                .content(body)
                .build()) \
            .build()

        response = client.im.v1.message.create(request)
        assert response.success(), f"发送失败: {response.code} - {response.msg}"


class TestReplyMessage:
    """测试回复消息（自包含：先发消息再回复）。"""

    def _send_text(self, client, text):
        """发送文本消息，返回 message_id。"""
        body = json.dumps({"text": text}, ensure_ascii=False)
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("text")
                .content(body)
                .build()) \
            .build()
        response = client.im.v1.message.create(request)
        assert response.success()
        return response.data.message_id

    def test_reply_text(self):
        """回复文本消息。"""
        client = _create_client()
        msg_id = self._send_text(client, "🤖 测试：回复目标")

        body = json.dumps({"text": "🤖 测试回复：纯文本"}, ensure_ascii=False)
        request = ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(body)
                .msg_type("text")
                .build()) \
            .build()

        response = client.im.v1.message.reply(request)
        assert response.success(), f"回复失败: {response.code} - {response.msg}"

    def test_reply_card(self):
        """回复卡片消息。"""
        client = _create_client()
        msg_id = self._send_text(client, "🤖 测试：回复目标（卡片）")

        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "elements": [
                    {"tag": "markdown", "content": "🤖 测试回复：**卡片格式**"}
                ]
            }
        }
        body = json.dumps(card, ensure_ascii=False)

        request = ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(body)
                .msg_type("interactive")
                .build()) \
            .build()

        response = client.im.v1.message.reply(request)
        assert response.success(), f"回复失败: {response.code} - {response.msg}"

    def test_reply_post(self):
        """回复 post 消息。"""
        client = _create_client()
        msg_id = self._send_text(client, "🤖 测试：回复目标（post）")

        post = {
            "zh_cn": {
                "content": [
                    [{"tag": "md", "text": "🤖 测试回复：**Post 格式**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"}]
                ]
            }
        }
        body = json.dumps(post, ensure_ascii=False)

        request = ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(body)
                .msg_type("post")
                .build()) \
            .build()

        response = client.im.v1.message.reply(request)
        assert response.success(), f"回复失败: {response.code} - {response.msg}"


class TestPatchMessage:
    """测试更新消息（先发卡片再更新）。"""

    def test_send_then_patch_card(self):
        """先发卡片消息，再更新它。"""
        client = _create_client()

        # 1. 先发一张卡片
        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "elements": [
                    {"tag": "markdown", "content": "🤖 测试更新：**原始内容**"}
                ]
            }
        }
        body = json.dumps(card, ensure_ascii=False)

        send_request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("interactive")
                .content(body)
                .build()) \
            .build()

        send_response = client.im.v1.message.create(send_request)
        assert send_response.success(), f"发送失败: {send_response.code} - {send_response.msg}"

        message_id = send_response.data.message_id

        # 2. 更新这张卡片
        card["body"]["elements"][0]["content"] = "🤖 测试更新：**已更新内容**"
        body = json.dumps(card, ensure_ascii=False)

        patch_request = PatchMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(PatchMessageRequestBody.builder()
                .content(body)
                .build()) \
            .build()

        patch_response = client.im.v1.message.patch(patch_request)
        assert patch_response.success(), f"更新失败: {patch_response.code} - {patch_response.msg}"


class TestSenderIntegration:
    """测试 sender.py 模块的集成测试（自包含）。"""

    def _send_target_message(self):
        """发送一条目标消息，返回 message_id。"""
        client = _create_client()
        body = json.dumps({"text": "🤖 sender 测试：目标消息"}, ensure_ascii=False)
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(TEST_CHAT_ID)
                .msg_type("text")
                .content(body)
                .build()) \
            .build()
        response = client.im.v1.message.create(request)
        assert response.success()
        return response.data.message_id

    @pytest.mark.asyncio
    async def test_send_reply_text(self):
        """send_reply 发送文本消息。"""
        from src.feishu.sender import send_reply
        msg_id = self._send_target_message()
        result = await send_reply(msg_id, "🤖 sender 测试：纯文本", msg_type="text")
        assert result is not None, "send_reply 返回 None，发送失败"

    @pytest.mark.asyncio
    async def test_send_reply_card(self):
        """send_reply 发送卡片消息。"""
        from src.feishu.sender import send_reply
        msg_id = self._send_target_message()
        result = await send_reply(msg_id, "🤖 sender 测试：**卡片格式**", msg_type="interactive")
        assert result is not None, "send_reply 返回 None，发送失败"

    @pytest.mark.asyncio
    async def test_send_reply_many_tables_post(self):
        """send_reply 超过 5 个表格用 post 格式。"""
        from src.feishu.sender import send_reply
        msg_id = self._send_target_message()
        table = "| a | b |\n|---|---|\n| 1 | 2 |"
        content = "🤖 sender 测试：**多表格 post**\n\n" + "\n\n".join([table] * 10)
        result = await send_reply(msg_id, content, msg_type="interactive")
        assert result is not None, "send_reply 返回 None，发送失败"
