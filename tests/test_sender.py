# -*- coding: utf-8 -*-
"""sender.py 飞书消息发送模块测试（基于 lark-channel-sdk）。"""

import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu.sender import (
    _count_markdown_tables,
    send_reply,
    update_rich_card,
    PreviewHandle,
    MAX_CARD_TABLES,
)
from src.feishu.card_builder import build_card_content, build_post_md_json, build_rich_card_content


# ── 辅助函数 ──

def _mock_send_result(message_id="msg_123", success=True):
    """模拟 channel.send() 的返回值。"""
    result = MagicMock()
    result.success = success
    result.message_id = message_id
    return result


def _mock_channel():
    """创建一个 mock channel 实例。"""
    ch = MagicMock()
    ch.send = AsyncMock(return_value=_mock_send_result())
    ch.send_card_by_reference = AsyncMock(return_value=_mock_send_result())
    ch.create_card_instance = AsyncMock(return_value="")
    ch.update_card_element_content = AsyncMock()
    ch.finish_streaming_card = AsyncMock()
    ch.update_card = AsyncMock(return_value=_mock_send_result())
    return ch


# ── 表格计数 ──

class TestCountMarkdownTables:

    def test_no_tables(self):
        assert _count_markdown_tables("hello world") == 0

    def test_single_table(self):
        assert _count_markdown_tables("| a | b |\n|---|---|\n| 1 | 2 |") == 1


# ── 富卡片构建 ──

class TestBuildRichCardContent:

    def test_schema_2_0(self):
        result = build_rich_card_content([], [], "hello")
        parsed = json.loads(result)
        assert parsed["schema"] == "2.0"

    def test_has_panels(self):
        thinking = [{"text": "思考中...", "icon": "chat-forbidden", "color": "grey"}]
        tools = [{"text": "sre_query()", "icon": "chat-forbidden", "color": "grey"}]
        result = build_rich_card_content(thinking, tools, "hello")
        parsed = json.loads(result)
        elements = parsed["body"]["elements"]
        assert len(elements) == 3
        assert elements[0]["tag"] == "collapsible_panel"
        assert elements[1]["tag"] == "collapsible_panel"
        assert elements[2]["tag"] == "markdown"

    def test_main_text_element_id(self):
        result = build_rich_card_content([], [], "hello")
        parsed = json.loads(result)
        md = [e for e in parsed["body"]["elements"] if e["tag"] == "markdown"][0]
        assert md["element_id"] == "main_text"

    def test_no_panels_when_not_streaming(self):
        result = build_rich_card_content([], [], "hello", is_streaming=False)
        parsed = json.loads(result)
        elements = parsed["body"]["elements"]
        assert elements[0]["tag"] == "markdown"

    def test_thinking_panel_shown_when_streaming(self):
        result = build_rich_card_content([], [], "hello", is_streaming=True)
        parsed = json.loads(result)
        elements = parsed["body"]["elements"]
        assert elements[0]["tag"] == "collapsible_panel"

    def test_streaming_config(self):
        result = build_rich_card_content([], [], "hello", is_streaming=True)
        parsed = json.loads(result)
        assert parsed["config"]["streaming_mode"] is True


# ── send_reply ──

class TestSendReply:

    @pytest.mark.asyncio
    async def test_returns_preview_handle(self):
        with patch("src.feishu.sender.get_channel", return_value=_mock_channel()):
            handle = await send_reply("msg_001", "chat_001", "hello", msg_type="interactive")
            assert isinstance(handle, PreviewHandle)

    @pytest.mark.asyncio
    async def test_card_json_mode(self):
        mock_ch = _mock_channel()
        mock_ch.create_card_instance = AsyncMock(return_value="card_123")
        mock_ch.send_card_by_reference = AsyncMock(return_value=_mock_send_result())
        with patch("src.feishu.sender.get_channel", return_value=mock_ch):
            card = build_rich_card_content([], [], "hello")
            handle = await send_reply("msg_001", "chat_001", card, msg_type="interactive", is_card_json=True)
            assert handle.card_id == "card_123"

    @pytest.mark.asyncio
    async def test_text_message(self):
        mock_ch = _mock_channel()
        mock_ch.send = AsyncMock(return_value=_mock_send_result("msg_456"))
        with patch("src.feishu.sender.get_channel", return_value=mock_ch):
            handle = await send_reply("msg_001", "chat_001", "hello", msg_type="text")
            assert handle.message_id == "msg_456"
            mock_ch.send.assert_called_once()


# ── update_rich_card ──

class TestUpdateRichCard:

    @pytest.mark.asyncio
    async def test_uses_cardkit_when_streaming(self):
        handle = PreviewHandle(message_id="msg_001", card_id="card_123")
        mock_ch = _mock_channel()
        with patch("src.feishu.sender.get_channel", return_value=mock_ch):
            await update_rich_card(handle, [], [], "hello", is_streaming=True)
            mock_ch.update_card_element_content.assert_called_once()
            assert handle.sequence == 1

    @pytest.mark.asyncio
    async def test_uses_patch_when_final_update(self):
        handle = PreviewHandle(message_id="msg_001", card_id="card_123")
        mock_ch = _mock_channel()
        with patch("src.feishu.sender.get_channel", return_value=mock_ch):
            await update_rich_card(handle, [], [], "hello", is_streaming=False, force=True, status="done")
            # 最终更新走 patch 路径，不走 stream
            mock_ch.update_card_element_content.assert_not_called()
            mock_ch.update_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_patch_no_card_id(self):
        handle = PreviewHandle(message_id="msg_001", card_id="")
        mock_ch = _mock_channel()
        with patch("src.feishu.sender.get_channel", return_value=mock_ch):
            await update_rich_card(handle, [], [], "hello")
            mock_ch.update_card_element_content.assert_not_called()
            mock_ch.update_card.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
