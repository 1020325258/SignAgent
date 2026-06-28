# -*- coding: utf-8 -*-
"""MCP 服务器工厂模块。"""

from claude_agent_sdk import create_sdk_mcp_server

from ..tools import knowledge_search, sre_query, apollo_query


def create_mcp_servers() -> dict:
    """创建 MCP 服务器配置。

    Returns:
        MCP 服务器字典
    """
    # 创建知识库查询服务器
    knowledge_server = create_sdk_mcp_server(
        name="knowledge",
        version="1.0.0",
        tools=[knowledge_search],
    )

    # 创建 SRE 查询服务器
    sre_server = create_sdk_mcp_server(
        name="sre",
        version="1.0.0",
        tools=[sre_query],
    )

    # 创建 Apollo 配置查询服务器
    apollo_server = create_sdk_mcp_server(
        name="apollo",
        version="1.0.0",
        tools=[apollo_query],
    )

    return {
        "knowledge": knowledge_server,
        "sre": sre_server,
        "apollo": apollo_server,
    }
