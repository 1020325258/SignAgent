# -*- coding: utf-8 -*-
"""SRE 生产环境数据查询工具。"""
import logging
from typing import Any, Optional, Dict, Tuple

import httpx
from claude_agent_sdk import tool

from config import get_sre_config
from .enums import ENUM_REGISTRY

logger = logging.getLogger(__name__)

# 加载配置
_config = get_sre_config()
SRE_BASE_URL = _config.get("base_url", "http://preview.i.nrs-sales-project.home.ke.com")

# action 到 API 配置的映射
# 格式: {"base_url": "...", "endpoint": "..."}
API_CONFIGS = {
    # SRE 后端接口
    "decrypt": {"base_url": SRE_BASE_URL, "endpoint": "/sre/decrypt"},
    "contract": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract"},
    "contract_node": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-node"},
    "contract_user": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-user"},
    "contract_field": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-field"},
    "contract_quotation": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-quotation-relation"},
    "config_snap": {"base_url": SRE_BASE_URL, "endpoint": "/sre/project-config-snap"},
    "city_company_info": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-city-company-info"},
    "contract_log": {"base_url": SRE_BASE_URL, "endpoint": "/sre/contract-log"},
    "field_config": {"base_url": SRE_BASE_URL, "endpoint": "/sre/field-config"},
    "protocol_config": {"base_url": SRE_BASE_URL, "endpoint": "/sre/protocol-config"},
    "dim_combos": {"base_url": SRE_BASE_URL, "endpoint": "/sre/field-config-dim-combos"},
    # 用户系统接口
    "user-phone-query": {"base_url": "http://i.cms.home.ke.com", "endpoint": "/api/operate/user-phone"},
}

# ── 字段含义映射 ──────────────────────────────────────────────
# key = "action.field" 或 "field"（通用兜底）
# value = (中文含义, 枚举类型名或None)
FIELD_MEANINGS: Dict[str, Tuple[str, Optional[str]]] = {
    # ── 通用字段 ──
    "contractCode": ("合同编号", None),
    "delStatus": ("删除标记", None),
    "ctime": ("创建时间", None),
    "mtime": ("更新时间", None),
    # ── contract ──
    "contract.contractNo": ("合同编号", None),
    "contract.businessType": ("业务类型", "BusinessTypeEnum"),
    "contract.projectOrderId": ("订单号", None),
    "contract.type": ("合同类型", "ContractTypeEnum"),
    "contract.status": ("合同状态", "ContractStatusEnum"),
    "contract.pdfGenerationMode": ("PDF生成模式", "PdfGenerationModeEnum"),
    "contract.userQueryStatus": ("用户可见性", None),
    "contract.userConfirmStatus": ("用户确认状态", None),
    "contract.userSignStatus": ("用户签署状态", None),
    "contract.signChannelType": ("签署方式", "SignChannelTypeEnum"),
    "contract.userSignType": ("用户签署方式", "UserSignTypeEnum"),
    "contract.auditType": ("审核类型", "AuditTypeEnum"),
    "contract.amount": ("合同金额", None),
    "contract.relateContractCode": ("关联合同编号", None),
    "contract.platformInstanceId": ("协议平台实例ID", None),
    "contract.errorMessage": ("发起失败信息", None),
    # ── contract_user ──
    "contract_user.roleType": ("用户角色", "RoleTypeEnum"),
    "contract_user.name": ("姓名", None),
    "contract_user.phone": ("手机号(加密)", None),
    "contract_user.isSign": ("是否为签约人", "IsSignEnum"),
    "contract_user.isAuth": ("是否已认证", None),
    "contract_user.certificateType": ("证件类型", "CertificateTypeEnum"),
    "contract_user.certificateNo": ("证件号码(加密)", None),
    # ── contract_node ──
    "contract_node.nodeType": ("节点类型", "NodeTypeEnum"),
    "contract_node.fireTime": ("发生时间戳", None),
    # ── contract_log ──
    "contract_log.type": ("操作类型", "LogTypeEnum"),
    "contract_log.content": ("日志内容", None),
    "contract_log.remark": ("备注", None),
    # ── contract_field ──
    "contract_field.fieldKey": ("字段名称", None),
    "contract_field.fieldValue": ("字段值", None),
    # ── contract_quotation ──
    "contract_quotation.billCode": ("关联单据编号", None),
    "contract_quotation.bindType": ("绑定类型", "BindTypeEnum"),
    "contract_quotation.status": ("关联状态", None),
    # ── city_company_info ──
    "city_company_info.businessType": ("业务类型", "BusinessTypeEnum"),
    "city_company_info.contractType": ("合同类型", "ContractTypeEnum"),
    "city_company_info.signChannelType": ("签署方式", "SignChannelTypeEnum"),
    "city_company_info.auditType": ("审核类型", "AuditTypeEnum"),
    "city_company_info.processMode": ("流程模式", None),
    "city_company_info.formId": ("版式ID", None),
    "city_company_info.version": ("版本号", None),
    # ── field_config ──
    "field_config.businessType": ("业务类型", "BusinessTypeEnum"),
    "field_config.gbcode": ("城市code", None),
    "field_config.companyCode": ("分公司code", None),
    "field_config.contractType": ("合同类型", "ContractTypeEnum"),
    "field_config.version": ("版本号", None),
    "field_config.moduleKey": ("字段所属模块", None),
    "field_config.fieldKey": ("字段key", None),
    "field_config.fieldName": ("字段名称", None),
    "field_config.description": ("字段描述", None),
    "field_config.required": ("是否必填", None),
    "field_config.disabled": ("是否只读", None),
}


