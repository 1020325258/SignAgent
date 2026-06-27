# -*- coding: utf-8 -*-
"""SRE 生产环境数据查询工具。"""
import logging
from typing import Any, Optional

import httpx
from claude_agent_sdk import tool

logger = logging.getLogger(__name__)

# SRE 服务配置
SRE_BASE_URL = "http://preview.i.nrs-sales-project.home.ke.com"

# action 到 API endpoint 的映射
ENDPOINT_MAP = {
    "decrypt": "/sre/decrypt",
    "contract": "/sre/contract",
    "contract_node": "/sre/contract-node",
    "contract_user": "/sre/contract-user",
    "contract_field": "/sre/contract-field",
    "contract_quotation": "/sre/contract-quotation-relation",
    "config_snap": "/sre/project-config-snap",
    "city_company_info": "/sre/contract-city-company-info",
    "contract_log": "/sre/contract-log",
    "field_config": "/sre/field-config",
    "protocol_config": "/sre/protocol-config",
    "dim_combos": "/sre/field-config-dim-combos",
}


def clean_params(params: dict) -> dict:
    """清理参数，移除 None 和空字符串。"""
    return {k: v for k, v in params.items() if v is not None and v != ""}


@tool(
    "sre_query",
    """查询 SRE 生产环境数据，用于排查线上问题。

支持的 action 类型：
- contract: 查询合同信息（需要 contract_code 或 project_order_id）
- contract_node: 查询合同节点（需要 contract_code）
- contract_user: 查询签约人（需要 contract_code）
- contract_field: 查询合同扩展字段（需要 contract_code）
- contract_log: 查询操作日志（需要 contract_code）
- config_snap: 查询配置快照（需要 project_order_id）
- decrypt: 解密敏感信息（需要 encrypted_text）
- field_config: 查询字段配置（需要 business_type, gb_code, company_code, contract_type, version）

参数格式：
- contract_code: 合同编号，以 "C" 开头 + 数字，如 C1776759658764987
- project_order_id: 订单号，18位纯数字，如 826041310000003912""",
    {
        "action": str,
        "contract_code": Optional[str],
        "project_order_id": Optional[str],
        "encrypted_text": Optional[str],
        "business_type": Optional[int],
        "gb_code": Optional[int],
        "company_code": Optional[str],
        "version": Optional[int],
        "contract_type": Optional[int],
        "form_id": Optional[int],
        "page_num": Optional[int],
        "page_size": Optional[int],
    },
)
async def sre_query(args: dict[str, Any]) -> dict[str, Any]:
    """查询 SRE 生产环境数据。"""
    action = args.get("action", "")
    if not action:
        return {
            "content": [{"type": "text", "text": "错误：缺少 action 参数"}],
            "is_error": True,
        }

    # 获取 endpoint
    endpoint = ENDPOINT_MAP.get(action)
    if not endpoint:
        return {
            "content": [{"type": "text", "text": f"未知的操作类型: {action}。支持的类型：{', '.join(ENDPOINT_MAP.keys())}"}],
            "is_error": True,
        }

    # 构建查询参数
    params = {"app": "sreAgent"}

    # 提取常用参数
    contract_code = args.get("contract_code", "")
    project_order_id = args.get("project_order_id", "")

    if action == "decrypt":
        encrypted_text = args.get("encrypted_text", "")
        if not encrypted_text:
            return {
                "content": [{"type": "text", "text": "decrypt 操作需要 encrypted_text 参数"}],
                "is_error": True,
            }
        params["text"] = encrypted_text

    elif action == "contract":
        if not contract_code and not project_order_id:
            return {
                "content": [{"type": "text", "text": "contract 操作需要 contract_code 或 project_order_id 参数"}],
                "is_error": True,
            }
        if contract_code:
            params["contractCode"] = contract_code
        if project_order_id:
            params["projectOrderId"] = project_order_id

    elif action in ("contract_node", "contract_user", "contract_field", "contract_quotation", "contract_log"):
        if not contract_code:
            return {
                "content": [{"type": "text", "text": f"{action} 操作需要 contract_code 参数（以C开头的合同编号）"}],
                "is_error": True,
            }
        params["contractCode"] = contract_code
        if action == "contract_log" and args.get("log_type") is not None:
            params["type"] = args["log_type"]

    elif action == "config_snap":
        if not project_order_id:
            return {
                "content": [{"type": "text", "text": "config_snap 操作需要 project_order_id 参数（18位订单号）"}],
                "is_error": True,
            }
        params["projectOrderId"] = project_order_id

    elif action == "city_company_info":
        required = ["business_type", "gb_code", "company_code", "version", "contract_type"]
        missing = [f for f in required if args.get(f) is None]
        if missing:
            return {
                "content": [{"type": "text", "text": f"city_company_info 操作需要以下参数: {', '.join(missing)}"}],
                "is_error": True,
            }
        params["businessType"] = args["business_type"]
        params["gbCode"] = args["gb_code"]
        params["companyCode"] = args["company_code"]
        params["version"] = args["version"]
        params["type"] = args["contract_type"]

    elif action == "field_config":
        required = ["business_type", "gb_code", "company_code", "contract_type", "version"]
        missing = [f for f in required if args.get(f) is None]
        if missing:
            return {
                "content": [{"type": "text", "text": f"field_config 操作需要以下参数: {', '.join(missing)}"}],
                "is_error": True,
            }
        params["businessType"] = args["business_type"]
        params["gbcode"] = args["gb_code"]
        params["companyCode"] = args["company_code"]
        params["contractType"] = args["contract_type"]
        params["version"] = args["version"]
        if args.get("page_num") is not None:
            params["pageNum"] = args["page_num"]
        if args.get("page_size") is not None:
            params["pageSize"] = args["page_size"]

    elif action == "protocol_config":
        form_id = args.get("form_id")
        if form_id is None:
            return {
                "content": [{"type": "text", "text": "protocol_config 操作需要 form_id 参数"}],
                "is_error": True,
            }
        params["formId"] = form_id

    # 清理参数
    params = clean_params(params)

    # 执行查询
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{SRE_BASE_URL}{endpoint}"
            logger.info("SRE query: action=%s, url=%s, params=%s", action, url, params)

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # 检查响应
            if not data.get("success"):
                message = data.get("message", "查询失败")
                return {
                    "content": [{"type": "text", "text": f"查询失败: {message}"}],
                    "is_error": True,
                }

            result_data = data.get("data")
            if result_data is None:
                return {
                    "content": [{"type": "text", "text": "查询结果为空"}],
                }

            # 格式化结果
            formatted = format_sre_result(action, result_data)
            return {
                "content": [{"type": "text", "text": formatted}],
            }

    except httpx.TimeoutException:
        return {
            "content": [{"type": "text", "text": "查询超时，请稍后重试"}],
            "is_error": True,
        }
    except Exception as e:
        logger.exception("SRE query failed")
        return {
            "content": [{"type": "text", "text": f"查询异常: {str(e)}"}],
            "is_error": True,
        }


def format_sre_result(action: str, data: Any) -> str:
    """格式化 SRE 查询结果。"""
    if isinstance(data, list):
        if not data:
            return "查询结果为空"

        # 列表格式化为表格
        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            lines = [f"## 查询结果 ({len(data)} 条)\n"]
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("| " + " | ".join(["---"] * len(keys)) + " |")

            for item in data:
                values = [str(item.get(k, ""))[:100] for k in keys]
                lines.append("| " + " | ".join(values) + " |")

            return "\n".join(lines)
        else:
            return f"## 查询结果\n\n" + "\n".join(f"- {item}" for item in data)

    elif isinstance(data, dict):
        # 对象格式化为表格
        lines = ["## 查询结果\n"]
        lines.append("| 字段 | 值 |")
        lines.append("|------|-----|")

        for key, value in data.items():
            str_value = str(value)
            if len(str_value) > 200:
                str_value = str_value[:200] + "..."
            lines.append(f"| {key} | {str_value} |")

        return "\n".join(lines)

    else:
        return f"## 查询结果\n\n```json\n{data}\n```"
