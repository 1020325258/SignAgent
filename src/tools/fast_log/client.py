# -*- coding: utf-8 -*-
"""FAST 日志平台 API 客户端。"""

import json
import logging
from datetime import datetime
from typing import Tuple, List

import httpx

from .query_builder import build_query_payload

logger = logging.getLogger(__name__)

FAST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "kbn-version": "7.7.0"
}


def extract_content(src: dict) -> str:
    """从日志源中提取内容。

    优先级：message > data_msg > data_info_msg > data_resp_result > data_errmsg > data_all

    Args:
        src: 日志 _source 字段

    Returns:
        日志内容字符串
    """
    content = (
        src.get('message') or
        src.get('data_msg') or
        src.get('data_info_msg') or
        src.get('data_resp_result') or
        src.get('data_errmsg') or
        src.get('data_all')
    )
    if not content:
        content = json.dumps(src, ensure_ascii=False)
    return content


async def fetch_logs(
    keyword: str,
    start: datetime,
    end: datetime,
    index: str,
    fast_domain: str,
    fetch_size: int = 500
) -> Tuple[int, List[dict]]:
    """查询 FAST 日志。

    Args:
        keyword: 关键词
        start: 开始时间
        end: 结束时间
        index: ES 索引模式
        fast_domain: FAST API 地址
        fetch_size: 返回条数

    Returns:
        (总命中数, hits 列表)

    Raises:
        ValueError: 网络或 API 错误
    """
    payload = build_query_payload(keyword, start, end, index, fetch_size)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                fast_domain,
                json=payload,
                headers=FAST_HEADERS,
            )

            # HTTP 状态码错误
            if response.status_code == 404:
                raise ValueError(f"FAST 索引不存在或已过期：{index}")
            elif response.status_code == 403:
                raise ValueError("FAST 服务访问被拒绝，请检查权限配置")
            elif response.status_code >= 500:
                raise ValueError(f"FAST 服务内部错误 (HTTP {response.status_code})，请稍后重试")

            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        raise ValueError("FAST 服务请求超时（30秒），请稍后重试或缩小查询范围")
    except httpx.ConnectError:
        raise ValueError(f"无法连接 FAST 服务：{fast_domain}。请确认：\n1. 是否在公司内网\n2. 网络连接是否正常")
    except json.JSONDecodeError:
        raise ValueError("FAST 服务返回了无效的 JSON 响应，请稍后重试")

    # 解析响应
    raw_hits = data.get("rawResponse", {}).get("hits", {})
    total_info = raw_hits.get("total", {})
    total_count = total_info.get("value", 0) if isinstance(total_info, dict) else int(total_info or 0)
    hits = raw_hits.get("hits", [])

    return total_count, hits