def get_meaning(action: str, field_name: str) -> Optional[Tuple[str, Optional[str]]]:
    """查询字段含义，返回 (含义, 枚举类型名) 或 None。

    优先匹配 "action.field"，未命中则匹配 "field"（通用兜底）。
    """
    return (
        FIELD_MEANINGS.get(f"{action}.{field_name}")
        or FIELD_MEANINGS.get(field_name)
    )


def translate_enum(enum_name: str, value: Any) -> str:
    """翻译枚举值，返回 '值=含义' 格式。

    Args:
        enum_name: 枚举类型名，如 "ContractTypeEnum"。
        value: 枚举值。

    Returns:
        翻译后的字符串，如 "6=整装首期款合同"。
        如果无法翻译，返回原值字符串。
    """
    if not enum_name or value is None:
        return str(value)

    mapping = ENUM_REGISTRY.get(enum_name)
    if mapping:
        # 尝试 int 转换（大部分枚举是 int 类型）
        try:
            int_value = int(value)
            translated = mapping.get(int_value)
            if translated:
                return f"{int_value}={translated}"
        except (ValueError, TypeError):
            # 非数字类型的枚举
            translated = mapping.get(str(value))
            if translated:
                return f"{value}={translated}"

    return str(value)


def clean_params(params: dict) -> dict:
    """清理参数，移除 None 和空字符串。"""
    return {k: v for k, v in params.items() if v is not None and v != ""}


@tool(
    "sre_query",
    """查询系统数据，用于排查线上问题。

支持的 action 类型：
- contract: 查询合同信息（需要 contract_code 或 project_order_id）
- contract_node: 查询合同节点（需要 contract_code）
- contract_user: 查询签约人（需要 contract_code）
- contract_field: 查询合同扩展字段（需要 contract_code）
- contract_log: 查询操作日志（需要 contract_code）
- config_snap: 查询配置快照（需要 project_order_id）
- decrypt: 解密敏感信息（需要 encrypted_text）
- field_config: 查询字段配置（需要 business_type, gb_code, company_code, contract_type, version）
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

    # 获取 API 配置
    api_config = API_CONFIGS.get(action)
    if not api_config:
        return {
            "content": [{"type": "text", "text": f"未知的操作类型: {action}。支持的类型：{', '.join(API_CONFIGS.keys())}"}],
            "is_error": True,
        }

    # 构建查询参数
    params = {}
    # SRE 接口需要 app 参数
    if api_config["base_url"] == SRE_BASE_URL:
        params["app"] = "sreAgent"

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

    elif action == "user-phone-query":
        phone = args.get("phone", "")
        if not phone:
            return {
                "content": [{"type": "text", "text": "user-phone-query 操作需要 phone 参数（手机号）"}],
                "is_error": True,
            }
        params["bizId"] = phone
        params["pageSize"] = 50
        params["currentPage"] = 1

    # 清理参数
    params = clean_params(params)

    # 执行查询
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{api_config['base_url']}{api_config['endpoint']}"
            logger.info("SRE query: action=%s, url=%s, params=%s", action, url, params)

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # 根据不同的 action 处理响应
            if action == "user-phone-query":
                # 用户查询接口的响应格式
                result_data = data.get("data", {})
                user_list = result_data.get("list", [])
                if not user_list:
                    return {
                        "content": [{"type": "text", "text": f"未找到手机号 {args.get('phone')} 对应的用户"}],
                    }
                user = user_list[0]
                formatted = f"## 查询结果\n\n- **用户ID**: {user.get('userId', '未知')}\n- **用户名**: {user.get('userName', '未知')}\n- **手机号**: {user.get('phone', '未知')}"
                return {
                    "content": [{"type": "text", "text": formatted}],
                }
            else:
                # SRE 接口的响应格式
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
    """格式化 SRE 查询结果（带枚举值翻译）。"""
    if isinstance(data, list):
        if not data:
            return "查询结果为空"

        # 列表格式化为表格
        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            lines = [f"## 查询结果 ({len(data)} 条)\n"]

            # 表头
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("| " + " | ".join(["---"] * len(keys)) + " |")

            # 含义行
            meanings = []
            for key in keys:
                meaning = get_meaning(action, key)
                if meaning:
                    desc, _ = meaning
                    meanings.append(desc)
                else:
                    meanings.append("")
            lines.append("| " + " | ".join(meanings) + " |")

            # 数据行
            for item in data:
                values = []
                for key in keys:
                    meaning = get_meaning(action, key)
                    if meaning:
                        _, enum_name = meaning
                        # 自动翻译枚举值
                        str_value = translate_enum(enum_name, item.get(key)) if enum_name else str(item.get(key, ""))
                    else:
                        str_value = str(item.get(key, ""))

                    if len(str_value) > 100:
                        str_value = str_value[:100] + "..."
                    values.append(str_value)
                lines.append("| " + " | ".join(values) + " |")

            return "\n".join(lines)
        else:
            return f"## 查询结果\n\n" + "\n".join(f"- {item}" for item in data)

    elif isinstance(data, dict):
        # 对象格式化为表格
        lines = ["## 查询结果\n"]
        lines.append("| 字段 | 值 | 含义 |")
        lines.append("|------|-----|------|")

        for key, value in data.items():
            meaning = get_meaning(action, key)
            if meaning:
                desc, enum_name = meaning
                # 自动翻译枚举值
                str_value = translate_enum(enum_name, value) if enum_name else str(value)
                col3 = desc
            else:
                str_value = str(value)
                col3 = "-"

            if len(str_value) > 200:
                str_value = str_value[:200] + "..."
            lines.append(f"| {key} | {str_value} | {col3} |")

        return "\n".join(lines)

    else:
        return f"## 查询结果\n\n```json\n{data}\n```"
