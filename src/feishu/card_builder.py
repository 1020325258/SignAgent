# -*- coding: utf-8 -*-
"""飞书卡片内容构建模块 - 对照 cc-connect 实现。

支持两种卡片：
1. 简单卡片 — 单个 markdown 元素
2. 富卡片 — 折叠面板（思考/工具）+ markdown 正文 + header + footer
"""

import json
import re
from typing import List, Dict


# ── 内容预处理（参照 cc-connect 的 sanitizeCardMarkdownForCard）──

def preprocess_markdown(content: str) -> str:
    """预处理 markdown 内容，确保飞书 card 正确渲染。"""
    result = []
    for i, ch in enumerate(content):
        if i > 0 and content[i:i+3] == '```' and content[i-1] != '\n':
            result.append('\n')
        result.append(ch)
    content = ''.join(result)

    content = re.sub(
        r'\[([^\]]*)\]\((?!https?://)([^)]+)\)',
        r'\1',
        content,
    )

    content = re.sub(r'!\[(?!img_)[^\]]*\]\([^)]*\)', '', content)

    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


# ── 折叠面板（参照 cc-connect 的 buildRichPanel）──

def _build_collapsible_panel(title: str, expanded: bool, elements: List[dict]) -> dict:
    """构建飞书折叠面板。"""
    return {
        "tag": "collapsible_panel",
        "expanded": expanded,
        "background_color": "grey",
        "header": {
            "title": {"tag": "plain_text", "content": title},
        },
        "border": {"color": "grey"},
        "vertical_spacing": "8px",
        "padding": "4px 8px",
        "elements": elements,
    }


def _build_step_element(text: str, icon_token: str = "chat-forbidden", text_color: str = "grey", done: bool = False) -> dict:
    """构建单个步骤元素。"""
    return {
        "tag": "div",
        "icon": {"tag": "standard_icon", "token": icon_token},
        "text": {
            "tag": "plain_text",
            "content": ("✅ " if done else "") + text,
            "text_size": "notation",
            "text_color": text_color,
        },
    }


def _build_panel_elements(steps: List[Dict], max_steps: int = 10) -> list:
    """构建面板内的元素列表。"""
    if not steps:
        return [_build_step_element("等待中...", text_color="grey")]

    elements = []
    hidden = 0
    if len(steps) > max_steps:
        hidden = len(steps) - max_steps
        steps = steps[hidden:]

    if hidden > 0:
        elements.append(_build_step_element(f"... {hidden} 个步骤已隐藏", text_color="grey"))

    for step in steps:
        text = step.get("text", "")
        icon = step.get("icon", "chat-forbidden")
        color = step.get("color", "grey")
        done = step.get("done", False)
        elements.append(_build_step_element(text, icon_token=icon, text_color=color, done=done))

    return elements


# ── Header 和 Footer（对照 cc-connect）──

def _build_header(status: str = "working") -> dict:
    """构建卡片 header。

    对照 cc-connect:
    - blue = 思考中/工作中
    - green = 完成
    - red = 错误
    """
    templates = {
        "thinking": ("blue", "思考中..."),
        "working": ("blue", "工作中..."),
        "done": ("green", "完成"),
        "error": ("red", "错误"),
    }
    template, title = templates.get(status, ("blue", "工作中..."))
    return {
        "template": template,
        "title": {"tag": "plain_text", "content": title},
    }


def _build_footer(elapsed_seconds: float = 0, model: str = "") -> list:
    """构建 footer 元素列表（hr + 信息行）。"""
    parts = []
    if elapsed_seconds > 0:
        parts.append(f"⏱ {elapsed_seconds:.1f}s")
    if model:
        parts.append(model)

    if not parts:
        return []

    return [
        {"tag": "hr"},
        {
            "tag": "markdown",
            "content": " | ".join(parts),
            "text_size": "notation",
        },
    ]


# ── 卡片构建 ──

def build_card_content(content: str, is_thinking: bool = False) -> str:
    """构建简单飞书卡片（单个 markdown 元素）。"""
    content = preprocess_markdown(content)

    if is_thinking:
        content = "⏳ **正在思考中...**\n\n---\n\n" + content

    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "streaming_mode": True,
            "update_multi": True,
            "enable_forward_interaction": True,
        },
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "element_id": "main_text",
                    "content": content,
                }
            ],
        },
    }
    return json.dumps(card, ensure_ascii=False)


def build_rich_card_content(
    thinking_steps: List[Dict],
    tool_steps: List[Dict],
    markdown: str,
    is_streaming: bool = True,
    status: str = "working",
    elapsed_seconds: float = 0,
    model: str = "",
) -> str:
    """构建富飞书卡片（header + 折叠面板 + markdown 正文 + footer）。

    Args:
        thinking_steps: 思考步骤列表
        tool_steps: 工具调用步骤列表
        markdown: 正文内容
        is_streaming: 是否正在流式输出
        status: 状态（thinking/working/done/error）
        elapsed_seconds: 已用时间（秒）
        model: 模型名称
    """
    markdown = preprocess_markdown(markdown)
    elements = []

    # Reasoning 折叠面板
    if thinking_steps or is_streaming:
        panel_title = f"思考 ({len(thinking_steps)})" if thinking_steps else "思考中..."
        panel_elements = _build_panel_elements(thinking_steps)
        elements.append(_build_collapsible_panel(
            title=panel_title,
            expanded=is_streaming,
            elements=panel_elements,
        ))

    # Tools 折叠面板
    if tool_steps:
        panel_title = f"工具 ({len(tool_steps)})"
        panel_elements = _build_panel_elements(tool_steps)
        elements.append(_build_collapsible_panel(
            title=panel_title,
            expanded=False,
            elements=panel_elements,
        ))

    # markdown 正文
    elements.append({
        "tag": "markdown",
        "element_id": "main_text",
        "content": markdown if markdown else " ",
    })

    # Footer
    footer_elements = _build_footer(elapsed_seconds, model)
    elements.extend(footer_elements)

    # Header（streaming 时用蓝色，结束时用绿色）
    header_status = status if not is_streaming else "working"
    if is_streaming and not thinking_steps and not tool_steps and not markdown.strip():
        header_status = "thinking"

    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "streaming_mode": is_streaming,
            "update_multi": True,
            "enable_forward_interaction": True,
        },
        "header": _build_header(header_status),
        "body": {
            "elements": elements,
        },
    }
    return json.dumps(card, ensure_ascii=False)


# ── Post 格式构建 ──

def build_post_md_json(content: str) -> str:
    """构建 post 消息格式。"""
    post = {
        "zh_cn": {
            "content": [
                [
                    {"tag": "md", "text": content}
                ]
            ]
        }
    }
    return json.dumps(post, ensure_ascii=False)
