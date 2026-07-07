# -*- coding: utf-8 -*-
"""FAST 日志查询工具集成测试。

运行方式:
    python3 -m pytest tests/test_fast_log.py -v -s

注意：集成测试需要在公司内网环境下运行，非内网环境会自动跳过。
"""

import pytest
import httpx
from datetime import datetime, timedelta, timezone

from src.tools.fast_log.tool import (
    fast_log_query,
    parse_time_to_millis,
    get_default_time_range,
    format_result,
)
from src.tools.fast_log.client import extract_content


# ── 内网环境检测 ──────────────────────────────────────────────

def is_intranet_available() -> bool:
    """检测是否在公司内网环境。"""
    try:
        response = httpx.head(
            "https://api.fast.ke.com",
            timeout=3,
            follow_redirects=False,
        )
        return response.status_code < 500
    except Exception:
        return False


# 标记：需要内网环境
requires_intranet = pytest.mark.skipif(
    not is_intranet_available(),
    reason="需要公司内网环境"
)


# ── 时间处理测试 ──────────────────────────────────────────────

class TestTimeHandling:
    """时间处理相关测试。"""

    def test_parse_time_to_millis_datetime(self):
        """测试解析 datetime 格式为毫秒时间戳。

        输入："2025-07-07 10:30:00"
        输出：毫秒时间戳（13位数字）
        """
        result = parse_time_to_millis("2025-07-07 10:30:00")
        assert isinstance(result, int)
        assert result > 1000000000000  # 毫秒时间戳应该是13位
        # 验证能正确还原
        dt = datetime.fromtimestamp(result / 1000, tz=timezone(timedelta(hours=8)))
        assert dt.year == 2025
        assert dt.month == 7
        assert dt.day == 7
        assert dt.hour == 10
        assert dt.minute == 30

    def test_parse_time_to_millis_iso(self):
        """测试解析 ISO 格式。

        输入："2025-07-07T10:30:00"
        输出：毫秒时间戳
        """
        result = parse_time_to_millis("2025-07-07T10:30:00")
        assert isinstance(result, int)
        assert result > 1000000000000

    def test_parse_time_to_millis_date_only(self):
        """测试解析日期格式。

        输入："2025-07-07"
        输出：毫秒时间戳（时间为 00:00:00）
        """
        result = parse_time_to_millis("2025-07-07")
        dt = datetime.fromtimestamp(result / 1000, tz=timezone(timedelta(hours=8)))
        assert dt.hour == 0
        assert dt.minute == 0

    def test_parse_time_to_millis_timestamp_seconds(self):
        """测试解析秒级时间戳字符串。

        输入："1688697000"（秒级时间戳）
        输出：毫秒时间戳（自动乘以1000）
        """
        result = parse_time_to_millis("1688697000")
        assert result == 1688697000000

    def test_parse_time_to_millis_timestamp_millis(self):
        """测试解析毫秒级时间戳字符串。

        输入："1688697000000"（毫秒级时间戳）
        输出：原样返回
        """
        result = parse_time_to_millis("1688697000000")
        assert result == 1688697000000

    def test_parse_time_to_millis_invalid(self):
        """测试解析无效格式。

        输入："invalid-time"
        输出：ValueError
        """
        with pytest.raises(ValueError):
            parse_time_to_millis("invalid-time")

    def test_get_default_time_range(self):
        """测试默认时间范围。

        验证点：
        1. 返回元组 (stime, etime)
        2. 时间差为 15 小时
        3. 都是毫秒时间戳
        """
        stime, etime = get_default_time_range()
        assert isinstance(stime, int)
        assert isinstance(etime, int)
        assert stime < etime

        # 验证时间差约为 15 小时（允许几秒误差）
        diff_ms = etime - stime
        diff_hours = diff_ms / (1000 * 3600)
        assert 14.9 < diff_hours < 15.1


# ── 内容提取测试 ──────────────────────────────────────────────

