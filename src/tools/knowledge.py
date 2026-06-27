# -*- coding: utf-8 -*-
"""知识库查询工具 - 查询 Ke-RAG 知识库。"""
import os
import logging
from typing import Any

import httpx
from claude_agent_sdk import tool

logger = logging.getLogger(__name__)

# Ke-RAG 服务配置
KE_RAG_BASE_URL = "https://openapi-ait.ke.com/v1"
KE_RAG_API_KEY = os.getenv("KE_RAG_API_KEY", "")
DEFAULT_SPACE_ID = os.getenv("KE_RAG_SPACE_ID", "be5fb25a-7ce8-4268-a7ac-cc90010bf976")
DEFAULT_USER_ID = os.getenv("KE_RAG_USER_ID", "1000000030973949")


@tool(
    "knowledge_search",
    "搜索知识库获取相关信息。回答任何问题前，必须先调用此工具检索知识库。",
    {
        "query": str,
        "space_id": str,  # 可选，知识库空间 ID
        "limit": int,     # 可选，返回结果数量
    },
)
async def knowledge_search(args: dict[str, Any]) -> dict[str, Any]:
    """搜索知识库。

    Args:
        args: 包含 query（搜索关键词）、space_id（可选）、limit（可选）

    Returns:
        搜索结果
    """
    query = args.get("query", "")
    space_id = args.get("space_id", DEFAULT_SPACE_ID)
    limit = args.get("limit", 5)

    if not query:
        return {
            "content": [{"type": "text", "text": "错误：缺少搜索关键词"}],
            "is_error": True,
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{KE_RAG_BASE_URL}/rag/search",
                json={
                    "query": query,
                    "scope": [{"type": "file", "ids": [space_id]}],
                    "limit": limit,
                    "mode": "normal",
                    "user": DEFAULT_USER_ID,
                },
                headers={
                    "Authorization": f"Bearer {KE_RAG_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            # 检查 API 响应
            if data.get("code") != 0:
                error_msg = data.get("message", "查询失败")
                return {
                    "content": [{"type": "text", "text": f"知识库查询失败: {error_msg}"}],
                    "is_error": True,
                }

            # 解析结果
            docs = data.get("data", {}).get("docs", [])
            if not docs:
                return {
                    "content": [{"type": "text", "text": "知识库中未找到相关信息。"}],
                }

            # 格式化结果
            lines = [f"找到 {len(docs)} 条相关知识：\n"]
            for i, doc in enumerate(docs[:limit], 1):
                annotation = doc.get("annotation", {})
                file_name = annotation.get("file_name", "未知来源")
                file_id = annotation.get("file_id", "")
                content = doc.get("text", "")

                # 截断过长内容
                if len(content) > 500:
                    content = content[:500] + "..."

                file_ref = f"{file_name}||{file_id}" if file_id else file_name
                lines.append(f"{i}. **{file_name}** | 来源：{file_ref}")
                lines.append(f"   {content}\n")

            return {
                "content": [{"type": "text", "text": "\n".join(lines)}],
            }

    except httpx.TimeoutException:
        return {
            "content": [{"type": "text", "text": "知识库查询超时，请稍后重试"}],
            "is_error": True,
        }
    except Exception as e:
        logger.exception("Knowledge search failed")
        return {
            "content": [{"type": "text", "text": f"知识库查询异常: {str(e)}"}],
            "is_error": True,
        }
