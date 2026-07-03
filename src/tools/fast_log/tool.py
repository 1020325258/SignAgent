# -*- coding: utf-8 -*-
"""FAST 日志查询工具定义。"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from claude_agent_sdk import tool

from .client import fetch_logs, extract_content
from .query_builder import validate_keyword_syntax, normalize_keyword

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

def parse_time(time_str: str) -> datetime:
    """解析时间字符串，返回带北京时区的 datetime。

    Args:
        time_str: 时间字符串，支持格式：
            - "YYYY-MM-DD HH:MM:SS"
            - "YYYY-MM-DDTHH:MM:SS"
            - "YYYY-MM-DD"

    Returns:
        datetime 对象

    Raises:
        ValueError: 格式错误
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(time_str, fmt).replace(tzinfo=CST)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间格式: {time_str}，请使用 'YYYY-MM-DD HH:MM:SS'")


def default_time_range() -> tuple:
    """默认时间范围：过去 1 小时。"""
    now = datetime.now(CST)
    start = now - timedelta(hours=CONFIG.get("defaultTimeRangeHours", 1))
    return start, now


def validate_time_range(start: datetime, end: datetime) -> Optional[str]:
    """校验时间范围。

    Args:
        start: 开始时间
        end: 结束时间

    Returns:
        错误信息，合法返回 None
    """
    if start >= end:
        return "错误：start_time 必须早于 end_time"

    max_hours = CONFIG.get("maxTimeRangeHours", 48)
    if (end - start).total_seconds() > max_hours * 3600:
        return f"错误：时间范围不能超过 {max_hours} 小时，请缩小查询范围"

    return None


def format_time_desc(start: datetime, end: datetime) -> str:
    """格式化时间描述。"""
    return f"{start.strftime('%Y-%m-%d %H:%M:%S')} ~ {end.strftime('%Y-%m-%d %H:%M:%S')}"


# ================= 结果格式化 =================

def format_result(total_count: int, hits: list, keyword: str,
                  time_desc: str, project: str) -> str:
    """格式化查询结果。

    Args:
        total_count: 总命中数
        hits: 日志列表
        keyword: 关键词
        time_desc: 时间描述
        project: 项目名

    Returns:
        格式化后的字符串
    """
    max_results = CONFIG.get("maxResults", 100)

    # 无结果
    if total_count == 0:
        return (
            f"❌ 未找到匹配的日志\n\n"
            f"查询参数：\n"
            f"- 项目：{project}\n"
            f"- 关键词：{keyword}\n"
            f"- 时间范围：{time_desc}\n\n"
            f"建议：\n"
            f"1. 检查关键词拼写是否正确\n"
            f"2. 尝试扩大时间范围重试\n"
            f"3. 简化关键词（去掉 AND/OR，单独搜索）\n"
            f"4. 确认日志是否在该服务中产生"
        )

    # 结果被截断
    display_count = min(max_results, len(hits))
    truncated = total_count > display_count
    truncation_tip = ""
    if truncated:
        truncation_tip = f"\n⚠️ 共 {total_count} 条结果，仅显示前 {display_count} 条。如需查看更多，请缩小时间范围或添加更多过滤条件。"

    # 格式化日志
    lines = [f"✅ 查询结果：共 {total_count} 条日志\n"]
    for hit in hits[:display_count]:
        src = hit.get("_source", {})
        ts = src.get("timestamp", "")
        level = src.get("level", src.get("log_level", ""))
        content = extract_content(src)
        level_tag = f" [{level}]" if level else ""
        lines.append(f"[{ts}]{level_tag} {content}")

    lines.append(f"\n---\n查询参数：project={project}, keyword={keyword}, time={time_desc}{truncation_tip}")

    return "\n".join(lines)


# ================= 工具定义 =================

@tool(
    "fast_log_query",
    """查询 nrs-sales-project 项目的线上日志。

支持的查询语法：
- 单关键词：contractPersonalDataV2
- AND 查询：contractPersonalDataV2 AND 826062913000003587（同时包含两个关键词）
- OR 查询：ERROR OR Exception（包含任一关键词）

时间规则：
- 默认查询过去 1 小时的日志
- 可指定 start_time 和 end_time 精确查询
- 时间范围最大不超过 48 小时

返回结果格式：[时间戳] [日志级别] 日志内容""",
    {
        "keyword": str,
        "start_time": Optional[str],
        "end_time": Optional[str],
    },
)
async def fast_log_query(args: dict[str, Any]) -> dict[str, Any]:
    """查询 FAST 日志。"""
    keyword = args.get("keyword", "").strip()
    start_time = args.get("start_time")
    end_time = args.get("end_time")

    # 1. 校验 keyword
    if not keyword:
        return {
            "content": [{"type": "text", "text": "错误：缺少 keyword 参数，请提供搜索关键词"}],
            "is_error": True,
        }

    # 2. 校验关键词语法
    syntax_error = validate_keyword_syntax(keyword)
    if syntax_error:
        return {
            "content": [{"type": "text", "text": syntax_error}],
            "is_error": True,
        }

    # 3. 解析时间范围
    try:
        if start_time:
            start = parse_time(start_time)
        else:
            start = default_time_range()[0]

        if end_time:
            end = parse_time(end_time)
        else:
            end = default_time_range()[1]
    except ValueError as e:
        return {
            "content": [{"type": "text", "text": str(e)}],
            "is_error": True,
        }

    # 4. 校验时间范围
    time_error = validate_time_range(start, end)
    if time_error:
        return {
            "content": [{"type": "text", "text": time_error}],
            "is_error": True,
        }

    # 5. 获取项目配置
    project_name = CONFIG.get("defaultProject", "nrs-sales-project")
    project_config = CONFIG["projects"].get(project_name)
    if not project_config:
        return {
            "content": [{"type": "text", "text": f"错误：项目 '{project_name}' 配置不存在"}],
            "is_error": True,
        }

    # 6. 执行查询
    try:
        total_count, hits = await fetch_logs(
            keyword=normalize_keyword(keyword),
            start=start,
            end=end,
            index=project_config["fastIndex"],
            fast_domain=project_config["fastDomain"],
            fetch_size=CONFIG.get("maxResults", 100),
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

    # 7. 格式化结果
    time_desc = format_time_desc(start, end)
    if not start_time and not end_time:
        time_desc = "过去 1 小时"

    result_text = format_result(total_count, hits, keyword, time_desc, project_name)

    return {
        "content": [{"type": "text", "text": result_text}],
    }
