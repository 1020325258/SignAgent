"""
飞书 SDK 集成模块

使用飞书官方 SDK 的长连接方式，无需公网 IP。
"""

import os
import json
import logging
import asyncio
import ssl
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

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from ..agent import SignAgent

# 加载环境变量
load_dotenv()

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 全局变量
agent: SignAgent = None
ws_client: lark.ws.Client = None


def init_agent():
    """初始化 SignAgent"""
    global agent

    project_dir = os.getenv("SIGN_AGENT_PROJECT_DIR", ".")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config, debug=debug)
    logger.info(f"✅ SignAgent 初始化完成 (debug={debug})")


def handle_message(data: P2ImMessageReceiveV1) -> None:
    """
    处理接收到的消息（同步版本）

    Args:
        data: 消息事件数据
    """
    try:
        logger.info(f"收到消息事件: {data}")
        message = data.event.message
        sender = data.event.sender

        # 获取消息内容
        message_type = message.message_type
        content = message.content
        chat_id = message.chat_id
        message_id = message.message_id
        sender_id = sender.sender_id.open_id

        # 只处理文本消息
        if message_type != "text":
            logger.info(f"忽略非文本消息: {message_type}")
            return

        # 解析消息内容
        try:
            content_data = json.loads(content)
            question = content_data.get("text", "")
        except json.JSONDecodeError:
            question = content

        # 去掉 @机器人 的部分
        if question.startswith("@"):
            question = question.split(" ", 1)[-1].strip()

        if not question:
            return

        logger.info(f"收到消息: {question}")

        # 在新线程中运行异步任务
        import threading
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_message(message_id, question))
            finally:
                loop.close()

        thread = threading.Thread(target=run_async)
        thread.start()

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()


async def process_message(message_id: str, question: str):
    """处理消息并发送回复"""
    try:
        # 先发送一条卡片消息
        reply_message_id = await send_reply(message_id, "正在分析你的问题...", msg_type="interactive")
        if not reply_message_id:
            logger.error("发送初始消息失败")
            return

        # 收集输出并实时更新
        full_answer = ""
        async for text in agent.chat(question=question):
            full_answer += text
            logger.info(f"收到输出: {text[:100]}...")
            # 每次收到输出就更新卡片
            await update_message(reply_message_id, full_answer, is_thinking=True)

        # 最终更新，去掉思考状态
        await update_message(reply_message_id, full_answer, is_thinking=False)

        logger.info(f"完整回复: {full_answer[:200]}...")

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()


