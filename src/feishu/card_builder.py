# -*- coding: utf-8 -*-
"""飞书卡片内容构建模块 - 借鉴 cc-connect 的实现。"""

import json
import re

# 飞书表格限制（借鉴 cc-connect）
MAX_CARD_TABLES = 5


def clean_markdown(text: str) -> str:
    """
    清理 markdown 格式（飞书表格不支持 markdown 语法）

    Args:
        text: 包含 markdown 格式的文本

    Returns:
        清理后的纯文本
    """
    # 去掉粗体 **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)

    # 去掉删除线 ~~text~~
    text = re.sub(r'~~(.*?)~~', r'\1', text)

    # 去掉行内代码 `text`
    text = re.sub(r'`(.*?)`', r'\1', text)

    # 去掉链接 [text](url)，保留文本
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)

    # 去掉图片 ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 注意：不去掉斜体 *text* 和 __text__，因为下划线可能是变量名的一部分
    # 如 mcp__sre__sre_query

    return text.strip()


def build_card_content(content: str, is_thinking: bool = False) -> str:
    """
    构建飞书卡片内容

    Args:
        content: 消息内容
        is_thinking: 是否为思考状态

    Returns:
        卡片 JSON 字符串
    """
    # ── 解析内容，分离 markdown 文本和表格 ──
    elements = []
    markdown_lines = []
    in_table = False
    table_headers = []
    table_rows = []

    def flush_markdown():
        """将累积的 markdown 行添加到 elements"""
        if markdown_lines:
            text = '\n'.join(markdown_lines).strip()
            if text:
                elements.append({
                    "tag": "markdown",
                    "content": text
                })
            markdown_lines.clear()

    def flush_table():
        """将累积的表格添加到 elements（借鉴 cc-connect 的表格限制）"""
        if table_headers and table_rows:
            # 检查表格数量限制（借鉴 cc-connect: maxCardTables = 5）
            table_count = sum(1 for e in elements if e.get("tag") == "table")
            if table_count >= MAX_CARD_TABLES:
                # 超过限制，降级为 markdown 格式
                markdown_lines.append(f"**表格 {table_count + 1}（已超过显示限制）**")
                for row in table_rows[:5]:  # 只显示前 5 行
                    markdown_lines.append(" | ".join(row))
                if len(table_rows) > 5:
                    markdown_lines.append(f"... 还有 {len(table_rows) - 5} 行")
                table_headers.clear()
                table_rows.clear()
                return

            # 构建飞书 Table 组件
            columns = []
            for i, header in enumerate(table_headers):
                # 清理表头中的 markdown 格式
                clean_header = clean_markdown(header)
                columns.append({
                    "name": f"col_{i}",
                    "display_name": clean_header,
                    "data_type": "text",
                    "width": "auto"
                })

            rows = []
            for row in table_rows:
                row_data = {}
                for i, cell in enumerate(row):
                    if i < len(table_headers):
                        # 清理 markdown 格式（飞书表格不支持）
                        clean_cell = clean_markdown(cell)
                        row_data[f"col_{i}"] = clean_cell
                rows.append(row_data)

            elements.append({
                "tag": "table",
                "page_size": 10,
                "row_height": "low",
                "header_style": {
                    "text_align": "left",
                    "text_size": "normal",
                    "background_style": "grey",
                    "bold": True
                },
                "columns": columns,
                "rows": rows
            })
        table_headers.clear()
        table_rows.clear()

    lines = content.split('\n')

    for line in lines:
        # 过滤掉图片链接 ![alt](url)
        if re.search(r'!\[.*?\]\(.*?\)', line):
            continue

        # 将 ## 标题 转换为 **标题**
        if line.strip().startswith('#'):
            flush_table()
            title = re.sub(r'^#+\s*', '', line.strip())
            markdown_lines.append(f"**{title}**")
            continue

        # ── 表格处理：检测 markdown 表格，转换成飞书 Table 组件 ──
        if re.match(r'^\s*\|.*\|\s*$', line.strip()):
            cells = [c.strip() for c in line.strip().split('|') if c.strip()]

            # 跳过分隔行 |------|------|
            if all(re.match(r'^[-:]+$', c) for c in cells):
                in_table = True
                continue

            # 第一行是表头
            if not in_table:
                flush_markdown()
                table_headers = cells
                in_table = True
                continue

            # 数据行
            if table_headers and len(cells) == len(table_headers):
                table_rows.append(cells)
            continue

        # 表格结束
        if in_table and not re.match(r'^\s*\|.*\|\s*$', line.strip()):
            flush_table()
            in_table = False

        markdown_lines.append(line)

    # 处理剩余内容
    flush_markdown()
    flush_table()

    # 构建卡片
    card = {
        "elements": elements
    }

    # 如果是思考状态，添加一个 loading 提示
    if is_thinking:
        card["elements"].insert(0, {
            "tag": "markdown",
            "content": "⏳ **正在思考中...**\n\n---\n"
        })

    return json.dumps(card)
