# -*- coding: utf-8 -*-
"""Apollo 配置查询工具。"""
import os
import logging
from typing import Any, Optional

import httpx
from claude_agent_sdk import tool

from config import get_apollo_config

logger = logging.getLogger(__name__)

# 加载配置
_config = get_apollo_config()
APOLLO_BASE_URL = _config.get("base_url", "http://apollo.portal.life.ke.com")
APOLLO_TOKEN = _config.get("token", "")
APOLLO_ENV = _config.get("env", "PROD")
APOLLO_APP_ID = _config.get("app_id", "utopia-nrs-sales-project")
APOLLO_CLUSTER = _config.get("cluster", "default")
APOLLO_DEFAULT_NAMESPACE = _config.get("default_namespace", "application")


async def apollo_get(url: str) -> Any:
    """发送 GET 请求到 Apollo。"""
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    if APOLLO_TOKEN:
        headers["Authorization"] = APOLLO_TOKEN

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 404:
                return None
            if response.status_code == 401:
                logger.warning("Apollo authentication failed")
                return None
            if response.status_code == 403:
                logger.warning("Apollo access denied")
                return None
            if response.status_code != 200:
                logger.warning("Apollo API error: status=%d, url=%s", response.status_code, url)
                return None

            return response.json()
    except Exception as e:
        logger.error("Apollo request failed: %s", e)
        return None


async def apollo_get_item(namespace: str, key: str) -> Optional[dict]:
    """查询单个配置项。"""
    url = f"{APOLLO_BASE_URL}/openapi/v1/envs/{APOLLO_ENV}/apps/{APOLLO_APP_ID}/clusters/{APOLLO_CLUSTER}/namespaces/{namespace}/items/{key}"
    return await apollo_get(url)


async def apollo_list_items(namespace: str) -> Optional[list]:
    """列出 namespace 下所有配置项（自动分页）。"""
    all_items = []
    page = 0
    page_size = 100

    while True:
        url = f"{APOLLO_BASE_URL}/openapi/v1/envs/{APOLLO_ENV}/apps/{APOLLO_APP_ID}/clusters/{APOLLO_CLUSTER}/namespaces/{namespace}/items?page={page}&size={page_size}"
        data = await apollo_get(url)

        if data is None:
            return None if page == 0 else all_items

        if isinstance(data, dict) and "content" in data:
            items = data["content"]
            all_items.extend(items)
            total = data.get("total", 0)
            if len(all_items) >= total or len(items) < page_size:
                break
            page += 1
        elif isinstance(data, list):
            return data
        else:
            return None

    return all_items


async def apollo_get_latest_release(namespace: str) -> Optional[dict]:
    """查询 namespace 最新 release 信息。"""
    url = f"{APOLLO_BASE_URL}/openapi/v1/envs/{APOLLO_ENV}/apps/{APOLLO_APP_ID}/clusters/{APOLLO_CLUSTER}/namespaces/{namespace}/releases/latest"
    return await apollo_get(url)


@tool(
    "apollo_query",
    """查询 Apollo 配置中心的配置数据。
支持按 key 精确查询、列出全部配置、模糊搜索 key、查看 release 信息。

支持的 action 类型：
- get: 根据 key 查询单个配置值（需要 key 参数）
- list: 列出 namespace 下所有配置
- search: 按关键字模糊搜索配置 key（需要 key 参数作为搜索关键字）
- release: 查询最新 release 信息

【重要】配置可能分布在不同 namespace 中，常见 namespace 包括：
- application（默认）
- contract
- bootstrap
如果在默认 namespace 中找不到配置，请尝试其他 namespace。

【关键】Apollo 配置的 key 都是英文格式，如 'attach.config.ocrOpenCity'、'contract.trade.enabled' 等。
不要使用中文作为 key 搜索。""",
    {
        "action": str,
        "namespace": str,
        "key": str,
    },
)
async def apollo_query(args: dict[str, Any]) -> dict[str, Any]:
    """查询 Apollo 配置。"""
    action = args.get("action", "")
    if not action:
        return {
            "content": [{"type": "text", "text": "错误：缺少 action 参数"}],
            "is_error": True,
        }

    # namespace 默认为 application
    namespace = args.get("namespace", "") or APOLLO_DEFAULT_NAMESPACE
    key = args.get("key", "")

    logger.info("Apollo query: action=%s, namespace=%s, key=%s", action, namespace, key)

    try:
        if action == "get":
            return await _get_item(namespace, key)
        elif action == "list":
            return await _list_items(namespace)
        elif action == "search":
            return await _search_items(namespace, key)
        elif action == "release":
            return await _get_release(namespace)
        else:
            return {
                "content": [{"type": "text", "text": f"未知操作: {action}，支持 get/list/search/release"}],
                "is_error": True,
            }
    except Exception as e:
        logger.exception("Apollo query failed")
        return {
            "content": [{"type": "text", "text": f"Apollo 查询异常: {str(e)}"}],
            "is_error": True,
        }