def build_card_content(content: str, is_thinking: bool = False) -> str:
    """
    构建飞书卡片内容

    Args:
        content: 消息内容
        is_thinking: 是否为思考状态

    Returns:
        卡片 JSON 字符串
    """
    import re

    # ── 解析内容，分离 markdown 文本和表格 ──
    elements = []
    markdown_lines = []
    in_table = False
    table_headers = []
    table_rows = []

    def flush_markdown():
        """将累积的 markdown 行添加到 elements"""
        if markdown_lines:
            text = '\n'.join(markdown_lines).strip()
            if text:
                elements.append({
                    "tag": "markdown",
                    "content": text
                })
            markdown_lines.clear()

    def flush_table():
        """将累积的表格添加到 elements"""
        if table_headers and table_rows:
            # 构建飞书 Table 组件
            columns = []
            for i, header in enumerate(table_headers):
                columns.append({
                    "name": f"col_{i}",
                    "display_name": header,
                    "data_type": "text",
                    "width": "auto"
                })

            rows = []
            for row in table_rows:
                row_data = {}
                for i, cell in enumerate(row):
                    if i < len(table_headers):
                        row_data[f"col_{i}"] = cell
                rows.append(row_data)

            elements.append({
                "tag": "table",
                "page_size": 10,
                "row_height": "medium",
                "header_style": {
                    "text_align": "left",
                    "text_size": "normal",
                    "background_style": "grey",
                    "bold": True
                },
                "columns": columns,
                "rows": rows
            })
        table_headers.clear()
        table_rows.clear()

    lines = content.split('\n')

    for line in lines:
        # 过滤掉图片链接 ![alt](url)
        if re.search(r'!\[.*?\]\(.*?\)', line):
            continue

        # 将 ## 标题 转换为 **标题**
        if line.strip().startswith('#'):
            flush_table()
            title = re.sub(r'^#+\s*', '', line.strip())
            markdown_lines.append(f"**{title}**")
            continue

        # ── 表格处理：检测 markdown 表格，转换成飞书 Table 组件 ──
        if re.match(r'^\s*\|.*\|\s*$', line.strip()):
            cells = [c.strip() for c in line.strip().split('|') if c.strip()]

            # 跳过分隔行 |------|------|
            if all(re.match(r'^[-:]+$', c) for c in cells):
                in_table = True
                continue

            # 第一行是表头
            if not in_table:
                flush_markdown()
                table_headers = cells
                in_table = True
                continue

            # 数据行
            if table_headers and len(cells) == len(table_headers):
                table_rows.append(cells)
            continue

        # 表格结束
        if in_table and not re.match(r'^\s*\|.*\|\s*$', line.strip()):
            flush_table()
            in_table = False

        markdown_lines.append(line)

    # 处理剩余内容
    flush_markdown()
    flush_table()

    # 构建卡片
    card = {
        "elements": elements
    }

    # 如果是思考状态，添加一个 loading 提示
    if is_thinking:
        card["elements"].insert(0, {
            "tag": "markdown",
            "content": "⏳ **正在思考中...**\n\n---\n"
        })

    return json.dumps(card)


async def send_reply(message_id: str, content: str, msg_type: str = "text") -> str:
    """
    发送回复消息

    Args:
        message_id: 原始消息 ID
        content: 回复内容
        msg_type: 消息类型，text 或 interactive

    Returns:
        回复消息的 message_id，失败返回 None
    """
    try:
        # 创建 Client
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()

        # 根据消息类型构造内容
        if msg_type == "interactive":
            card_content = build_card_content(content, is_thinking=True)
        else:
            card_content = json.dumps({"text": content})

        # 构造回复请求
        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(card_content)
                .msg_type(msg_type)
                .build()) \
            .build()

        # 发送回复
        response = client.im.v1.message.reply(request)

        if response.success():
            reply_message_id = response.data.message_id
            logger.info(f"回复发送成功: {reply_message_id}")
            return reply_message_id
        else:
            logger.error(f"回复发送失败: {response.code} - {response.msg}")
            return None

    except Exception as e:
        logger.error(f"发送回复失败: {e}")
        return None


async def update_message(message_id: str, content: str, is_thinking: bool = True):
    """
    更新消息内容（用于流式输出）

    Args:
        message_id: 要更新的消息 ID
        content: 新的消息内容
        is_thinking: 是否仍在思考中
    """
    try:
        # 创建 Client
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()

        # 构建卡片内容
        card_content = build_card_content(content, is_thinking=is_thinking)

        # 构造更新请求
        request = PatchMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(PatchMessageRequestBody.builder()
                .content(card_content)
                .build()) \
            .build()

        # 更新消息
        response = client.im.v1.message.patch(request)

        if response.success():
            logger.debug(f"消息更新成功: {message_id}")
        else:
            logger.error(f"消息更新失败: {response.code} - {response.msg}")

    except Exception as e:
        logger.error(f"更新消息失败: {e}")


def start_feishu_sdk():
    """启动飞书 SDK 长连接"""
    global ws_client

    # 初始化 Agent
    init_agent()

    # 创建事件处理器
    event_handler = lark.EventDispatcherHandler.builder(
        "", ""  # 长连接模式不需要 encrypt_key 和 verification_token
    ).register_p2_im_message_receive_v1(handle_message) \
     .build()

    # 创建 WebSocket 客户端
    ws_client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG
    )

    logger.info("""
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  连接方式: 飞书 SDK 长连接（无需公网 IP）                    ║
║  状态: 正在连接飞书服务器...                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 启动长连接
    ws_client.start()
