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
    _build_content,
    send_reply,
    update_message,
    PreviewHandle,
    create_card_entity,
    stream_card_text,
    MAX_CARD_TABLES,
)
from src.feishu.card_builder import build_card_content, build_post_md_json


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


def _make_many_tables(n=10):
    table = "| a | b |\n|---|---|\n| 1 | 2 |"
    return "\n\n".join([table] * n)


# ── 表格计数 ──

class TestCountMarkdownTables:

    def test_no_tables(self):
        assert _count_markdown_tables("hello world") == 0

    def test_single_table(self):
        assert _count_markdown_tables("| a | b |\n|---|---|\n| 1 | 2 |") == 1

    def test_two_tables(self):
        content = "| a | b |\n|---|---|\n| 1 | 2 |\n\nsome text\n\n| c | d |\n|---|---|\n| 3 | 4 |"
        assert _count_markdown_tables(content) == 2

    def test_six_tables(self):
        assert _count_markdown_tables(_make_many_tables(6)) == 6


# ── 卡片构建 ──

class TestBuildCardContent:

    def test_schema_2_0(self):
        result = build_card_content("hello")
        parsed = json.loads(result)
        assert parsed["schema"] == "2.0"

    def test_element_id_main_text(self):
        """markdown 元素有 element_id。"""
        result = build_card_content("hello")
        parsed = json.loads(result)
        elem = parsed["body"]["elements"][0]
        assert elem["element_id"] == "main_text"

    def test_streaming_config(self):
        """config 包含 streaming_mode。"""
        result = build_card_content("hello")
        parsed = json.loads(result)
        assert parsed["config"]["streaming_mode"] is True
        assert parsed["config"]["update_multi"] is True

    def test_single_markdown_element(self):
        result = build_card_content("**bold** text")
        parsed = json.loads(result)
        elements = parsed["body"]["elements"]
        assert len(elements) == 1
        assert elements[0]["tag"] == "markdown"

    def test_thinking_prefix(self):
        result = build_card_content("hello", is_thinking=True)
        parsed = json.loads(result)
        content = parsed["body"]["elements"][0]["content"]
        assert "思考中" in content


# ── Post 格式构建 ──

class TestBuildPostMdJson:

    def test_structure(self):
        result = build_post_md_json("hello **world**")
        parsed = json.loads(result)
        assert parsed["zh_cn"]["content"][0][0]["tag"] == "md"


# ── 格式选择 ──

class TestBuildContent:

    def test_text_type(self):
        msg_type, body = _build_content("hello", "text")
        assert msg_type == "text"

    def test_interactive_small_tables(self):
        content = "| a | b |\n|---|---|\n| 1 | 2 |"
        msg_type, body = _build_content(content, "interactive")
        assert msg_type == "interactive"

    def test_interactive_many_tables_falls_to_post(self):
        content = _make_many_tables(10)
        msg_type, body = _build_content(content, "interactive")
        assert msg_type == "post"


# ── send_reply ──

class TestSendReply:

    @pytest.mark.asyncio
    async def test_text_type(self):
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.with_retry") as mock_retry:
            mock_retry.return_value = _mock_success_response()
            handle = await send_reply("msg_001", "hello", msg_type="text")
            assert handle.message_id == "msg_123"

    @pytest.mark.asyncio
    async def test_returns_preview_handle(self):
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.with_retry") as mock_retry, \
             patch("src.feishu.sender.create_card_entity") as mock_create_entity:
            mock_retry.return_value = _mock_success_response()
            mock_create_entity.return_value = ""  # cardkit-v1 失败，降级
            handle = await send_reply("msg_001", "hello **bold**", msg_type="interactive")
            assert isinstance(handle, PreviewHandle)
            assert handle.message_id == "msg_123"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.with_retry") as mock_retry:
            mock_retry.side_effect = Exception("error")
            handle = await send_reply("msg_001", "hello")
            assert handle.message_id == ""


# ── update_message ──

class TestUpdateMessage:

    @pytest.mark.asyncio
    async def test_uses_cardkit_when_available(self):
        """有 card_id 时用 cardkit-v1 流式更新。"""
        handle = PreviewHandle(message_id="msg_001", card_id="card_123")
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.stream_card_text") as mock_stream:
            mock_stream.return_value = True
            await update_message(handle, "hello", is_thinking=False)
            mock_stream.assert_called_once()
            assert handle.sequence == 1

    @pytest.mark.asyncio
    async def test_fallback_to_patch_when_no_card_id(self):
        """没有 card_id 时降级为 Patch。"""
        handle = PreviewHandle(message_id="msg_001", card_id="")
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.with_retry") as mock_retry, \
             patch("src.feishu.sender.stream_card_text") as mock_stream:
            mock_retry.return_value = _mock_success_response()
            await update_message(handle, "hello", is_thinking=False)
            mock_stream.assert_not_called()
            mock_retry.assert_called()

    @pytest.mark.asyncio
    async def test_fallback_to_patch_when_stream_fails(self):
        """cardkit-v1 失败时降级为 Patch。"""
        handle = PreviewHandle(message_id="msg_001", card_id="card_123")
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.stream_card_text") as mock_stream, \
             patch("src.feishu.sender.with_retry") as mock_retry:
            mock_stream.return_value = False
            mock_retry.return_value = _mock_success_response()
            await update_message(handle, "hello", is_thinking=False)
            assert handle.sequence == 1
            mock_retry.assert_called()  # Patch 被调用

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        handle = PreviewHandle(message_id="msg_001")
        with patch("src.feishu.sender._create_client") as mock_create, \
             patch("src.feishu.sender.with_retry") as mock_retry:
            mock_retry.side_effect = Exception("error")
            await update_message(handle, "hello")  # 不抛出


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
