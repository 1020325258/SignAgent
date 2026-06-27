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

from .agent import SignAgent

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
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config)
    logger.info("✅ SignAgent 初始化完成")


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
        # 调用 Agent 处理
        result = []
        async for text in agent.chat(question=question):
            result.append(text)

        answer = "".join(result)

        # 发送回复
        await send_reply(message_id, answer)

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        import traceback
        traceback.print_exc()


async def send_reply(message_id: str, content: str):
    """
    发送回复消息

    Args:
        message_id: 原始消息 ID
        content: 回复内容
    """
    try:
        # 创建 Client
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()

        # 构造回复请求
        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(json.dumps({"text": content}))
                .msg_type("text")
                .build()) \
            .build()

        # 发送回复
        response = client.im.v1.message.reply(request)

        if response.success():
            logger.info(f"回复发送成功: {message_id}")
        else:
            logger.error(f"回复发送失败: {response.code} - {response.msg}")

    except Exception as e:
        logger.error(f"发送回复失败: {e}")


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