async def _get_item(namespace: str, key: str) -> dict:
    """查询单个配置项。"""
    if not key:
        return {
            "content": [{"type": "text", "text": "get 操作需要传入 key 参数"}],
            "is_error": True,
        }

    data = await apollo_get_item(namespace, key)
    if data is None:
        suggestion = ""
        if namespace == "application":
            suggestion = "\n\n【建议】该配置可能在其他 namespace 中，请尝试：\n- namespace='contract'\n- namespace='bootstrap'"
        return {
            "content": [{"type": "text", "text": f"在 namespace='{namespace}' 中未找到配置项: {key}{suggestion}"}],
            "is_error": True,
        }

    value = data.get("value", "")
    result = (
        f"## Apollo 配置查询结果\n\n"
        f"| 字段 | 值 |\n"
        f"|------|----|\n"
        f"| 环境 | {APOLLO_ENV} |\n"
        f"| appId | {APOLLO_APP_ID} |\n"
        f"| namespace | {namespace} |\n"
        f"| key | {key} |\n"
        f"| value | {value} |\n"
    )
    return {"content": [{"type": "text", "text": result}]}


async def _list_items(namespace: str) -> dict:
    """列出 namespace 下所有配置项。"""
    data = await apollo_list_items(namespace)
    if data is None:
        return {
            "content": [{"type": "text", "text": f"无法获取 namespace={namespace} 的配置列表"}],
            "is_error": True,
        }

    if not data:
        return {
            "content": [{"type": "text", "text": f"namespace={namespace} 下没有配置项"}],
        }

    lines = [
        f"## Apollo 配置列表\n\n"
        f"**环境**: {APOLLO_ENV} | **appId**: {APOLLO_APP_ID} | **namespace**: {namespace}\n\n"
        f"共 {len(data)} 个配置项：\n\n"
        f"| # | key | value (前100字符) |\n"
        f"|---|-----|--------------------|\n",
    ]
    for i, item in enumerate(data, 1):
        k = item.get("key", "")
        v = item.get("value", "")
        if len(v) > 100:
            v = v[:100] + "..."
        lines.append(f"| {i} | `{k}` | {v} |\n")

    return {"content": [{"type": "text", "text": "".join(lines)}]}


async def _search_items(namespace: str, keyword: str) -> dict:
    """按关键字模糊搜索配置 key。"""
    if not keyword:
        return {
            "content": [{"type": "text", "text": "search 操作需要传入 key 参数作为搜索关键字"}],
            "is_error": True,
        }

    data = await apollo_list_items(namespace)
    if data is None:
        return {
            "content": [{"type": "text", "text": f"无法获取 namespace={namespace} 的配置列表"}],
            "is_error": True,
        }

    keyword_lower = keyword.lower()
    matched = [
        item for item in data
        if keyword_lower in item.get("key", "").lower()
        or keyword_lower in item.get("value", "").lower()
    ]

    if not matched:
        has_chinese = any('一' <= char <= '鿿' for char in keyword)
        hint = ""
        if has_chinese:
            hint = "\n\n【提示】Apollo 配置的 key 都是英文格式，中文搜索通常无法匹配。请使用英文 key 搜索。"
        return {
            "content": [{"type": "text", "text": f"在 namespace={namespace} 中未找到匹配 '{keyword}' 的配置项{hint}"}],
        }

    lines = [
        f"## Apollo 配置搜索结果\n\n"
        f"**搜索关键字**: `{keyword}` | **匹配数量**: {len(matched)}\n\n"
        f"| # | key | value (前100字符) |\n"
        f"|---|-----|--------------------|\n",
    ]
    for i, item in enumerate(matched, 1):
        k = item.get("key", "")
        v = item.get("value", "")
        if len(v) > 100:
            v = v[:100] + "..."
        lines.append(f"| {i} | `{k}` | {v} |\n")

    return {"content": [{"type": "text", "text": "".join(lines)}]}


async def _get_release(namespace: str) -> dict:
    """查询 namespace 最新 release 信息。"""
    data = await apollo_get_latest_release(namespace)
    if data is None:
        return {
            "content": [{"type": "text", "text": f"无法获取 namespace={namespace} 的 release 信息"}],
            "is_error": True,
        }

    release_time = data.get("releaseTime", "未知")
    comment = data.get("comment", "无")
    configurations = data.get("configurations", [])

    lines = [
        f"## Apollo Release 信息\n\n"
        f"| 字段 | 值 |\n"
        f"|------|----|\n"
        f"| 环境 | {APOLLO_ENV} |\n"
        f"| appId | {APOLLO_APP_ID} |\n"
        f"| namespace | {namespace} |\n"
        f"| 发布时间 | {release_time} |\n"
        f"| 备注 | {comment} |\n"
        f"| 配置项数量 | {len(configurations)} |\n",
    ]

    if configurations:
        lines.append("\n### 配置项详情\n\n")
        lines.append("| key | value (前100字符) |\n")
        lines.append("|-----|--------------------|\n")
        for item in configurations:
            k = item.get("key", "")
            v = item.get("value", "")
            if len(v) > 100:
                v = v[:100] + "..."
            lines.append(f"| `{k}` | {v} |\n")

    return {"content": [{"type": "text", "text": "".join(lines)}]}
