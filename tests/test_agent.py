# -*- coding: utf-8 -*-
"""签约助手 Agent 测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestSignAgent:
    """SignAgent 测试类。"""

    @pytest.fixture
    def agent(self):
        """创建测试用的 Agent 实例。"""
        from src.agent import SignAgent

        return SignAgent(
            project_dir="/tmp/test_project",
            api_config={
                "ANTHROPIC_BASE_URL": "https://test.api.com",
                "ANTHROPIC_AUTH_TOKEN": "test-token",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-8",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
            },
        )

    def test_agent_initialization(self, agent):
        """测试 Agent 初始化。"""
        assert agent.project_dir == "/tmp/test_project"
        assert agent.api_config["ANTHROPIC_MODEL"] == "claude-sonnet-4-6"
        assert "签约系统助手" in agent.system_prompt

    def test_agent_has_chat_method(self, agent):
        """测试 Agent 有 chat 方法。"""
        assert hasattr(agent, "chat")
        assert callable(agent.chat)

    def test_agent_has_clear_memory(self, agent):
        """测试 Agent 有 clear_memory 方法。"""
        assert hasattr(agent, "clear_memory")
        assert callable(agent.clear_memory)
