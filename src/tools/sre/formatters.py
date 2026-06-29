# -*- coding: utf-8 -*-
"""结果格式化模块。"""

import logging
from typing import Any

from .config import get_field_meaning
from .enums import ENUM_REGISTRY

logger = logging.getLogger(__name__)


def translate_enum(enum_name: str, value: Any) -> str:
    """翻译枚举值，返回 '值=含义' 格式。

    Args:
        enum_name: 枚举类型名，如 "ContractTypeEnum"。
        value: 枚举值。

    Returns:
        翻译后的字符串，如 "6=整装首期款合同"。
        如果无法翻译，返回原值字符串。
    """
    if not enum_name or value is None:
        return str(value)

    mapping = ENUM_REGISTRY.get(enum_name)
    if mapping:
        try:
            int_value = int(value)
            translated = mapping.get(int_value)
            if translated:
                return f"{int_value}={translated}"
        except (ValueError, TypeError):
            translated = mapping.get(str(value))
            if translated:
                return f"{value}={translated}"

    return str(value)


def format_result(action: str, data: Any) -> str:
    """格式化查询结果。

    Args:
        action: 操作类型
        data: 查询结果数据

    Returns:
        格式化后的字符串
    """
    # 处理空结果
    if data is None:
        return "查询结果为空"

    # 根据数据类型格式化
    if isinstance(data, list):
        return format_list(action, data)
    elif isinstance(data, dict):
        return format_object(action, data)
    else:
        return f"## 查询结果\n\n```json\n{data}\n```"


def format_list(action: str, data: list) -> str:
    """格式化列表数据。"""
    if not data:
        return "查询结果为空"

    if not isinstance(data[0], dict):
        return f"## 查询结果\n\n" + "\n".join(f"- {item}" for item in data)

    keys = list(data[0].keys())

    # 如果字段太多（>6），只展示关键字段
    MAX_COLUMNS = 6
    if len(keys) > MAX_COLUMNS:
        # 优先展示有含义的字段
        key_scores = []
        for key in keys:
            meaning = get_field_meaning(action, key)
            score = 2 if meaning and meaning[0] else (1 if key in ["id", "fieldKey", "fieldName", "moduleKey", "name"] else 0)
            key_scores.append((key, score))
        # 按分数排序，取前 MAX_COLUMNS 个
        key_scores.sort(key=lambda x: -x[1])
        keys = [k for k, _ in key_scores[:MAX_COLUMNS]]

    lines = [f"## 查询结果 ({len(data)} 条)\n"]

    # 表头
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("| " + " | ".join(["---"] * len(keys)) + " |")

    # 含义行
    meanings = []
    for key in keys:
        meaning = get_field_meaning(action, key)
        meanings.append(meaning[0] if meaning else "")
    lines.append("| " + " | ".join(meanings) + " |")

    # 数据行（最多显示 20 行）
    MAX_ROWS = 20
    for item in data[:MAX_ROWS]:
        values = []
        for key in keys:
            meaning = get_field_meaning(action, key)
            if meaning:
                _, enum_name = meaning
                str_value = translate_enum(enum_name, item.get(key)) if enum_name else str(item.get(key, ""))
            else:
                str_value = str(item.get(key, ""))

            if len(str_value) > 50:
                str_value = str_value[:50] + "..."
            values.append(str_value)
        lines.append("| " + " | ".join(values) + " |")

    # 如果数据被截断，添加提示
    if len(data) > MAX_ROWS:
        lines.append(f"\n... 还有 {len(data) - MAX_ROWS} 条数据未显示")

    return "\n".join(lines)


def format_object(action: str, data: dict) -> str:
    """格式化对象数据。"""
    lines = ["## 查询结果\n"]
    lines.append("| 字段 | 值 | 含义 |")
    lines.append("|------|-----|------|")

    for key, value in data.items():
        meaning = get_field_meaning(action, key)
        if meaning:
            desc, enum_name = meaning
            str_value = translate_enum(enum_name, value) if enum_name else str(value)
            col3 = desc
        else:
            str_value = str(value)
            col3 = "-"

        if len(str_value) > 200:
            str_value = str_value[:200] + "..."
        lines.append(f"| {key} | {str_value} | {col3} |")

    return "\n".join(lines)


