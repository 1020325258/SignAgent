# -*- coding: utf-8 -*-
"""sender.py 飞书消息发送模块测试。"""

import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu.sender import (
    _count_markdown_tables,
    send_reply,
    update_message,
    update_rich_card,
    PreviewHandle,
    create_card_entity,
    stream_card_text,
    MAX_CARD_TABLES,
)
from src.feishu.card_builder import build_card_content, build_post_md_json, build_rich_card_content


# ── 辅助函数 ──

def _mock_success_response(message_id="msg_123"):
    resp = MagicMock()
    resp.success.return_value = True
    resp.data = MagicMock()
    resp.data.message_id = message_id
    return resp


def _mock_error_response(code=99991401, msg="error"):
    resp = MagicMock()
    resp.success.return_value = False
    resp.code = code
    resp.msg = msg
    return resp


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
        # 应该有：思考面板 + 工具面板 + markdown
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
        # 非 streaming 模式，空面板不显示
        assert elements[0]["tag"] == "markdown"

    def test_thinking_panel_shown_when_streaming(self):
        result = build_rich_card_content([], [], "hello", is_streaming=True)
        parsed = json.loads(result)
        elements = parsed["body"]["elements"]
        # streaming 模式下，思考面板始终显示
        assert elements[0]["tag"] == "collapsible_panel"

    def test_streaming_config(self):
        result = build_rich_card_content([], [], "hello", is_streaming=True)
        parsed = json.loads(result)
        assert parsed["config"]["streaming_mode"] is True


# ── send_reply ──

class TestSendReply:

    @pytest.mark.asyncio
    async def test_returns_preview_handle(self):
        with patch("src.feishu.sender._create_client"), \
             patch("src.feishu.sender.with_retry") as mock_retry, \
             patch("src.feishu.sender.create_card_entity") as mock_entity:
            mock_retry.return_value = _mock_success_response()
            mock_entity.return_value = ""
            handle = await send_reply("msg_001", "hello", msg_type="interactive")
            assert isinstance(handle, PreviewHandle)

    @pytest.mark.asyncio
    async def test_card_json_mode(self):
        with patch("src.feishu.sender._create_client"), \
             patch("src.feishu.sender.with_retry") as mock_retry, \
             patch("src.feishu.sender.create_card_entity") as mock_entity:
            mock_retry.return_value = _mock_success_response()
            mock_entity.return_value = "card_123"
            card = build_rich_card_content([], [], "hello")
            handle = await send_reply("msg_001", card, msg_type="interactive", is_card_json=True)
            assert handle.card_id == "card_123"


# ── update_rich_card ──

class TestUpdateRichCard:

    @pytest.mark.asyncio
    async def test_uses_cardkit_when_available(self):
        handle = PreviewHandle(message_id="msg_001", card_id="card_123")
        with patch("src.feishu.sender._create_client"), \
             patch("src.feishu.sender.stream_card_text") as mock_stream:
            mock_stream.return_value = True
            await update_rich_card(handle, [], [], "hello")
            mock_stream.assert_called_once()
            assert handle.sequence == 1

    @pytest.mark.asyncio
    async def test_fallback_to_patch(self):
        handle = PreviewHandle(message_id="msg_001", card_id="")
        with patch("src.feishu.sender._create_client"), \
             patch("src.feishu.sender.with_retry") as mock_retry, \
             patch("src.feishu.sender.stream_card_text") as mock_stream:
            mock_retry.return_value = _mock_success_response()
            await update_rich_card(handle, [], [], "hello")
            mock_stream.assert_not_called()
            mock_retry.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
