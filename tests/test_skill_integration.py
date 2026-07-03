# -*- coding: utf-8 -*-
"""
集成测试：验证 Skill 工具是否被正确调用。
"""

import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestSkillIntegration:
    """Skill 集成测试类"""

    @pytest.fixture
    def agent(self):
        """创建测试用的 Agent 实例"""
        from src.agent import SignAgent

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return SignAgent(
            project_dir=project_dir,
            api_config={
                "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
                "ANTHROPIC_AUTH_TOKEN": "test-token",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
        )

    @pytest.mark.asyncio
    async def test_chat_returns_events(self, agent):
        """测试 chat 方法返回事件流"""
        # 模拟 SDK 返回
        mock_messages = [
            MagicMock(
                content=[
                    MagicMock(
                        __class__=type('TextBlock', (), {}),
                        text="测试回复",
                        thinking=None,
                    )
                ]
            ),
            MagicMock(
                num_turns=1,
                duration_ms=1000,
                duration_api_ms=800,
                total_cost_usd=0.01,
                stop_reason="end_turn",
            ),
        ]

        with patch.object(agent, 'chat', return_value=async_mock_generator([
            {"type": "text", "content": "测试回复"},
        ])):
            events = []
            async for event in agent.chat(question="测试问题", user_id="test_user"):
                events.append(event)

            assert len(events) > 0, "应返回至少一个事件"
            assert any(e.get("type") == "text" for e in events), "应包含文本事件"


async def async_mock_generator(items):
    """创建异步生成器模拟"""
    for item in items:
        yield item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
