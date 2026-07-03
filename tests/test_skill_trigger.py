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

    def test_skill_trigger_words_in_skill_files(self, agent):
        """测试触发词在 SKILL.md 文件中（而非系统提示词）"""
        import os
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "personal-contract-data-empty", "SKILL.md"
        )
        assert os.path.exists(skill_file), "SKILL.md 文件应存在"

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 触发词应该在 SKILL.md 中
        assert "个性化报价为空" in content, "SKILL.md 应包含触发词 '个性化报价为空'"
        assert "销售合同个性化" in content, "SKILL.md 应包含触发词 '销售合同个性化'"

    @pytest.mark.asyncio
    async def test_chat_method_exists(self, agent):
        """测试 chat 方法存在"""
        assert hasattr(agent, 'chat'), "Agent 应有 chat 方法"
        assert callable(agent.chat), "chat 方法应可调用"

    def test_skill_files_content(self, agent):
        """测试 skill 文件内容正确"""
        project_dir = agent.project_dir
        skill_file = os.path.join(
            project_dir, ".claude", "skills", "personal-contract-data-empty", "SKILL.md"
        )

        assert os.path.exists(skill_file), f"skill 文件不存在: {skill_file}"

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查 frontmatter
        assert content.startswith("---"), "skill 文件应以 frontmatter 开头"
        assert "name: personal-contract-data-empty" in content, "应包含正确的 name"
        assert "description:" in content, "应包含 description"

        # 检查触发条件
        assert "触发条件" in content, "应包含触发条件章节"
        assert "个性化报价" in content, "应提到个性化报价"

        # 检查排查流程
        assert "排查流程" in content, "应包含排查流程章节"
        assert "fast_log_query" in content, "应提到 fast_log_query 工具"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
