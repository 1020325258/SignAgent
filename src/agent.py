"""
签约助手 Agent

基于 Claude Code SDK 实现的签约系统智能助手。
"""

import asyncio
from typing import Optional, AsyncGenerator
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ToolUseBlock, ResultMessage


# 工具图标和显示格式
TOOL_DISPLAY = {
    "Read": ("📄", lambda inp: inp.get("file_path", "")),
    "Grep": ("🔍", lambda inp: f"{inp.get('pattern', '')} in {inp.get('path', '.')}"),
    "Bash": ("💻", lambda inp: inp.get("command", "")),
    "Glob": ("📁", lambda inp: inp.get("pattern", "")),
    "Write": ("✏️", lambda inp: inp.get("file_path", "")),
    "Edit": ("✏️", lambda inp: inp.get("file_path", "")),
    "WebFetch": ("🌐", lambda inp: inp.get("url", "")),
    "WebSearch": ("🔍", lambda inp: inp.get("query", "")),
}


def format_tool_use(tool: str, inp: dict) -> str:
    """格式化工具调用信息"""
    if tool in TOOL_DISPLAY:
        icon, get_desc = TOOL_DISPLAY[tool]
        desc = get_desc(inp)
        return f"\n{icon} {tool}: {desc}\n"
    else:
        # 未知工具，显示工具名和第一个参数
        first_value = next(iter(inp.values()), "") if inp else ""
        return f"\n🔧 {tool}: {first_value}\n"


class SignAgent:
    """签约系统智能助手"""

    def __init__(
        self,
        project_dir: str,
        api_config: Optional[dict] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        初始化签约助手

        Args:
            project_dir: 签约系统项目目录
            api_config: API 配置，如果为 None 则使用默认配置
            system_prompt: 自定义系统提示词
        """
        self.project_dir = project_dir
        self.api_config = api_config or self._default_api_config()
        self.system_prompt = system_prompt or self._default_system_prompt()

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
        return """你是签约系统助手，专门帮助用户理解和使用签约系统。

你的职责：
1. 回答关于签约流程、合同模板、签约状态等问题
2. 解释系统功能和操作步骤
3. 协助排查签约相关的问题
4. 提供签约系统的最佳实践建议

能力范围：
- 阅读和分析签约系统代码
- 搜索合同模板和配置
- 查询签约记录和状态
- 解释业务规则和流程

注意事项：
- 只读操作，不会修改任何代码或数据
- 引用具体的文件路径和代码行号
- 提供准确的业务术语解释
- 遇到不确定的问题，明确告知用户"""

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
            allowed_tools = ["Read", "Glob", "Grep", "Bash"]

        options = ClaudeAgentOptions(
            allowed_tools=allowed_tools,
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
                    elif isinstance(block, ToolUseBlock):
                        # 通用工具调用信息
                        tool = block.name
                        inp = block.input
                        yield format_tool_use(tool, inp)
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