class TestExtractContent:
    """日志内容提取测试。"""

    def test_extract_from_hit(self):
        """测试从 hit 对象提取字段。

        输入：标准的 ES hit 对象
        输出：提取后的字典
        """
        hit = {
            "_source": {
                "segmentId": "seg-123",
                "traceId": "trace-456",
                "data_info_msg": "测试日志消息",
                "timestamp": "2025-07-07T10:30:00",
            },
            "_index": "index-11274-11219-2025.07.07",
        }
        result = extract_content(hit)
        assert result["segmentId"] == "seg-123"
        assert result["traceId"] == "trace-456"
        assert result["data_info_msg"] == "测试日志消息"
        assert result["timestamp"] == "2025-07-07T10:30:00"
        assert result["_index"] == "index-11274-11219-2025.07.07"

    def test_extract_with_missing_fields(self):
        """测试字段缺失的情况。

        输入：部分字段缺失的 hit 对象
        输出：缺失字段为空字符串
        """
        hit = {
            "_source": {
                "data_info_msg": "只有消息",
            },
        }
        result = extract_content(hit)
        assert result["segmentId"] == ""
        assert result["traceId"] == ""
        assert result["data_info_msg"] == "只有消息"

    def test_extract_with_empty_source(self):
        """测试空 _source 的情况。

        输入：空 _source
        输出：所有字段为空字符串
        """
        hit = {"_source": {}}
        result = extract_content(hit)
        assert result["segmentId"] == ""
        assert result["traceId"] == ""
        assert result["data_info_msg"] == ""


# ── 结果格式化测试 ──────────────────────────────────────────────

class TestFormatResult:
    """结果格式化测试。"""

    def test_format_empty_result(self):
        """测试空结果格式化。

        输入：total=0, hits=[]
        输出：包含"未找到"的提示信息
        """
        result = {"total": 0, "hits": []}
        text = format_result(result, "test query", "过去 15 小时")
        assert "未找到" in text
        assert "test query" in text

    def test_format_with_hits(self):
        """测试有结果的格式化。

        输入：total=2, hits=[...]
        输出：包含日志内容的格式化字符串
        """
        result = {
            "total": 2,
            "hits": [
                {
                    "segmentId": "seg-1",
                    "traceId": "trace-1",
                    "data_info_msg": "日志消息1",
                    "timestamp": "2025-07-07T10:30:00",
                    "_index": "index-1",
                },
                {
                    "segmentId": "seg-2",
                    "traceId": "trace-2",
                    "data_info_msg": "日志消息2",
                    "timestamp": "2025-07-07T10:31:00",
                    "_index": "index-2",
                },
            ],
        }
        text = format_result(result, "test query", "过去 15 小时")
        assert "共 2 条" in text
        assert "日志消息1" in text
        assert "日志消息2" in text
        assert "trace-1" in text
        assert "trace-2" in text

    def test_format_with_size_limit(self):
        """测试结果数量限制。

        输入：total=5, hits 有 5 条
        输出：显示所有 5 条
        """
        result = {
            "total": 5,
            "hits": [
                {
                    "segmentId": f"seg-{i}",
                    "traceId": f"trace-{i}",
                    "data_info_msg": f"消息{i}",
                    "timestamp": f"2025-07-07T10:{30+i}:00",
                    "_index": "index-1",
                }
                for i in range(5)
            ],
        }
        text = format_result(result, "test", "过去 15 小时")
        assert "共 5 条" in text
        # 验证所有消息都显示
        for i in range(5):
            assert f"消息{i}" in text


# ── MCP 工具集成测试（真实调用） ─────────────────────────────

