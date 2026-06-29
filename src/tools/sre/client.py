# -*- coding: utf-8 -*-
"""HTTP 客户端模块。"""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


async def call_api(url: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """调用 API。

    Args:
        url: API URL
        method: HTTP 方法（GET 或 POST）
        params: 请求参数

    Returns:
        API 响应数据

    Raises:
        httpx.TimeoutException: 请求超时
        httpx.HTTPStatusError: HTTP 错误
    """
    async with httpx.AsyncClient(timeout=30) as client:
        if method.upper() == "GET":
            response = await client.get(url, params=params)
        elif method.upper() == "POST":
            response = await client.post(url, json=params)
        else:
            raise ValueError(f"不支持的 HTTP 方法: {method}")

        response.raise_for_status()
        return response.json()
