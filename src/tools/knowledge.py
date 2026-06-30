# -*- coding: utf-8 -*-
"""知识库查询工具 - 查询 Ke-RAG 知识库。"""
import os
import logging
from typing import Any

import httpx
from claude_agent_sdk import tool

from config import get_knowledge_config

logger = logging.getLogger(__name__)

# 加载配置
_config = get_knowledge_config()
KE_RAG_BASE_URL = _config.get("base_url", "https://openapi-ait.ke.com/v1")
KE_RAG_API_KEY = os.getenv("KE_RAG_API_KEY", "")
KE_RAG_SPACE_ID = _config.get("space_id", "be5fb25a-7ce8-4268-a7ac-cc90010bf976")
KE_RAG_SPACE_TYPE = _config.get("space_type", "space")
KE_RAG_USER_ID = _config.get("user_id", "1000000030973949")
KE_RAG_MODE = _config.get("mode", "normal")
KE_RAG_LIMIT = _config.get("limit", 20)


@tool(
    "knowledge_search",
    """搜索知识库获取相关信息。
回答任何问题前，必须先调用此工具检索知识库，禁止凭记忆回答。
调用此工具后，必须在回答中引用来源。
引用格式必须严格为：[文件名||文件ID]
例如：根据知识库信息 [退款政策.md||file-001] 的说明...""",
    {
        "query": str,
    },
)
async def knowledge_search(args: dict[str, Any]) -> dict[str, Any]:
    """搜索知识库。

    Args:
        args: 包含 query（搜索关键词）

    Returns:
        搜索结果
    """
    query = args.get("query", "")

    if not query:
        return {
            "content": [{"type": "text", "text": "错误：缺少搜索关键词"}],
            "is_error": True,
        }

    # 使用固定的配置（与 milo-v2 一致）
    request_body = {
        "query": query,
        "scope": [{"type": KE_RAG_SPACE_TYPE, "ids": [KE_RAG_SPACE_ID]}],
        "limit": KE_RAG_LIMIT,
        "user": KE_RAG_USER_ID,
        "mode": KE_RAG_MODE,
    }

    logger.info("Knowledge search: query=%s, space_id=%s", query, KE_RAG_SPACE_ID)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{KE_RAG_BASE_URL}/rag/search",
                json=request_body,
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
                    "content": [{"type": "text", "text": "知识库中未找到相关信息。请告知用户：抱歉，知识库中未找到与您问题相关的信息，无法提供准确回答。"}],
                }

            # 格式化结果（与 milo-v2 一致）
            lines = [f"找到 {len(docs)} 条相关知识：\n"]

            for i, doc in enumerate(docs[:KE_RAG_LIMIT], 1):
                annotation = doc.get("annotation", {})
                file_name = annotation.get("file_name", "未知来源")
                file_id = annotation.get("file_id", "")
                content = doc.get("text", "")

                # 包含 file_id 用于引用
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
