# -*- coding: utf-8 -*-
"""配置模块。"""

import os
import yaml
from typing import Any, Dict


def load_tools_config() -> Dict[str, Any]:
    """加载工具配置。

    Returns:
        工具配置字典
    """
    config_path = os.path.join(os.path.dirname(__file__), "tools.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# 全局配置缓存
_tools_config = None


def get_tools_config() -> Dict[str, Any]:
    """获取工具配置（带缓存）。

    Returns:
        工具配置字典
    """
    global _tools_config
    if _tools_config is None:
        _tools_config = load_tools_config()
    return _tools_config


def get_apollo_config() -> Dict[str, Any]:
    """获取 Apollo 配置。"""
    return get_tools_config().get("apollo", {})


def get_sre_config() -> Dict[str, Any]:
    """获取 SRE 配置。"""
    return get_tools_config().get("sre", {})


def get_knowledge_config() -> Dict[str, Any]:
    """获取知识库配置。"""
    return get_tools_config().get("knowledge", {})