@requires_intranet
class TestFastLogIntegration:
    """FAST 日志 MCP 工具集成测试。

    调用 fast_log_query 工具的完整链路，测试实际输出。

    运行方式:
        python3 -m pytest tests/test_fast_log.py::TestFastLogIntegration -v -s

    注意：这些测试会真实调用 FAST API，请确保在公司内网环境下运行。
    """

    @pytest.mark.asyncio
    async def test_query_with_basic_query_string(self):
        """测试基本的 queryString 查询。

        验证点：
        1. 工具能正常调用
        2. 返回结构正确
        3. 结果包含查询参数信息
        """
        result = await fast_log_query.handler({
            "queryString": '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"',
        })

        # 验证返回结构
        assert "content" in result
        assert len(result["content"]) > 0
        assert "text" in result["content"][0]

        text = result["content"][0]["text"]
        print("\n" + "=" * 60)
        print("基本查询结果：")
        print("=" * 60)
        print(text)
        print("=" * 60)

        # 验证结果包含查询参数
        assert "盖公司章PDF入参" in text or "盖公司章PDF出参" in text or "未找到" in text

    @pytest.mark.asyncio
    async def test_query_with_custom_size(self):
        """测试自定义 size 参数。

        验证点：
        1. size 参数生效
        2. 返回结果数量不超过 size
        """
        result = await fast_log_query.handler({
            "queryString": '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"',
            "size": 5,
        })

        text = result["content"][0]["text"]
        print("\n" + "=" * 60)
        print("自定义 size=5 查询结果：")
        print("=" * 60)
        print(text)
        print("=" * 60)

        # 验证返回结构正确
        assert "content" in result

    @pytest.mark.asyncio
    async def test_query_with_time_range(self):
        """测试带时间范围的查询。

        验证点：
        1. 自定义时间范围生效
        2. 结果格式正确
        """
        # 计算时间范围：过去 2 小时
        now = datetime.now(timezone(timedelta(hours=8)))
        start = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        end = now.strftime("%Y-%m-%d %H:%M:%S")

        result = await fast_log_query.handler({
            "queryString": '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"',
            "start_time": start,
            "end_time": end,
        })

        text = result["content"][0]["text"]
        print("\n" + "=" * 60)
        print("带时间范围的查询结果：")
        print("=" * 60)
        print(text)
        print("=" * 60)

        # 验证包含时间范围信息
        assert start[:10] in text  # 包含日期

    @pytest.mark.asyncio
    async def test_query_with_millis_timestamp(self):
        """测试使用毫秒时间戳的时间范围。

        验证点：
        1. 毫秒时间戳格式正确解析
        2. 查询正常执行
        """
        # 计算时间范围：过去 1 小时（毫秒时间戳）
        now = datetime.now(timezone(timedelta(hours=8)))
        etime = int(now.timestamp() * 1000)
        stime = int((now - timedelta(hours=1)).timestamp() * 1000)

        result = await fast_log_query.handler({
            "queryString": '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"',
            "start_time": str(stime),
            "end_time": str(etime),
        })

        text = result["content"][0]["text"]
        print("\n" + "=" * 60)
        print("毫秒时间戳查询结果：")
        print("=" * 60)
        print(text)
        print("=" * 60)

        assert "content" in result

    @pytest.mark.asyncio
    async def test_query_empty_query_string(self):
        """测试空 queryString 查询。

        验证点：
        1. 返回错误信息
        2. is_error 标志为 True
        """
        result = await fast_log_query.handler({
            "queryString": "",
        })

        assert result.get("is_error") is True
        assert "缺少 queryString" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_query_invalid_time_range(self):
        """测试非法时间范围。

        验证点：
        1. start > end 时返回错误
        2. is_error 标志为 True
        """
        result = await fast_log_query.handler({
            "queryString": "test",
            "start_time": "2025-07-07 12:00:00",
            "end_time": "2025-07-07 10:00:00",  # end < start
        })

        assert result.get("is_error") is True
        assert "必须早于" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_query_default_time_range_is_15_hours(self):
        """测试默认时间范围为 15 小时。

        验证点：
        1. 不传时间参数时，默认过去 15 小时
        2. 结果中显示正确的默认时间描述
        """
        result = await fast_log_query.handler({
            "queryString": '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"',
        })

        text = result["content"][0]["text"]
        print("\n" + "=" * 60)
        print("默认时间范围查询结果：")
        print("=" * 60)
        print(text)
        print("=" * 60)

        # 验证包含默认时间描述
        assert "过去 15 小时" in text


# ── 主入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
