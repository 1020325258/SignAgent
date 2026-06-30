# -*- coding: utf-8 -*-
"""签约助手 Agent 核心模块。"""

import os
import logging
from typing import Optional, AsyncGenerator, Dict, Any
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
            max_turns=50,
        )

    async def chat(
        self,
        question: str,
        user_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        与签约助手进行对话。

        Yields:
            结构化事件字典:
            - {"type": "text", "content": "..."} — agent 文本输出
            - {"type": "thinking", "content": "..."} — 思考过程
            - {"type": "tool_use", "name": "...", "input": "..."} — 工具调用
            - {"type": "tool_result", "content": "...", "is_error": bool} — 工具结果（仅日志）
        """
        session_id = self.session_manager.get_or_create_session_id(user_id)
        is_new_session = not self.session_manager._is_session_valid(session_id)

        options = self._create_options()
        client = self.session_manager.create_client(
            session_id=session_id,
            options=options,
            resume=not is_new_session,
        )

        try:
            await client.connect()
            await client.query(question)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                yield {"type": "text", "content": block.text}

                        elif isinstance(block, ThinkingBlock):
                            if block.thinking:
                                yield {"type": "thinking", "content": block.thinking}

                        elif isinstance(block, ToolUseBlock):
                            yield {
                                "type": "tool_use",
                                "name": block.name,
                                "input": _summarize_tool_input(block.name, block.input),
                            }

                elif isinstance(message, UserMessage):
                    if message.tool_use_result:
                        result = message.tool_use_result
                        is_error = False
                        if isinstance(result, dict):
                            content = result.get("content", "")
                            is_error = result.get("is_error", False)
                        elif isinstance(result, list):
                            parts = []
                            for item in result:
                                if isinstance(item, dict):
                                    text = item.get("text", "")
                                    if text:
                                        parts.append(text)
                            content = "\n".join(parts)
                        elif isinstance(result, str):
                            content = result
                        else:
                            content = str(result)
                        # 工具结果：打日志 + yield 事件（用于标记工具完成状态）
                        if content:
                            logger.info(f"工具结果: {content[:500]}...")
                        yield {"type": "tool_result", "content": content, "is_error": is_error}

                elif isinstance(message, ResultMessage):
                    pass

            self.session_manager.save_session(user_id, session_id)

        except Exception as e:
            logger.error(f"对话失败: {e}")
            raise
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def clear_memory(self, user_id: str) -> None:
        """清除用户会话。"""
        self.session_manager.delete_session(user_id)
        logger.info(f"已清除用户会话: {user_id}")


def _summarize_tool_input(name: str, inp: dict) -> str:
    """生成工具输入的摘要文本。"""
    if not inp:
        return name
    params = []
    for k, v in inp.items():
        v_str = str(v)
        if len(v_str) > 100:
            v_str = v_str[:100] + "..."
        params.append(f"{k}: {v_str}")
    return f"{name}({', '.join(params)})"
