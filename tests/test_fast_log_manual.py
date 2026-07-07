# -*- coding: utf-8 -*-
"""手动测试 FAST 日志查询 - 展示 curl 请求和响应。"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx

# 配置
API_URL = "https://api.fast.ke.com/es/query"
API_KEY = "5dc1a7c244e388912d075ad0c4209b12"
USER_ID = "1000000000000000"
INDEX = "index-11274-11219*"
FIELDS = ["segmentId", "traceId", "data_info_msg", "timestamp", "_index"]

CST = timezone(timedelta(hours=8))


def build_curl_command(payload: dict) -> str:
    """构建 curl 命令。"""
    headers = [
        f'-H "api_key: {API_KEY}"',
        f'-H "X-NRS-User-Id: {USER_ID}"',
        '-H "Content-Type: application/json"',
    ]
    data = json.dumps(payload, ensure_ascii=False)
    return f"""curl --location --request POST '{API_URL}' \\
{' '.join(headers)} \\
--data-raw '{data}'"""


async def query_logs():
    """查询日志并展示请求和响应。"""
    # 计算时间范围：过去 15 小时
    now = datetime.now(CST)
    stime = int((now - timedelta(hours=15)).timestamp() * 1000)
    etime = int(now.timestamp() * 1000)

    # 构建查询参数
    query_string = '("盖公司章PDF入参" or "盖公司章PDF出参") && "130784367"'
    size = 20

    payload = {
        "index": INDEX,
        "stime": stime,
        "etime": etime,
        "fields": FIELDS,
        "queryString": query_string,
        "size": size,
    }

    # 打印 curl 命令
    print("=" * 80)
    print("📤 请求 CURL 命令:")
    print("=" * 80)
    print(build_curl_command(payload))
    print()

    # 打印请求参数
    print("=" * 80)
    print("📋 请求参数 (JSON):")
    print("=" * 80)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()

    # 发送请求
    headers = {
        "api_key": API_KEY,
        "X-NRS-User-Id": USER_ID,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            response = await client.post(API_URL, json=payload, headers=headers)

            print("=" * 80)
            print(f"📥 响应状态码: {response.status_code}")
            print("=" * 80)
            print()

            # 打印响应头
            print("=" * 80)
            print("📋 响应头:")
            print("=" * 80)
            for key, value in response.headers.items():
                print(f"{key}: {value}")
            print()

            # 打印响应体
            print("=" * 80)
            print("📄 响应内容:")
            print("=" * 80)
            data = response.json()
            print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])  # 限制输出长度
            print()

            # 解析结果
            total = data.get("total", 0)
            hits = data.get("data", [])

            print("=" * 80)
            print(f"✅ 查询结果: 共 {total} 条日志")
            print("=" * 80)
            for i, hit in enumerate(hits[:10]):  # 只显示前10条
                print(f"\n--- 日志 {i+1} ---")
                print(f"  segmentId: {hit.get('segmentId', '')}")
                print(f"  traceId: {hit.get('traceId', '')}")
                print(f"  data_info_msg: {hit.get('data_info_msg', '')[:200]}")
                print(f"  timestamp: {hit.get('timestamp', '')}")

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")


if __name__ == "__main__":
    asyncio.run(query_logs())
