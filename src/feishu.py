"""
飞书 cc-connect 集成模块

处理飞书消息，对接签约助手 Agent。
"""

import os
import json
import hashlib
import logging
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from .agent import SignAgent

# 加载环境变量
load_dotenv()

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
feishu_app = FastAPI(
    title="签约助手 - 飞书机器人",
    description="飞书 cc-connect 集成",
    version="1.0.0",
)

# 全局 Agent 实例
agent: SignAgent = None

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")


class FeishuEvent(BaseModel):
    """飞书事件"""
    event_schema: str = "2.0"
    header: dict = {}
    event: dict = {}

    class Config:
        # 允许字段名与 BaseModel 属性冲突
        protected_namespaces = ()


class FeishuMessage(BaseModel):
    """飞书消息"""
    message_id: str = ""
    chat_id: str = ""
    chat_type: str = ""
    content: str = ""
    message_type: str = "text"
    sender: dict = {}


@feishu_app.on_event("startup")
async def startup():
    """应用启动时初始化 Agent"""
    global agent

    project_dir = os.getenv("SIGN_SYSTEM_PROJECT_DIR", ".")
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config)
    logger.info(f"✅ 飞书签约助手已启动，项目目录: {project_dir}")


def verify_signature(timestamp: str, nonce: str, body: str, signature: str) -> bool:
    """
    验证飞书签名

    Args:
        timestamp: 时间戳
        nonce: 随机数
        body: 请求体
        signature: 签名

    Returns:
        签名是否有效
    """
    # 飞书签名验证逻辑
    # TODO: 实现实际的签名验证
    return True


@feishu_app.post("/webhook/event")
async def handle_event(request: Request):
    """
    处理飞书事件回调

    飞书会向这个接口发送各种事件，包括：
    - 消息事件
    - 机器人被添加到群聊事件
    - 等等
    """
    try:
        body = await request.body()
        data = json.loads(body)

        # 验证签名
        headers = request.headers
        timestamp = headers.get("X-Lark-Request-Timestamp", "")
        nonce = headers.get("X-Lark-Request-Nonce", "")
        signature = headers.get("X-Lark-Signature", "")

        if not verify_signature(timestamp, nonce, body, signature):
            raise HTTPException(status_code=403, detail="签名验证失败")

        # 处理 URL 验证（首次配置 webhook 时飞书会发送）
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}

        # 处理事件
        event = data.get("event", {})
        event_type = event.get("type", "")

        if event_type == "im.message.receive_v1":
            # 接收到消息
            await handle_message(event)
        else:
            logger.info(f"未处理的事件类型: {event_type}")

        return {"code": 0, "msg": "success"}

    except Exception as e:
        logger.error(f"处理事件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_message(event: dict):
    """
    处理接收到的消息

    Args:
        event: 消息事件数据
    """
    try:
        message = event.get("message", {})
        message_type = message.get("message_type", "")
        content = message.get("content", "")
        chat_id = message.get("chat_id", "")
        message_id = message.get("message_id", "")
        sender = event.get("sender", {})

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

        # 调用 Agent 处理
        result = []
        async for text in agent.chat(question=question):
            result.append(text)

        answer = "".join(result)

        # 发送回复
        await send_reply(message_id, answer)

    except Exception as e:
        logger.error(f"处理消息失败: {e}")


async def send_reply(message_id: str, content: str):
    """
    发送回复消息

    Args:
        message_id: 原始消息 ID
        content: 回复内容
    """
    # TODO: 实现实际的消息发送
    # 需要使用飞书 API 发送消息
    logger.info(f"发送回复到 {message_id}: {content[:100]}...")

    # 这里需要调用飞书 API：
    # POST https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply
    # 需要先获取 access_token


async def get_access_token() -> str:
    """
    获取飞书访问令牌

    Returns:
        访问令牌
    """
    # TODO: 实现获取 access_token 的逻辑
    # POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
    # {
    #     "app_id": "xxx",
    #     "app_secret": "xxx"
    # }
    return ""


def start_feishu_server():
    """启动飞书服务"""
    import uvicorn

    host = os.getenv("FEISHU_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("FEISHU_SERVER_PORT", "8001"))

    logger.info(f"🚀 启动飞书签约助手服务: http://{host}:{port}")
    uvicorn.run(feishu_app, host=host, port=port)


if __name__ == "__main__":
    start_feishu_server()
