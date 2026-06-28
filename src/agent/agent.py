# -*- coding: utf-8 -*-
"""签约助手 Agent 核心模块。"""

import os
import logging
from typing import Optional, AsyncGenerator
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
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
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class SignAgent:
    """签约系统智能助手"""

    def __init__(
        self,
        project_dir: str,
        api_config: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        debug: bool = False,
        session_dir: str = "./sessions",
    ):
        """
        初始化签约助手

        Args:
            project_dir: 签约系统项目目录
            api_config: API 配置，如果为 None 则使用默认配置
            system_prompt: 自定义系统提示词
            debug: 是否开启 debug 模式（输出工具调用详情）
            session_dir: 会话存储目录
        """
        self.project_dir = project_dir
        self.api_config = api_config or get_default_api_config()
        self.system_prompt = system_prompt or get_default_system_prompt()
        self.debug = debug
        self.session_manager = SessionManager(storage_dir=session_dir)

    def _create_options(self) -> ClaudeAgentOptions:
        """创建 ClaudeAgentOptions。"""
        mcp_servers = create_mcp_servers()
        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "skills"
        )

        return ClaudeAgentOptions(
            allowed_tools=[
                "mcp__knowledge__knowledge_search",
                "mcp__sre__sre_query",
                "mcp__apollo__apollo_query",
            ],
            mcp_servers=mcp_servers,
            skills="all",
            add_dirs=[skills_dir],
            permission_mode="acceptEdits",
            cwd=self.project_dir,
            system_prompt=self.system_prompt,
            env=self.api_config,
            max_turns=30,
        )

    async def chat(
        self,
        question: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        与签约助手进行对话。

        Args:
            question: 用户问题
            user_id: 用户标识（飞书 open_id）

        Yields:
            助手的回复内容
        """
        # 获取或创建会话 ID
        session_id = self.session_manager.get_or_create_session_id(user_id)

        # 检查是否是新会话（用于决定是否 resume）
        is_new_session = not self.session_manager._is_session_valid(session_id)

        # 创建客户端
        options = self._create_options()
        client = self.session_manager.create_client(
            session_id=session_id,
            options=options,
            resume=not is_new_session,  # 如果不是新会话，则 resume
        )

        # 跟踪是否有工具调用
        has_tool_calls = False
        is_first_text_after_tools = False

        try:
            # 连接客户端
            await client.connect()

            # 发送查询
            await client.query(question)

            # 接收响应
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                if self.debug and has_tool_calls and is_first_text_after_tools:
                                    yield "\n---\n\n📋 **最终结果**\n\n"
                                    is_first_text_after_tools = False
                                yield block.text

                        elif isinstance(block, ThinkingBlock):
                            if self.debug and block.thinking:
                                yield format_thinking(block.thinking)

                        elif isinstance(block, ToolUseBlock):
                            if self.debug:
                                has_tool_calls = True
                                is_first_text_after_tools = True
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

            # 保存会话
            self.session_manager.save_session(user_id, session_id)

        except Exception as e:
            logger.error(f"对话失败: {e}")
            raise
        finally:
            # 断开连接
            try:
                await client.disconnect()
            except Exception:
                pass

    async def clear_memory(self, user_id: str) -> None:
        """
        清除用户会话。

        Args:
            user_id: 用户标识
        """
        self.session_manager.delete_session(user_id)
        logger.info(f"已清除用户会话: {user_id}")
