"""
签约助手 Agent

基于 Claude Code SDK 实现的签约系统智能助手。
"""

import os
import json
import asyncio
from typing import Optional, AsyncGenerator
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
)

from ..tools import knowledge_search, sre_query


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


def format_tool_use(tool: str, inp: dict) -> str:
    """格式化工具调用信息（完整参数）"""
    icon = TOOL_ICONS.get(tool, "🔧")

    # 格式化参数
    if inp:
        params = []
        for k, v in inp.items():
            v_str = str(v)
            # 截断过长的值
            if len(v_str) > 200:
                v_str = v_str[:200] + "..."
            params.append(f"  {k}: {v_str}")
        params_str = "\n".join(params)
        return f"\n{icon} **{tool}**\n{params_str}\n"
    else:
        return f"\n{icon} **{tool}**\n"


def format_tool_result(content: str, is_error: bool = False) -> str:
    """格式化工具执行结果"""
    prefix = "❌" if is_error else "✅"

    # 截断过长的结果
    if len(content) > 1000:
        content = content[:1000] + "\n... (结果已截断)"

    return f"\n{prefix} **工具结果**\n{content}\n"


def format_thinking(thinking: str) -> str:
    """格式化思考过程"""
    # 截断过长的思考
    if len(thinking) > 500:
        thinking = thinking[:500] + "\n... (思考已截断)"

    return f"\n💭 **思考中...**\n{thinking}\n"


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
        self.api_config = api_config or self._default_api_config()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.debug = debug

    def _default_api_config(self) -> dict:
        """默认 API 配置"""
        return {
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            "ANTHROPIC_AUTH_TOKEN": "",  # 需要从环境变量或配置文件读取
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-8",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
        }

    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是签约系统助手，专门帮助用户查询和排查签约系统的问题。

## 你的核心能力

1. **知识库搜索** — 使用 `mcp__knowledge__knowledge_search` 工具搜索知识库
2. **SRE 数据查询** — 使用 `mcp__sre__sre_query` 工具查询生产环境数据

## 工具使用指南

### 知识库搜索
当用户询问业务知识、流程规范、字段含义等问题时，使用知识库搜索：
```
mcp__knowledge__knowledge_search(query="合同签署流程")
```

### SRE 数据查询
当用户需要查询生产环境数据时，使用 SRE 查询工具。

**参数格式识别规则**：
| 参数 | 格式特征 | 示例 |
|------|---------|------|
| 合同编号 (contract_code) | 以字母 "C" 开头 + 数字 | C1776759658764987 |
| 订单号 (project_order_id) | 纯数字，通常 18 位 | 826041310000003912 |

**支持的 action 类型**：
- `contract` — 查询合同信息（需要 contract_code 或 project_order_id）
- `contract_node` — 查询合同节点（需要 contract_code）
- `contract_user` — 查询签约人（需要 contract_code）
- `contract_field` — 查询合同扩展字段（需要 contract_code）
- `contract_log` — 查询操作日志（需要 contract_code）
- `config_snap` — 查询配置快照（需要 project_order_id）
- `decrypt` — 解密敏感信息（需要 encrypted_text）

**查询示例**：
```
mcp__sre__sre_query(action="contract", project_order_id="826041310000003912")
mcp__sre__sre_query(action="contract", contract_code="C1776759658764987")
mcp__sre__sre_query(action="contract_node", contract_code="C1776759658764987")
mcp__sre__sre_query(action="contract_log", contract_code="C1776759658764987")
```

**重要**：
- 必须使用正确的 action 名称（如 "contract"，不是 "query_contracts"）
- 参数名必须准确（如 "contract_code"，不是 "contractCode"）
- 如果不确定参数类型，询问用户

## 注意事项
- 只读操作，不会修改任何数据
- 引用具体的字段值和数据
- 遇到不确定的问题，明确告知用户"""

    def _create_mcp_servers(self) -> dict:
        """创建 MCP 服务器配置。"""
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

        return {
            "knowledge": knowledge_server,
            "sre": sre_server,
        }

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
        ]
        all_tools = allowed_tools + mcp_tools

        # 创建 MCP 服务器
        mcp_servers = self._create_mcp_servers()

        # skills 目录
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")

        options = ClaudeAgentOptions(
            allowed_tools=all_tools,
            mcp_servers=mcp_servers,
            skills="all",  # 加载所有 skills
            add_dirs=[skills_dir],  # 添加 skills 目录
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
                        if block.text:  # 只输出非空文本
                            yield block.text

                    elif isinstance(block, ThinkingBlock):
                        # 思考过程（仅 debug 模式）
                        if self.debug and block.thinking:
                            yield format_thinking(block.thinking)

                    elif isinstance(block, ToolUseBlock):
                        # 工具调用信息（仅 debug 模式）
                        if self.debug:
                            yield format_tool_use(block.name, block.input)

            elif isinstance(message, UserMessage):
                # 工具执行结果（仅 debug 模式）
                if self.debug and message.tool_use_result:
                    result = message.tool_use_result
                    # 处理不同类型的 tool_use_result
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
                pass  # 跳过结果消息

    async def chat_and_print(self, question: str):
        """对话并直接打印结果"""
        async for text in self.chat(question):
            print(text, end="", flush=True)
        print()  # 换行

    async def analyze_contract(self, contract_type: str) -> str:
        """
        分析特定类型的合同模板

        Args:
            contract_type: 合同类型

        Returns:
            分析结果
        """
        question = f"请分析签约系统中 {contract_type} 类型的合同模板，包括：1. 模板结构 2. 关键字段 3. 业务规则 4. 签约流程"
        result = []
        async for text in self.chat(question):
            result.append(text)
        return "".join(result)

    async def explain_sign_flow(self, flow_name: str) -> str:
        """
        解释签约流程

        Args:
            flow_name: 流程名称

        Returns:
            流程解释
        """
        question = f"请详细解释签约系统中的 {flow_name} 流程，包括：1. 流程步骤 2. 参与角色 3. 状态流转 4. 异常处理"
        result = []
        async for text in self.chat(question):
            result.append(text)
        return "".join(result)

    async def troubleshoot(self, issue_description: str) -> str:
        """
        排查签约问题

        Args:
            issue_description: 问题描述

        Returns:
            排查结果和建议
        """
        question = f"签约系统遇到以下问题，请帮我排查：\n{issue_description}\n\n请分析可能的原因并提供解决方案。"
        result = []
        async for text in self.chat(question):
            result.append(text)
        return "".join(result)
