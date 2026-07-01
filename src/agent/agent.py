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
from claude_agent_sdk.types import (
    HookInput,
    HookContext,
    HookJSONOutput,
    HookMatcher,
)

from .config import get_default_api_config, get_default_system_prompt
from .mcp_factory import create_mcp_servers
from .session_manager import SessionManager

logger = logging.getLogger(__name__)
# CLI stderr 输出专用 logger，便于独立过滤
_sdk_stderr_logger = logging.getLogger(f"{__name__}.sdk_stderr")


# ── Hook 回调：记录工具调用生命周期 ──────────────────────────

async def _log_pre_tool_use(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PreToolUse hook：记录工具调用开始。"""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    # 截断过长的输入参数
    input_str = str(tool_input)
    if len(input_str) > 500:
        input_str = input_str[:500] + "..."
    logger.info(f"🔧 工具调用开始: {tool_name} | 参数: {input_str}")
    return {}


async def _log_post_tool_use(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PostToolUse hook：记录工具调用结果。"""
    tool_name = input_data.get("tool_name", "unknown")
    tool_response = input_data.get("tool_response", "")
    response_str = str(tool_response)
    if len(response_str) > 500:
        response_str = response_str[:500] + "..."
    logger.info(f"✅ 工具调用完成: {tool_name} | 结果: {response_str}")
    return {}


async def _log_post_tool_use_failure(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PostToolUseFailure hook：记录工具调用失败。"""
    tool_name = input_data.get("tool_name", "unknown")
    error = input_data.get("error", "unknown error")
    logger.error(f"❌ 工具调用失败: {tool_name} | 错误: {error}")
    return {}


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

        # CLI stderr 回调：将子进程的 stderr 输出转发到日志
        def _on_stderr(message: str) -> None:
            msg = message.rstrip()
            if msg:
                _sdk_stderr_logger.debug(msg)

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
            stderr=_on_stderr,
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[_log_pre_tool_use]),
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[_log_post_tool_use]),
                ],
                "PostToolUseFailure": [
                    HookMatcher(hooks=[_log_post_tool_use_failure]),
                ],
            },
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

        logger.info(
            f"对话开始 | user_id={user_id} | session={session_id[:8]}... | "
            f"{'新会话' if is_new_session else '恢复会话'} | "
            f"问题: {question[:100]}{'...' if len(question) > 100 else ''}"
        )

        try:
            await client.connect()
            await client.query(question)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                logger.debug(f"文本输出: {block.text[:200]}...")
                                yield {"type": "text", "content": block.text}

                        elif isinstance(block, ThinkingBlock):
                            if block.thinking:
                                logger.debug(f"思考过程: {block.thinking[:200]}...")
                                yield {"type": "thinking", "content": block.thinking}

                        elif isinstance(block, ToolUseBlock):
                            logger.debug(
                                f"工具请求: {block.name} | "
                                f"输入: {_summarize_tool_input(block.name, block.input)}"
                            )
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
                    # 记录会话结束的统计信息
                    logger.info(
                        f"对话结束 | turns={message.num_turns} | "
                        f"duration={message.duration_ms}ms | "
                        f"api_duration={message.duration_api_ms}ms | "
                        f"cost=${message.total_cost_usd:.4f} | "
                        f"stop_reason={message.stop_reason}"
                    )

            self.session_manager.save_session(user_id, session_id)

        except Exception as e:
            logger.error(f"对话失败: {e}", exc_info=True)
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
