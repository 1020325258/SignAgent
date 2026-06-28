# -*- coding: utf-8 -*-
"""格式化工具模块。"""

from .config import TOOL_ICONS


def format_tool_use(tool: str, inp: dict) -> str:
    """格式化工具调用信息（完整参数）。

    Args:
        tool: 工具名称
        inp: 工具输入参数

    Returns:
        格式化后的字符串
    """
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
    """格式化工具执行结果。

    Args:
        content: 工具返回内容
        is_error: 是否为错误结果

    Returns:
        格式化后的字符串
    """
    prefix = "❌" if is_error else "✅"

    # 截断过长的结果
    if len(content) > 1000:
        content = content[:1000] + "\n... (结果已截断)"

    return f"\n{prefix} **工具结果**\n{content}\n"


def format_thinking(thinking: str) -> str:
    """格式化思考过程。

    Args:
        thinking: 思考内容

    Returns:
        格式化后的字符串
    """
    # 截断过长的思考
    if len(thinking) > 500:
        thinking = thinking[:500] + "\n... (思考已截断)"

    return f"\n💭 **思考中...**\n{thinking}\n"
