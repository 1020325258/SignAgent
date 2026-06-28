# -*- coding: utf-8 -*-
"""签约助手 Agent 核心模块。"""

import os
from typing import Optional, AsyncGenerator
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ResultMessage,
)

from .config import get_default_api_config, get_default_system_prompt
from .formatters import format_tool_use, format_tool_result, format_thinking
from .mcp_factory import create_mcp_servers


class SignAgent:
    """签约系统智能助手"""

    def __init__(
        self,
        project_dir: str,
        api_config: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        debug: bool = False,
    ):
        """
        初始化签约助手

        Args:
            project_dir: 签约系统项目目录
            api_config: API 配置，如果为 None 则使用默认配置
            system_prompt: 自定义系统提示词
            debug: 是否开启 debug 模式（输出工具调用详情）
        """
        self.project_dir = project_dir
        self.api_config = api_config or get_default_api_config()
        self.system_prompt = system_prompt or get_default_system_prompt()
        self.debug = debug

    async def chat(
        self,
        question: str,
        allowed_tools: Optional[list[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        与签约助手进行对话

        Args:
            question: 用户问题
            allowed_tools: 允许使用的工具列表

        Yields:
            助手的回复内容
        """
        if allowed_tools is None:
            allowed_tools = []

        # MCP 工具列表
        mcp_tools = [
            "mcp__knowledge__knowledge_search",
            "mcp__sre__sre_query",
            "mcp__apollo__apollo_query",
        ]
        all_tools = allowed_tools + mcp_tools

        # 创建 MCP 服务器
        mcp_servers = create_mcp_servers()

        # skills 目录
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")

        options = ClaudeAgentOptions(
            allowed_tools=all_tools,
            mcp_servers=mcp_servers,
            skills="all",
            add_dirs=[skills_dir],
            permission_mode="acceptEdits",
            cwd=self.project_dir,
            system_prompt=self.system_prompt,
            env=self.api_config,
            max_turns=30,
        )

        async for message in query(prompt=question, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        if block.text:
                            yield block.text

                    elif isinstance(block, ThinkingBlock):
                        if self.debug and block.thinking:
                            yield format_thinking(block.thinking)

                    elif isinstance(block, ToolUseBlock):
                        if self.debug:
                            yield format_tool_use(block.name, block.input)

            elif isinstance(message, UserMessage):
                if self.debug and message.tool_use_result:
                    result = message.tool_use_result
                    if isinstance(result, dict):
                        content = result.get("content", "")
                        is_error = result.get("is_error", False)
                    elif isinstance(result, str):
                        content = result
                        is_error = False
                    else:
                        content = str(result)
                        is_error = False
                    if content:
                        yield format_tool_result(content, is_error)

            elif isinstance(message, ResultMessage):
                pass

    async def chat_and_print(self, question: str):
        """对话并直接打印结果"""
        async for text in self.chat(question):
            print(text, end="", flush=True)
        print()
