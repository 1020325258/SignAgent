# -*- coding: utf-8 -*-
"""SRE 查询工具定义。"""

import logging
from typing import Any, Optional

from claude_agent_sdk import tool

from .config import get_api_config, get_available_actions
from .handlers import handle_request
from .formatters import format_result, format_user_info

logger = logging.getLogger(__name__)


@tool(
    "sre_query",
    """查询系统数据，用于排查线上问题。

支持的 action 类型：
- contract: 查询合同信息（需要 contract_code 或 project_order_id）
- contract_node: 查询合同节点（需要 contract_code）
- contract_user: 查询签约人（需要 contract_code）
- contract_field: 查询合同扩展字段（需要 contract_code）
- contract_quotation: 查询签约单据（需要 contract_code）
- contract_log: 查询操作日志（需要 contract_code）
- config_snap: 查询配置快照（需要 project_order_id）
- decrypt: 解密敏感信息（需要 encrypted_text）
- city_company_info: 查询城市公司配置（需要 business_type, gb_code, company_code, version, contract_type）
- field_config: 查询字段配置（需要 business_type, gb_code, company_code, contract_type, version）
- protocol_config: 查询协议配置（需要 form_id）
- dim_combos: 查询维度组合
- user-phone-query: 根据手机号查询用户ID（需要 phone）

参数格式：
- contract_code: 合同编号，以 "C" 开头 + 数字，如 C1776759658764987
- project_order_id: 订单号，18位纯数字，如 826041310000003912
- phone: 手机号，11位数字，如 15524175708""",
    {
        "action": str,
        "contract_code": Optional[str],
        "project_order_id": Optional[str],
        "encrypted_text": Optional[str],
        "phone": Optional[str],
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
    """查询系统数据。"""
    action = args.get("action", "")

    if not action:
        return {
            "content": [{"type": "text", "text": "错误：缺少 action 参数"}],
            "is_error": True,
        }

    try:
        # 处理请求
        data = await handle_request(action, args)

        # 格式化结果
        api_config = get_api_config(action)
        if api_config and api_config.get("response", {}).get("format") == "user_info":
            # 用户查询接口特殊处理
            formatted = format_user_info(data if isinstance(data, list) else [data])
        else:
            formatted = format_result(action, data)

        return {
            "content": [{"type": "text", "text": formatted}],
        }

    except ValueError as e:
        return {
            "content": [{"type": "text", "text": str(e)}],
            "is_error": True,
        }
    except Exception as e:
        logger.exception("SRE query failed")
        return {
            "content": [{"type": "text", "text": f"查询异常: {str(e)}"}],
            "is_error": True,
        }
