# -*- coding: utf-8 -*-
"""
集成测试：验证盖章排查 Skill 能够被正确触发。

测试场景：用户询问 "C1783330573013484合同盖章失败原因" 时，
应该触发 company-seal-troubleshoot skill进行排查。
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# 设置环境变量
os.environ["ANTHROPIC_BASE_URL"] = "https://api.anthropic.com"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "test-token"
os.environ["ANTHROPIC_MODEL"] = "claude-sonnet-4-6"


class TestSealTroubleshootIntegration:
    """盖章排查集成测试类"""

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

    def test_skill_description_contains_trigger_words(self, agent):
        """测试 skill description 包含触发关键词"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取 description
        import re
        desc_match = re.search(r'description:\s*(.+?)(?:\n|$)', content)
        assert desc_match, "应包含 description 字段"
        description = desc_match.group(1)

        # 验证触发词
        trigger_words = ["盖公司章", "盖章失败", "盖章异常", "公司章报错"]
        for word in trigger_words:
            assert word in description, f"description 应包含触发词 '{word}'"

    def test_skill_troubleshooting_flow(self, agent):
        """测试 skill 排查流程完整性"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证排查流程步骤
        assert "第一步：提取合同号" in content, "应包含第一步：提取合同号"
        assert "第二步：查询合同的 platform_instance_id" in content, "应包含第二步"
        assert "第三步：查询 FAST 日志" in content, "应包含第三步"
        assert "第四步：分析日志结果" in content, "应包含第四步"

        # 验证工具调用
        assert "sre_query" in content, "应使用 sre_query 工具"
        assert "fast_log_query" in content, "应使用 fast_log_query 工具"

    def test_skill_contract_code_format(self, agent):
        """测试 skill 中合同编号格式说明"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证合同编号格式说明
        assert '以字母 "C" 开头' in content, "应说明合同编号格式"
        assert "C1776759658764987" in content, "应包含合同编号示例"

    def test_skill_lucene_query_format(self, agent):
        """测试 skill 中 Lucene 查询格式"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证 Lucene 查询格式
        assert "盖公司章PDF入参" in content, "应包含日志查询关键词"
        assert "盖公司章PDF出参" in content, "应包含日志查询关键词"
        assert "Lucene" in content, "应说明使用 Lucene 语法"

    def test_skill_error_codes(self, agent):
        """测试 skill 中错误码说明"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证错误码说明
        assert "3001" in content, "应包含错误码 3001"
        assert "未获取到有效的自动签授权信息" in content, "应包含错误码 3001 的说明"

    def test_skill_output_format(self, agent):
        """测试 skill 输出格式模板"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证输出格式
        assert "盖公司章异常排查结果" in content, "应包含输出格式标题"
        assert "合同信息" in content, "应包含合同信息章节"
        assert "盖章日志" in content, "应包含盖章日志章节"
        assert "问题分析" in content, "应包含问题分析章节"
        assert "原始错误信息" in content, "应包含原始错误信息章节"
        assert "错误原因总结" in content, "应包含错误原因总结章节"
        assert "建议处理方式" not in content, "不应再包含建议处理方式章节"

    def test_skill_requires_contract_code(self, agent):
        """测试 skill 要求提供合同编号"""
        skill_file = os.path.join(
            agent.project_dir, ".claude", "skills",
            "company-seal-troubleshoot", "SKILL.md"
        )

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证必须提供合同号
        assert "必须提供合同号" in content, "应强调必须提供合同号"
        assert "必须反问用户" in content, "应说明未提供时反问用户"

    @pytest.mark.asyncio
    async def test_chat_with_seal_question_should_trigger_skill(self, agent):
        """测试盖章问题应触发 skill（通过 SDK 配置验证）"""
        # 验证 SDK 配置正确
        options = agent._create_options()

        # skills 应配置为 "all"，这会自动加载所有 skills
        assert options.skills == "all", "skills 应配置为 'all'"

        # Skill 工具不应在 allowed_tools 中（由 SDK 自动注入）
        assert "Skill" not in options.allowed_tools, "Skill 不应在 allowed_tools中"

        # MCP 工具应正确配置
        assert "mcp__sre__sre_query" in options.allowed_tools, "应包含 sre_query 工具"
        assert "mcp__fast_log__fast_log_query" in options.allowed_tools, "应包含 fast_log_query 工具"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
