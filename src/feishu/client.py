# -*- coding: utf-8 -*-
"""飞书客户端初始化模块。"""

import os
import logging

from dotenv import load_dotenv

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
