# -*- coding: utf-8 -*-
"""SRE 查询工具配置模块。"""

import os
import yaml
from typing import Any, Dict, Optional, Tuple

# 配置文件路径
_CONFIG_DIR = os.path.dirname(__file__)
_APIS_CONFIG_PATH = os.path.join(_CONFIG_DIR, "apis.yaml")
_FIELD_MEANINGS_PATH = os.path.join(_CONFIG_DIR, "field_meanings.yaml")

# 缓存
_apis_cache = None
_meanings_cache = None


def load_apis_config() -> Dict[str, Any]:
    """加载 API 配置。"""
    global _apis_cache
    if _apis_cache is None:
        with open(_APIS_CONFIG_PATH, "r", encoding="utf-8") as f:
            _apis_cache = yaml.safe_load(f)
    return _apis_cache


def get_api_config(action: str) -> Optional[Dict[str, Any]]:
    """获取指定 action 的 API 配置。"""
    config = load_apis_config()
    return config.get("apis", {}).get(action)


def get_available_actions() -> list:
    """获取所有可用的 action 列表。"""
    config = load_apis_config()
    return list(config.get("apis", {}).keys())


def load_field_meanings() -> Dict[str, Tuple[str, Optional[str]]]:
    """加载字段含义配置。"""
    global _meanings_cache
    if _meanings_cache is None:
        with open(_FIELD_MEANINGS_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
            _meanings_cache = {k: tuple(v) for k, v in raw.items()}
    return _meanings_cache


def get_field_meaning(action: str, field_name: str) -> Optional[Tuple[str, Optional[str]]]:
    """查询字段含义。

    优先匹配 "action.field"，未命中则匹配 "field"（通用兜底）。
    """
    meanings = load_field_meanings()
    return (
        meanings.get(f"{action}.{field_name}")
        or meanings.get(field_name)
    )
