# -*- coding: utf-8 -*-
"""FAST 日志平台 API 客户端 - 使用新的 ES 查询接口。"""

import json
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 固定的请求头
FAST_HEADERS = {
    "api_key": "5dc1a7c244e388912d075ad0c4209b12",
    "X-NRS-User-Id": "1000000000000000",
    "Content-Type": "application/json",
}


def extract_content(hit: dict) -> dict:
    """从日志 hit 中提取关键信息。

    Args:
        hit: 新接口返回的日志对象（直接包含字段，无 _source 包装）

    Returns:
        提取后的字典
    """
    return {
        "segmentId": hit.get("segmentId", ""),
        "traceId": hit.get("traceId", ""),
        "data_info_msg": hit.get("data_info_msg", ""),
        "timestamp": hit.get("timestamp", ""),
        "_index": hit.get("_index", ""),
    }


async def fetch_logs(
    query_string: str,
    stime: int,
    etime: int,
    index: str,
    fields: List[str],
    size: int = 20,
    api_url: str = "https://api.fast.ke.com/es/query",
) -> Dict[str, Any]:
    """查询 FAST 日志。

    Args:
        query_string: ES 查询字符串，例如 '("关键词1" or "关键词2") && "条件"'
        stime: 开始时间戳（毫秒）
        etime: 结束时间戳（毫秒）
        index: ES 索引模式
        fields: 返回字段列表
        size: 返回条数，默认 20
        api_url: API 地址

    Returns:
        包含查询结果的字典:
        - total: 总命中数
        - hits: 日志列表（已提取字段）

    Raises:
        ValueError: 网络或 API 错误
    """
    payload = {
        "index": index,
        "stime": stime,
        "etime": etime,
        "fields": fields,
        "queryString": query_string,
        "size": size,
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            response = await client.post(
                api_url,
                json=payload,
                headers=FAST_HEADERS,
            )

            # HTTP 状态码错误处理
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
        raise ValueError(f"无法连接 FAST 服务：{api_url}。请确认：\n1. 是否在公司内网\n2. 网络连接是否正常")
    except json.JSONDecodeError:
        raise ValueError("FAST 服务返回了无效的 JSON 响应，请稍后重试")

    # 解析响应 - 根据新接口格式
    total = data.get("total", 0)
    hits = data.get("data", [])  # 新接口返回 data 字段

    # 提取每条日志的关键字段
    extracted_hits = [extract_content(hit) for hit in hits]

    return {
        "total": total,
        "hits": extracted_hits,
    }
