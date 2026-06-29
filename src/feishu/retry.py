# -*- coding: utf-8 -*-
"""重试机制模块 - 借鉴 cc-connect 的实现。"""

import time
import random
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
RETRY_INITIAL_DELAY = 0.5  # 秒
RETRY_MAX_DELAY = 5.0  # 秒


def is_transient_error(error: Exception) -> bool:
    """判断是否为瞬态错误（可重试）。"""
    error_str = str(error).lower()
    transient_keywords = [
        "connection reset",
        "broken pipe",
        "timeout",
        "eof",
        "connection refused",
        "temporary failure",
    ]
    return any(keyword in error_str for keyword in transient_keywords)


def with_retry(func: Callable, *args, **kwargs) -> Any:
    """带重试的函数执行。

    Args:
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次重试的异常
    """
    last_error = None
    delay = RETRY_INITIAL_DELAY

    for attempt in range(MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if not is_transient_error(e) or attempt == MAX_RETRIES:
                raise

            # 添加 jitter
            jitter = random.uniform(0, delay * 0.25)
            actual_delay = delay + jitter

            logger.warning(f"Transient error, retrying (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            time.sleep(actual_delay)

            # 指数退避
            delay = min(delay * 2, RETRY_MAX_DELAY)

    raise last_error
