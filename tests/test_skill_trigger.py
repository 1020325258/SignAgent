# -*- coding: utf-8 -*-
"""
测试 Skill 工具是否被正确触发。
"""

import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# 设置环境变量
os.environ["ANTHROPIC_BASE_URL"] = "https://api.anthropic.com"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "test-token"
os.environ["ANTHROPIC_MODEL"] = "claude-sonnet-4-6"


class TestSkillTrigger:
    """Skill 触发测试类"""

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

    def test_skill_tool_not_in_allowed_tools(self, agent):
        """测试 Skill 工具不在 allowed_tools 中（SDK 自动处理）"""
        options = agent._create_options()
        # Skill 工具应由 SDK 通过 skills="all" 自动注入，不需要手动添加
        assert "Skill" not in options.allowed_tools, "Skill 工具应由 SDK 自动注入，不需要手动添加"

    def test_skills_configured(self, agent):
        """测试 skills 配置正确"""
        options = agent._create_options()
        assert options.skills == "all", "skills 应配置为 'all'"

    def test_system_prompt_uses_preset(self, agent):
        """测试系统提示词使用 preset 模式"""
        options = agent._create_options()
        assert isinstance(options.system_prompt, dict), "system_prompt 应为 dict 类型"
        assert options.system_prompt.get("type") == "preset", "应使用 preset 类型"
        assert options.system_prompt.get("preset") == "claude_code", "应使用 claude_code preset"
        assert "append" in options.system_prompt, "应包含 append 字段"

    def test_system_prompt_append_content(self, agent):
        """测试系统提示词 append 内容正确"""
        from src.agent.config import get_default_system_prompt

        prompt = get_default_system_prompt()
        assert "签约系统助手" in prompt, "应包含角色定义"
        assert "mcp__knowledge__knowledge_search" in prompt, "应包含 MCP 工具说明"

    def test_company_seal_troubleshoot_skill_exists(self, agent):
        """测试盖章排查 skill 文件存在"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )
        assert os.path.exists(skill_file), f"盖章排查 skill 文件应存在: {skill_file}"

    def test_company_seal_troubleshoot_skill_content(self, agent):
        """测试盖章排查 skill 文件内容正确"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查 frontmatter
        assert content.startswith("---"), "skill 文件应以 frontmatter 开头"
        assert "name: company-seal-troubleshoot" in content, "应包含正确的 name"
        assert "description:" in content, "应包含 description"

        # 检查触发关键词
        assert "盖章失败" in content, "应包含触发词 '盖章失败'"
        assert "盖公司章" in content, "应包含触发词 '盖公司章'"

        # 检查排查流程
        assert "platform_instance_id" in content, "应包含 platform_instance_id 查询"
        assert "fast_log_query" in content, "应提到 fast_log_query 工具"

    @pytest.mark.asyncio
    async def test_chat_method_exists(self, agent):
        """测试 chat 方法存在"""
        assert hasattr(agent, 'chat'), "Agent 应有 chat 方法"
        assert callable(agent.chat), "chat 方法应可调用"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
