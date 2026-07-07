# -*- coding: utf-8 -*-
"""FAST 日志查询工具定义 - 使用新的 ES 查询接口。"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from claude_agent_sdk import tool

from .client import fetch_logs

logger = logging.getLogger(__name__)

# ================= 加载配置 =================

def _load_config() -> dict:
    """加载配置文件。"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = _load_config()
CST = timezone(timedelta(hours=8))


# ================= 时间处理 =================

def get_default_time_range() -> tuple[int, int]:
    """获取默认时间范围：过去 15 小时。

    Returns:
        (stime, etime) 毫秒时间戳元组
    """
    now = datetime.now(CST)
    start = now - timedelta(hours=CONFIG.get("defaultTimeRangeHours", 15))
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


def parse_time_to_millis(time_str: str) -> int:
    """解析时间字符串为毫秒时间戳。

    Args:
        time_str: 时间字符串，支持格式：
            - "YYYY-MM-DD HH:MM:SS"
            - "YYYY-MM-DDTHH:MM:SS"
            - "YYYY-MM-DD"
            - 毫秒时间戳字符串（纯数字）

    Returns:
        毫秒时间戳

    Raises:
        ValueError: 格式错误
    """
    # 尝试解析为纯数字时间戳
    if time_str.isdigit():
        ts = int(time_str)
        # 如果是秒级时间戳，转换为毫秒
        if ts < 10000000000:
            ts *= 1000
        return ts

    # 尝试解析为日期时间字符串
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(time_str, fmt).replace(tzinfo=CST)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"无法解析时间格式: {time_str}，请使用 'YYYY-MM-DD HH:MM:SS' 或毫秒时间戳")


def format_time_desc(stime: int, etime: int) -> str:
    """格式化时间描述。

    Args:
        stime: 毫秒时间戳
        etime: 毫秒时间戳

    Returns:
        可读的时间范围描述
    """
    start_dt = datetime.fromtimestamp(stime / 1000, tz=CST)
    end_dt = datetime.fromtimestamp(etime / 1000, tz=CST)
    return f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_dt.strftime('%Y-%m-%d %H:%M:%S')}"


# ================= 结果格式化 =================

def format_result(result: dict, query_string: str, time_desc: str) -> str:
    """格式化查询结果。

    Args:
        result: fetch_logs 返回的结果字典
        query_string: 查询字符串
        time_desc: 时间描述

    Returns:
        格式化后的字符串
    """
    total = result.get("total", 0)
    hits = result.get("hits", [])

    # 无结果
    if total == 0:
        return (
            f"❌ 未找到匹配的日志\n\n"
            f"查询参数：\n"
            f"- 查询语句：{query_string}\n"
            f"- 时间范围：{time_desc}\n\n"
            f"建议：\n"
            f"1. 检查查询语法是否正确\n"
            f"2. 尝试扩大时间范围重试\n"
            f"3. 简化查询条件\n"
            f"4. 确认日志是否在该索引中"
        )

    # 格式化日志
    lines = [f"✅ 查询结果：共 {total} 条日志\n"]
    for hit in hits:
        ts = hit.get("timestamp", "")
        trace_id = hit.get("traceId", "")
        segment_id = hit.get("segmentId", "")
        msg = hit.get("data_info_msg", "")

        # 构建行信息
        parts = []
        if ts:
            parts.append(f"[{ts}]")
        if trace_id:
            parts.append(f"traceId={trace_id}")
        if segment_id:
            parts.append(f"segmentId={segment_id}")
        if msg:
            parts.append(msg)

        lines.append(" | ".join(parts) if parts else json.dumps(hit, ensure_ascii=False))

    lines.append(f"\n---\n查询参数：queryString={query_string}, time={time_desc}")

    return "\n".join(lines)


# ================= 工具定义 =================

@tool(
    "fast_log_query",
    """查询 nrs-sales-project 项目的线上日志（FAST 平台）。

    此工具使用 Lucene 查询语法，由你根据用户问题构造 queryString。

    【Lucene 查询语法】
    - 单关键词：直接写关键词，如 `合同编号`
    - 短语查询：用双引号包裹，如 `"盖公司章PDF入参"`
    - 逻辑或：用 `or` 连接，如 `"关键词1" or "关键词2"`
    - 逻辑与：用 `and` 或 `&&` 连接，如 `"关键词1" && "关键词2"`
    - 组合查询：用括号分组，如 `("关键词1" or "关键词2") && "过滤条件"`
    - 通配符：`*` 匹配任意字符，`?` 匹配单个字符

    【参数说明】
    - queryString（必填）：Lucene 查询字符串，由你根据用户问题构造
    - size（可选）：返回条数，默认 20
    - start_time（可选）：开始时间，格式 'YYYY-MM-DD HH:MM:SS'。默认过去 15 小时
    - end_time（可选）：结束时间，格式 'YYYY-MM-DD HH:MM:SS'。默认当前时间

    【时间规则】
    - 默认查询过去 15 小时的日志
    - 如需特定时段，传入 'YYYY-MM-DD HH:MM:SS' 格式的时间""",
    {
        "queryString": str,
        "size": Optional[int],
        "start_time": Optional[str],
        "end_time": Optional[str],
    },
)
async def fast_log_query(args: dict[str, Any]) -> dict[str, Any]:
    """查询 FAST 日志。"""
    query_string = args.get("queryString", "").strip()
    size = args.get("size") or CONFIG.get("defaultSize", 20)
    start_time = args.get("start_time")
    end_time = args.get("end_time")

    # 1. 校验 queryString
    if not query_string:
        return {
            "content": [{"type": "text", "text": "错误：缺少 queryString 参数，请提供 ES 查询语句"}],
            "is_error": True,
        }

    # 2. 解析时间范围
    try:
        if start_time:
            stime = parse_time_to_millis(start_time)
        else:
            stime = get_default_time_range()[0]

        if end_time:
            etime = parse_time_to_millis(end_time)
        else:
            etime = get_default_time_range()[1]
    except ValueError as e:
        return {
            "content": [{"type": "text", "text": str(e)}],
            "is_error": True,
        }

    # 3. 校验时间范围
    if stime >= etime:
        return {
            "content": [{"type": "text", "text": "错误：start_time 必须早于 end_time"}],
            "is_error": True,
        }

    # 4. 获取固定配置
    index = CONFIG.get("index", "index-11274-11219*")
    fields = CONFIG.get("fields", ["segmentId", "traceId", "data_info_msg", "timestamp", "_index"])
    api_url = CONFIG.get("apiUrl", "https://api.fast.ke.com/es/query")

    # 5. 执行查询
    try:
        result = await fetch_logs(
            query_string=query_string,
            stime=stime,
            etime=etime,
            index=index,
            fields=fields,
            size=size,
            api_url=api_url,
        )
    except ValueError as e:
        return {
            "content": [{"type": "text", "text": str(e)}],
            "is_error": True,
        }
    except Exception as e:
        logger.exception("FAST log query failed")
        return {
            "content": [{"type": "text", "text": f"查询异常: {str(e)}"}],
            "is_error": True,
        }

    # 6. 格式化结果
    time_desc = format_time_desc(stime, etime)
    if not start_time and not end_time:
        time_desc = f"过去 {CONFIG.get('defaultTimeRangeHours', 15)} 小时"

    result_text = format_result(result, query_string, time_desc)

    return {
        "content": [{"type": "text", "text": result_text}],
    }
