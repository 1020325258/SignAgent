# -*- coding: utf-8 -*-
"""飞书 API 集成测试（基于 lark-channel-sdk）。

实际调用飞书 API 发送消息，验证 sender.py 的格式选择和内容构建是否正确。

使用方式:
    # 设置环境变量后运行
    FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx FEISHU_TEST_CHAT_ID=xxx python3 -m pytest tests/test_feishu_api.py -v

    # 跳过（CI 等无凭证环境自动 skip）
    python3 -m pytest tests/test_feishu_api.py -v
"""

import json
import os
import sys
import pytest
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lark_channel import FeishuChannel

# 检查凭证
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
TEST_CHAT_ID = os.getenv("FEISHU_TEST_CHAT_ID", "")  # 测试群 chat_id

HAS_CREDENTIALS = bool(APP_ID and APP_SECRET and TEST_CHAT_ID)

pytestmark = pytest.mark.skipif(
    not HAS_CREDENTIALS,
    reason="需要 FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_TEST_CHAT_ID 环境变量"
)


@pytest.fixture(scope="module")
def channel():
    """创建 channel 实例。"""
    ch = FeishuChannel(app_id=APP_ID, app_secret=APP_SECRET)
    return ch


@pytest.fixture(scope="module")
def event_loop():
    """创建事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestSendText:
    """测试发送纯文本消息。"""

    @pytest.mark.asyncio
    async def test_send_text_message(self, channel):
        """发送纯文本消息到群聊。"""
        result = await channel.send(TEST_CHAT_ID, {"text": "🤖 测试消息：纯文本格式"})
        assert result.success, f"发送失败: {result.error}"


class TestSendCard:
    """测试发送卡片消息。"""

    @pytest.mark.asyncio
    async def test_send_card_schema_2_0(self, channel):
        """发送 schema 2.0 卡片格式。"""
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
        result = await channel.send(TEST_CHAT_ID, {"card": card})
        assert result.success, f"发送失败: {result.error}"

    @pytest.mark.asyncio
    async def test_send_card_many_markdown_tables(self, channel):
        """发送包含多个 markdown 表格的卡片。"""
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
        result = await channel.send(TEST_CHAT_ID, {"card": card})
        assert result.success, f"发送失败: {result.error}"


class TestSendPost:
    """测试发送 post 消息。"""

    @pytest.mark.asyncio
    async def test_send_post_with_md_tag(self, channel):
        """发送 post 格式（md 标签）。"""
        post = {
            "zh_cn": {
                "content": [
                    [{"tag": "md", "text": "🤖 测试消息：**Post 格式 (md 标签)**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"}]
                ]
            }
        }
        result = await channel.send(TEST_CHAT_ID, {"post": post})
        assert result.success, f"发送失败: {result.error}"

    @pytest.mark.asyncio
    async def test_send_post_many_tables(self, channel):
        """发送包含多个表格的 post 消息（超过 5 个表格的场景）。"""
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
        result = await channel.send(TEST_CHAT_ID, {"post": post})
        assert result.success, f"发送失败: {result.error}"


class TestReplyMessage:
    """测试回复消息（自包含：先发消息再回复）。"""

    async def _send_text(self, channel, text):
        """发送文本消息，返回 message_id。"""
        result = await channel.send(TEST_CHAT_ID, {"text": text})
        assert result.success
        return result.message_id

    @pytest.mark.asyncio
    async def test_reply_text(self, channel):
        """回复文本消息。"""
        msg_id = await self._send_text(channel, "🤖 测试：回复目标")
        result = await channel.send(TEST_CHAT_ID, {"text": "🤖 测试回复：纯文本"}, {"reply_to": msg_id})
        assert result.success, f"回复失败: {result.error}"

    @pytest.mark.asyncio
    async def test_reply_card(self, channel):
        """回复卡片消息。"""
        msg_id = await self._send_text(channel, "🤖 测试：回复目标（卡片）")
        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "body": {
                "elements": [
                    {"tag": "markdown", "content": "🤖 测试回复：**卡片格式**"}
                ]
            }
        }
        result = await channel.send(TEST_CHAT_ID, {"card": card}, {"reply_to": msg_id})
        assert result.success, f"回复失败: {result.error}"

    @pytest.mark.asyncio
    async def test_reply_post(self, channel):
        """回复 post 消息。"""
        msg_id = await self._send_text(channel, "🤖 测试：回复目标（post）")
        post = {
            "zh_cn": {
                "content": [
                    [{"tag": "md", "text": "🤖 测试回复：**Post 格式**\n\n| 列1 | 列2 |\n|---|---|\n| 值1 | 值2 |"}]
                ]
            }
        }
        result = await channel.send(TEST_CHAT_ID, {"post": post}, {"reply_to": msg_id})
        assert result.success, f"回复失败: {result.error}"


class TestPatchMessage:
    """测试更新消息（先发卡片再更新）。"""

    @pytest.mark.asyncio
    async def test_send_then_patch_card(self, channel):
        """先发卡片消息，再更新它。"""
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
        result = await channel.send(TEST_CHAT_ID, {"card": card})
        assert result.success, f"发送失败: {result.error}"

        message_id = result.message_id

        # 2. 更新这张卡片
        card["body"]["elements"][0]["content"] = "🤖 测试更新：**已更新内容**"
        update_result = await channel.update_card(message_id, card)
        assert update_result.success, f"更新失败: {update_result.error}"


class TestSenderIntegration:
    """测试 sender.py 模块的集成测试（自包含）。"""

    async def _send_target_message(self, channel):
        """发送一条目标消息，返回 message_id。"""
        result = await channel.send(TEST_CHAT_ID, {"text": "🤖 sender 测试：目标消息"})
        assert result.success
        return result.message_id

    @pytest.mark.asyncio
    async def test_send_reply_text(self, channel):
        """send_reply 发送文本消息。"""
        from src.feishu.sender import send_reply
        msg_id = await self._send_target_message(channel)
        result = await send_reply(msg_id, TEST_CHAT_ID, "🤖 sender 测试：纯文本", msg_type="text")
        assert result.message_id, "send_reply 返回空 message_id，发送失败"

    @pytest.mark.asyncio
    async def test_send_reply_card(self, channel):
        """send_reply 发送卡片消息。"""
        from src.feishu.sender import send_reply
        msg_id = await self._send_target_message(channel)
        result = await send_reply(msg_id, TEST_CHAT_ID, "🤖 sender 测试：**卡片格式**", msg_type="interactive")
        assert result.message_id, "send_reply 返回空 message_id，发送失败"

    @pytest.mark.asyncio
    async def test_send_reply_many_tables_post(self, channel):
        """send_reply 超过 5 个表格用 post 格式。"""
        from src.feishu.sender import send_reply
        msg_id = await self._send_target_message(channel)
        table = "| a | b |\n|---|---|\n| 1 | 2 |"
        content = "🤖 sender 测试：**多表格 post**\n\n" + "\n\n".join([table] * 10)
        result = await send_reply(msg_id, TEST_CHAT_ID, content, msg_type="interactive")
        assert result.message_id, "send_reply 返回空 message_id，发送失败"
