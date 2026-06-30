# -*- coding: utf-8 -*-
"""飞书卡片内容构建模块 - 对照 cc-connect 实现。

cc-connect 的做法：
- card 用 schema 2.0，内容放在单个 markdown 元素中
- 不使用 Table 组件（表格直接作为 markdown 文本）
- 表格 >5 个时降级为 post 格式（md 标签）
- 不压缩正文内容
"""

import json
import re


# ── 内容预处理（参照 cc-connect 的 sanitizeCardMarkdownForCard）──

def _preprocess_markdown(content: str) -> str:
    """预处理 markdown 内容，确保飞书 card 正确渲染。

    参照 cc-connect:
    - preprocessFeishuMarkdown: 确保代码块前有换行
    - sanitizeMarkdownURLs: 去掉非 HTTP 链接
    """
    # 确保 ``` 前有换行
    result = []
    for i, ch in enumerate(content):
        if i > 0 and content[i:i+3] == '```' and content[i-1] != '\n':
            result.append('\n')
        result.append(ch)
    content = ''.join(result)

    # 去掉非 HTTP(S) 链接（飞书 API 会拒绝 code 230001）
    content = re.sub(
        r'\[([^\]]*)\]\((?!https?://)([^)]+)\)',
        r'\1',
        content,
    )

    # 去掉飞书不支持的图片引用（非 img_ 开头的）
    content = re.sub(r'!\[(?!img_)[^\]]*\]\([^)]*\)', '', content)

    # 折叠连续 3+ 空行为 2 空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


# ── 卡片构建（参照 cc-connect 的 buildCardJSON）──

def build_card_content(content: str, is_thinking: bool = False) -> str:
    """构建飞书卡片内容（card schema 2.0）。

    对照 cc-connect 的 buildCardJSON:
    - schema 2.0
    - 单个 markdown 元素
    - 不使用 Table 组件

    Args:
        content: 消息内容
        is_thinking: 是否为思考状态

    Returns:
        卡片 JSON 字符串
    """
    content = _preprocess_markdown(content)

    # 思考状态加在内容前面
    if is_thinking:
        content = "⏳ **正在思考中...**\n\n---\n\n" + content

    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "streaming_mode": True,
            "update_multi": True,
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


# ── Post 格式构建（参照 cc-connect 的 buildPostMdJSON）──

def build_post_md_json(content: str) -> str:
    """构建 post 消息格式。

    对照 cc-connect 的 buildPostMdJSON:
    - 使用 md 标签渲染 markdown
    - 不压缩内容

    Args:
        content: markdown 内容

    Returns:
        post 消息 JSON 字符串
    """
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
