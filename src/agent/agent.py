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


# ── 工作目录隔离：路径白名单守卫 ────────────────────────────

# 各工具的路径参数名映射
_TOOL_PATH_KEYS: dict[str, list[str]] = {
    "Read": ["file_path"],
    "Write": ["file_path"],
    "Edit": ["file_path"],
    "MultiEdit": ["file_path"],
    "Glob": ["pattern"],
    "Grep": ["path"],
    "NotebookEdit": ["notebook_path"],
}


def _create_path_guard(project_dir: str):
    """创建一个 PreToolUse hook，拦截所有试图访问工作目录外的文件操作。

    原理：Hook 在每个工具调用前触发，提取工具的路径参数，解析为绝对路径后
    检查是否在 project_dir 子树内。不在子树内的操作直接返回 deny。

    注意：
    - Bash 命令由 Sandbox 做 OS 级隔离，本 hook 只做辅助日志
    - 相对路径天然解析到 cwd（即 project_dir），自动安全
    - 网络工具（WebFetch/WebSearch）通过 disallowed_tools 禁用
    """
    from pathlib import Path

    project_root = Path(project_dir).resolve()

    def _resolve(path_str: str) -> Path:
        """将工具参数中的路径解析为绝对路径。"""
        p = Path(path_str)
        if p.is_absolute():
            return p
        # 展开 ~ 并相对于 project_root 解析
        expanded = Path(p.expanduser().expand_vars())
        if expanded.is_absolute():
            return expanded
        return (project_root / expanded).resolve()

    async def guard(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if tool_name not in _TOOL_PATH_KEYS:
            return {}

        for key in _TOOL_PATH_KEYS[tool_name]:
            path_str = tool_input.get(key)
            if not path_str or not isinstance(path_str, str):
                continue

            # Glob pattern 的绝对路径检查（相对 pattern 合法）
            if tool_name == "Glob" and not path_str.startswith("/"):
                continue

            # Grep path 的相对路径
            if tool_name == "Grep" and not path_str.startswith("/"):
                continue

            resolved = _resolve(path_str)

            try:
                resolved.relative_to(project_root)
            except ValueError:
                logger.warning(
                    f"⛔ 越界访问被拦截: {tool_name} → {resolved}"
                )
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"禁止访问工作目录外的路径。\n"
                            f"请求路径: {resolved}\n"
                            f"工作目录: {project_root}"
                        ),
                    }
                }

        return {}

    return guard


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
        """创建 ClaudeAgentOptions。

        安全策略（多层防线）：
        1. cwd + setting_sources=["project"] — 隔离用户级配置
        2. PreToolUse Hook 路径白名单 — 拦截 Read/Write/Edit/Glob/Grep 越界访问
        3. Sandbox — Bash 命令的 OS 级文件系统 + 网络隔离
        4. tools / disallowed_tools — 禁用不必要的内置工具
        """
        mcp_servers = create_mcp_servers()

        # CLI stderr 回调：将子进程的 stderr 输出转发到日志
        def _on_stderr(message: str) -> None:
            msg = message.rstrip()
            if msg:
                _sdk_stderr_logger.debug(msg)

        # 创建路径守卫 hook（闭包捕获 self.project_dir）
        _path_guard = _create_path_guard(self.project_dir)

        return ClaudeAgentOptions(
            # ── 工作目录 ──
            cwd=self.project_dir,
            setting_sources=["project"],  # 不加载 ~/.claude/CLAUDE.md

            # ── 工具集：只保留必需的 ──
            tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            allowed_tools=[
                "Read", "Write", "Edit", "Glob", "Grep",
                "mcp__knowledge__knowledge_search",
                "mcp__sre__sre_query",
                "mcp__apollo__apollo_query",
                "mcp__fast_log__fast_log_query",
            ],
            disallowed_tools=[
                "WebFetch",
                "WebSearch",
                "NotebookEdit",
            ],

            # ── MCP ──
            mcp_servers=mcp_servers,
            skills="all",

            # ── 权限 ──
            permission_mode="acceptEdits",

            # ── System Prompt ──
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.system_prompt,
            },

            # ── 运行时 ──
            env=self.api_config,
            max_turns=50,
            stderr=_on_stderr,

            # ── Hooks（多层） ──
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[_path_guard]),      # 第 1 层：路径白名单
                    HookMatcher(hooks=[_log_pre_tool_use]), # 第 2 层：审计日志
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[_log_post_tool_use]),
                ],
                "PostToolUseFailure": [
                    HookMatcher(hooks=[_log_post_tool_use_failure]),
                ],
            },

            # ── Sandbox：Bash 命令的 OS 级隔离 ──
            sandbox={
                "enabled": True,
                "autoAllowBashIfSandboxed": True,
                "allowUnsandboxedCommands": False,  # 严格模式：禁止绕过沙箱
                "filesystem": {
                    # 写权限：仅项目目录 + 临时目录（沙箱默认行为）
                    "denyRead": [
                        "~/.ssh/**",
                        "~/.aws/**",
                        "~/.config/gcloud/**",
                    ],
                },
                "network": {
                    "deniedDomains": ["*"],  # Bash 子进程禁止外网
                },
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
