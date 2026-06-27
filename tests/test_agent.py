"""
签约助手 Agent 测试
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# 模拟 claude_agent_sdk
mock_sdk = MagicMock()


class TestSignAgent:
    """SignAgent 测试类"""

    @pytest.fixture
    def agent(self):
        """创建测试用的 Agent 实例"""
        from src.agent import SignAgent

        return SignAgent(
            project_dir="/tmp/test_project",
            api_config={
                "ANTHROPIC_BASE_URL": "https://test.api.com",
                "ANTHROPIC_AUTH_TOKEN": "test-token",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
        )

    def test_agent_initialization(self, agent):
        """测试 Agent 初始化"""
        assert agent.project_dir == "/tmp/test_project"
        assert agent.api_config["ANTHROPIC_MODEL"] == "claude-sonnet-4-6"
        assert "签约系统助手" in agent.system_prompt

    def test_default_system_prompt(self, agent):
        """测试默认系统提示词"""
        prompt = agent._default_system_prompt()
        assert "签约系统助手" in prompt
        assert "只读操作" in prompt

    @pytest.mark.asyncio
    async def test_chat_method(self, agent):
        """测试 chat 方法"""
        # 模拟 SDK 返回
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="测试回复")]

        with patch("src.agent.query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [mock_message]

            result = []
            async for text in agent.chat("测试问题"):
                result.append(text)

            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_analyze_contract(self, agent):
        """测试合同分析方法"""
        with patch.object(agent, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = iter(["分析结果"])

            result = await agent.analyze_contract("采购合同")
            assert result == "分析结果"

    @pytest.mark.asyncio
    async def test_explain_sign_flow(self, agent):
        """测试流程解释方法"""
        with patch.object(agent, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = iter(["流程说明"])

            result = await agent.explain_sign_flow("合同签署")
            assert result == "流程说明"

    @pytest.mark.asyncio
    async def test_troubleshoot(self, agent):
        """测试问题排查方法"""
        with patch.object(agent, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = iter(["排查结果"])

            result = await agent.troubleshoot("签署失败")
            assert result == "排查结果"
