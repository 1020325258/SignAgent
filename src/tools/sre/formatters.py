# -*- coding: utf-8 -*-
"""结果格式化模块。"""

import json
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


def format_value(action: str, key: str, value: Any) -> str:
    """格式化单个值，包含枚举翻译。

    Args:
        action: 操作类型
        key: 字段名
        value: 字段值

    Returns:
        格式化后的字符串
    """
    if value is None:
        return ""

    meaning = get_field_meaning(action, key)
    if meaning:
        _, enum_name = meaning
        if enum_name:
            return translate_enum(enum_name, value)

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
    """格式化列表数据为 JSON 格式。"""
    if not data:
        return "查询结果为空"

    if not isinstance(data[0], dict):
        return f"## 查询结果\n\n" + "\n".join(f"- {item}" for item in data)

    # 转换为 JSON 格式，包含枚举翻译
    formatted_data = []
    for item in data:
        formatted_item = {}
        for k, v in item.items():
            formatted_item[k] = format_value(action, k, v)
        formatted_data.append(formatted_item)

    return f"## 查询结果 ({len(data)} 条)\n\n```json\n{json.dumps(formatted_data, ensure_ascii=False, indent=2)}\n```"


def format_object(action: str, data: dict) -> str:
    """格式化对象数据为 JSON 格式。"""
    truncated = {}
    for k, v in data.items():
        truncated[k] = format_value(action, k, v)

    return f"## 查询结果\n\n```json\n{json.dumps(truncated, ensure_ascii=False, indent=2)}\n```"
