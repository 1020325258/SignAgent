# -*- coding: utf-8 -*-
"""SRE 生产环境数据查询工具。"""
import logging
from typing import Any

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


@tool(
    "sre_query",
    """查询 SRE 生产环境数据，用于排查线上问题。
支持查询：合同信息、合同节点、签约人、扩展字段、签约单据、配置快照、城市公司配置、操作日志、字段配置、协议配置、维度组合。
还支持解密身份证号、手机号等敏感信息。""",
    {
        "action": str,
        "contract_code": str,       # 可选，合同编号
        "project_order_id": str,    # 可选，订单号
        "encrypted_text": str,      # 可选，需要解密的密文
        "business_type": int,       # 可选，业务类型
        "gb_code": int,             # 可选，城市code
        "company_code": str,        # 可选，分公司code
        "version": int,             # 可选，版本号
        "contract_type": int,       # 可选，合同类型
        "form_id": int,             # 可选，版式ID
        "page_num": int,            # 可选，页码
        "page_size": int,           # 可选，每页大小
    },
)
async def sre_query(args: dict[str, Any]) -> dict[str, Any]:
    """查询 SRE 生产环境数据。

    Args:
        args: 查询参数

    Returns:
        查询结果
    """
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
            "content": [{"type": "text", "text": f"未知的操作类型: {action}"}],
            "is_error": True,
        }

    # 构建查询参数
    params = {"app": "sreAgent"}

    if action == "decrypt":
        encrypted_text = args.get("encrypted_text", "")
        if not encrypted_text:
            return {
                "content": [{"type": "text", "text": "decrypt 操作需要 encrypted_text 参数"}],
                "is_error": True,
            }
        params["text"] = encrypted_text

    elif action == "contract":
        contract_code = args.get("contract_code", "")
        project_order_id = args.get("project_order_id", "")
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
        contract_code = args.get("contract_code", "")
        if not contract_code:
            return {
                "content": [{"type": "text", "text": f"{action} 操作需要 contract_code 参数"}],
                "is_error": True,
            }
        params["contractCode"] = contract_code

    elif action == "config_snap":
        project_order_id = args.get("project_order_id", "")
        if not project_order_id:
            return {
                "content": [{"type": "text", "text": "config_snap 操作需要 project_order_id 参数"}],
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
