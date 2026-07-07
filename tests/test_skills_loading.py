# -*- coding: utf-8 -*-
"""
测试 skills 是否正常加载。
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# 模拟 claude_agent_sdk
mock_sdk = MagicMock()


class TestSkillsLoading:
    """Skills 加载测试类"""

    @pytest.fixture
    def agent(self):
        """创建测试用的 Agent 实例"""
        from src.agent import SignAgent

        # 使用实际的项目目录
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return SignAgent(
            project_dir=project_dir,
            api_config={
                "ANTHROPIC_BASE_URL": "https://test.api.com",
                "ANTHROPIC_AUTH_TOKEN": "test-token",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
        )

    def test_skills_configured_as_all(self, agent):
        """测试 skills 配置为 'all'"""
        options = agent._create_options()
        assert options.skills == "all", f"skills 应为 'all'，实际为: {options.skills}"

    def test_add_dirs_is_empty(self, agent):
        """测试 add_dirs 为空（skills 从 .claude/skills/ 自动发现）"""
        options = agent._create_options()
        assert len(options.add_dirs) == 0, f"add_dirs 应为空，实际为: {options.add_dirs}"

    def test_claude_skills_directory_exists(self, agent):
        """测试 .claude/skills 目录存在"""
        project_dir = agent.project_dir
        claude_skills_dir = os.path.join(project_dir, ".claude", "skills")
        assert os.path.exists(claude_skills_dir), f".claude/skills 目录不存在: {claude_skills_dir}"

    def test_all_skill_files_exist(self, agent):
        """测试所有 skill 文件存在"""
        project_dir = agent.project_dir
        claude_skills_dir = os.path.join(project_dir, ".claude", "skills")

        expected_skills = [
            "company-seal-troubleshoot",
            "contract-data-dictionary",
            "contract-field-config-query",
            "contract-personal-data-empty",
            "contract-start-date-unselectable",
            "rag-citation",
            "sre-add-api",
        ]

        for skill_name in expected_skills:
            skill_dir = os.path.join(claude_skills_dir, skill_name)
            skill_file = os.path.join(skill_dir, "SKILL.md")
            assert os.path.exists(skill_dir), f"skill 目录不存在: {skill_dir}"
            assert os.path.exists(skill_file), f"skill 文件不存在: {skill_file}"

    def test_skill_files_have_correct_frontmatter(self, agent):
        """测试 skill 文件有正确的 frontmatter"""
        project_dir = agent.project_dir
        claude_skills_dir = os.path.join(project_dir, ".claude", "skills")

        expected_skills = [
            "company-seal-troubleshoot",
            "contract-data-dictionary",
            "contract-field-config-query",
            "contract-personal-data-empty",
            "contract-start-date-unselectable",
            "rag-citation",
            "sre-add-api",
        ]

        for skill_name in expected_skills:
            skill_file = os.path.join(claude_skills_dir, skill_name, "SKILL.md")
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查 frontmatter
            assert content.startswith("---"), f"{skill_name}: 缺少 frontmatter"
            assert "name:" in content, f"{skill_name}: frontmatter 缺少 name 字段"
            assert "description:" in content, f"{skill_name}: frontmatter 缺少 description 字段"

    def test_sdk_options_structure(self, agent):
        """测试 SDK options 结构完整"""
        options = agent._create_options()

        # 验证必要字段存在
        assert hasattr(options, "skills"), "options 缺少 skills 字段"
        assert hasattr(options, "add_dirs"), "options 缺少 add_dirs 字段"
        assert hasattr(options, "mcp_servers"), "options 缺少 mcp_servers 字段"
        assert hasattr(options, "allowed_tools"), "options 缺少 allowed_tools 字段"
        assert hasattr(options, "permission_mode"), "options 缺少 permission_mode 字段"

    def test_mcp_servers_configured(self, agent):
        """测试 MCP servers 配置正确"""
        options = agent._create_options()
        assert len(options.mcp_servers) > 0, "mcp_servers 不应为空"

        # 验证包含必要的 MCP server
        assert "knowledge" in options.mcp_servers, "缺少 knowledge MCP server"
        assert "sre" in options.mcp_servers, "缺少 sre MCP server"
        assert "apollo" in options.mcp_servers, "缺少 apollo MCP server"

    def test_allowed_tools_configured(self, agent):
        """测试 allowed_tools 配置正确"""
        options = agent._create_options()
        assert len(options.allowed_tools) > 0, "allowed_tools 不应为空"

        # 验证包含必要的工具
        assert "mcp__knowledge__knowledge_search" in options.allowed_tools
        assert "mcp__sre__sre_query" in options.allowed_tools
        assert "mcp__apollo__apollo_query" in options.allowed_tools
        assert "mcp__fast_log__fast_log_query" in options.allowed_tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
