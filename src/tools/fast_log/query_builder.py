# -*- coding: utf-8 -*-
"""ES 查询构建器 - 支持单关键词、AND、OR 查询。"""

import re
from datetime import datetime
from typing import Optional


def normalize_keyword(keyword: str) -> str:
    """统一处理布尔操作符。

    支持的格式：
    - AND / and / And / &&
    - OR / or / Or / ||

    Args:
        keyword: 原始关键词

    Returns:
        标准化后的关键词
    """
    # && → AND
    keyword = keyword.replace("&&", " AND ")
    # || → OR
    keyword = keyword.replace("||", " OR ")
    # 统一 and/or 为大写
    keyword = re.sub(r'\b(and)\b', 'AND', keyword, flags=re.IGNORECASE)
    keyword = re.sub(r'\b(or)\b', 'OR', keyword, flags=re.IGNORECASE)
    # 清理多余空格
    keyword = re.sub(r'\s+', ' ', keyword).strip()
    return keyword


def validate_keyword_syntax(keyword: str) -> Optional[str]:
    """校验 AND/OR 语法是否正确。

    Args:
        keyword: 关键词

    Returns:
        错误信息，语法正确返回 None
    """
    normalized = normalize_keyword(keyword)

    # 以 AND/OR 开头
    if normalized.startswith("AND ") or normalized.startswith("OR "):
        return "错误：关键词不能以 AND/OR 开头，如 'AND contractPersonalDataV2'。正确格式：'k1 AND k2'"

    # 以 AND/OR 结尾
    if normalized.endswith(" AND") or normalized.endswith(" OR"):
        return "错误：关键词不能以 AND/OR 结尾，如 'contractPersonalDataV2 AND'。正确格式：'k1 AND k2'"

    # 连续的 AND/OR
    if " AND AND " in normalized or " OR OR " in normalized:
        return "错误：存在连续的布尔操作符，请检查关键词格式"

    if " AND OR " in normalized or " OR AND " in normalized:
        return "错误：AND 和 OR 不能直接相邻混用。如需复杂查询，请使用单个关键词或简化的布尔表达式"

    # AND 和 OR 混用
    if " AND " in normalized and " OR " in normalized:
        return "错误：暂不支持 AND 和 OR 混用，请使用单一布尔操作符。如需同时满足多个条件用 AND，满足其一用 OR"

    return None


def build_keyword_query(keyword: str) -> dict:
    """根据关键词构建 ES query 查询。

    Args:
        keyword: 关键词（支持 AND/OR 语法）

    Returns:
        ES query dict
    """
    normalized = normalize_keyword(keyword)

    if " AND " in normalized:
        parts = normalized.split(" AND ")
        return {
            "bool": {
                "must": [
                    {"query_string": {"query": p.strip()}}
                    for p in parts if p.strip()
                ]
            }
        }
    elif " OR " in normalized:
        parts = normalized.split(" OR ")
        return {
            "bool": {
                "should": [
                    {"query_string": {"query": p.strip()}}
                    for p in parts if p.strip()
                ],
                "minimum_should_match": 1
            }
        }
    else:
        return {"query_string": {"query": normalized}}


def build_query_payload(
    keyword: str,
    start: datetime,
    end: datetime,
    index: str,
    fetch_size: int = 500
) -> dict:
    """构建完整的 ES 查询 payload。

    Args:
        keyword: 关键词
        start: 开始时间
        end: 结束时间
        index: ES 索引模式
        fetch_size: 返回条数

    Returns:
        完整的查询 payload
    """
    keyword_query = build_keyword_query(keyword)

    return {
        "params": {
            "index": index,
            "body": {
                "size": fetch_size,
                "sort": [{"timestamp": {"order": "desc"}}],
                "query": {
                    "bool": {
                        "must": [keyword_query],
                        "filter": [
                            {
                                "range": {
                                    "timestamp": {
                                        "gte": start.isoformat(),
                                        "lte": end.isoformat(),
                                        "format": "strict_date_optional_time"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
        "serverStrategy": "es"
    }
