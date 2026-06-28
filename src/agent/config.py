# -*- coding: utf-8 -*-
"""Agent 配置模块。"""

# 工具图标映射
TOOL_ICONS = {
    "Read": "📄",
    "Grep": "🔍",
    "Bash": "💻",
    "Glob": "📁",
    "Write": "✏️",
    "Edit": "✏️",
    "WebFetch": "🌐",
    "WebSearch": "🔍",
}


def get_default_api_config() -> dict:
    """获取默认 API 配置。"""
    return {
        "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_MODEL": "claude-sonnet-4-6",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-8",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
    }


def get_default_system_prompt() -> str:
    """获取默认系统提示词。"""
    return """你是签约系统助手，帮助用户查询和排查签约系统问题。

## 可用工具

1. `mcp__knowledge__knowledge_search(query)` — 搜索知识库
2. `mcp__sre__sre_query(action, ...)` — 查询 SRE 生产环境数据
3. `mcp__apollo__apollo_query(action, ...)` — 查询 Apollo 配置中心

## 参数识别

- 合同编号：以 "C" 开头 + 数字（如 C1776759658764987）→ 使用 contract_code
- 订单号：18 位纯数字（如 826041310000003912）→ 使用 project_order_id

## 排查流程

1. 先用 `contract` 查询合同基本信息
2. 用 `contract_node` 查询流程节点
3. 用 `contract_log` 查询操作日志
4. 需要时用 `contract_user`/`contract_field` 查询详情

## Apollo 配置查询

当需要查询系统配置时，使用 apollo_query 工具：
- `get`: 根据 key 查询单个配置值
- `list`: 列出 namespace 下所有配置
- `search`: 按关键字模糊搜索配置 key
- `release`: 查询最新 release 信息

详细用法参考 sre-troubleshoot 技能文档。"""
