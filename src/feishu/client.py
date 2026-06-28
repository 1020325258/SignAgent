# -*- coding: utf-8 -*-
"""飞书客户端初始化模块。"""

import os
import ssl
import logging
import websockets

from dotenv import load_dotenv

# 禁用 SSL 验证（解决自签名证书问题）
ssl._create_default_https_context = ssl._create_unverified_context

# 猴子补丁 websockets 库的 SSL 验证
_original_connect = websockets.connect
async def _patched_connect(*args, **kwargs):
    kwargs.setdefault('ssl', ssl._create_unverified_context())
    return await _original_connect(*args, **kwargs)
websockets.connect = _patched_connect

load_dotenv()

logger = logging.getLogger(__name__)

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")


def get_feishu_config() -> dict:
    """获取飞书配置。"""
    return {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }
