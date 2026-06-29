# -*- coding: utf-8 -*-
"""请求处理模块。"""

import logging
from typing import Any, Dict, Optional

from .config import get_api_config, get_available_actions
from .client import call_api

logger = logging.getLogger(__name__)


def build_params(action: str, args: Dict[str, Any], api_config: Dict[str, Any]) -> Dict[str, Any]:
    """构建请求参数。

    Args:
        action: 操作类型
        args: 用户输入参数
        api_config: API 配置

    Returns:
        构建好的请求参数
    """
    params = {}

    # 添加认证参数
    auth = api_config.get("auth")
    if auth:
        params.update(auth)

    # 添加默认参数
    default_params = api_config.get("default_params", {})
    params.update(default_params)

    # 添加用户参数
    param_config = api_config.get("parameters", {})
    for param_name, param_def in param_config.items():
        value = args.get(param_name)
        if value is not None:
            api_key = param_def.get("api_key", param_name)
            params[api_key] = value

    return params


def validate_params(action: str, args: Dict[str, Any], api_config: Dict[str, Any]) -> Optional[str]:
    """验证参数。

    Args:
        action: 操作类型
        args: 用户输入参数
        api_config: API 配置

    Returns:
        错误信息，验证通过返回 None
    """
    param_config = api_config.get("parameters", {})
    required_any = api_config.get("required_any", [])

    # 检查必填参数
    for param_name, param_def in param_config.items():
        if param_def.get("required"):
            if not args.get(param_name):
                desc = param_def.get("description", param_name)
                return f"{action} 操作需要 {param_name} 参数（{desc}）"

    # 检查至少需要一个的参数
    if required_any:
        if not any(args.get(p) for p in required_any):
            param_descs = []
            for p in required_any:
                desc = param_config.get(p, {}).get("description", p)
                param_descs.append(f"{p}（{desc}）")
            return f"{action} 操作需要以下参数之一: {', '.join(param_descs)}"

    return None


async def handle_request(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """处理请求。

    Args:
        action: 操作类型
        args: 用户输入参数

    Returns:
        API 响应数据

    Raises:
        ValueError: 参数验证失败或未知的 action
    """
    # 获取 API 配置
    api_config = get_api_config(action)
    if not api_config:
        available = get_available_actions()
        raise ValueError(f"未知的操作类型: {action}。支持的类型：{', '.join(available)}")

    # 验证参数
    error = validate_params(action, args, api_config)
    if error:
        raise ValueError(error)

    # 构建参数
    params = build_params(action, args, api_config)

    # 调用 API
    url = f"{api_config['base_url']}{api_config['endpoint']}"
    method = api_config.get("method", "GET")

    logger.info("SRE query: action=%s, url=%s, params=%s", action, url, params)

    data = await call_api(url, method, params)

    return data
