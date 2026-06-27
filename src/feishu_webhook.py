"""
飞书 Webhook 集成模块

直接对接飞书开放平台，接收消息并回复。
"""

import os
import json
import hashlib
import logging
import httpx
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

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")

# 飞书 API 基础 URL
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# 全局变量
agent: SignAgent = None
access_token: str = None
token_expires_at: int = 0


class FeishuWebhook:
    """飞书 Webhook 处理器"""

    def __init__(self, app: FastAPI, sign_agent: SignAgent):
        """
        初始化飞书 Webhook

        Args:
            app: FastAPI 应用实例
            sign_agent: SignAgent 实例
        """
        self.app = app
        self.agent = sign_agent
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.app.post("/webhook/event")
        async def handle_event(request: Request):
            """处理飞书事件回调"""
            try:
                body = await request.body()
                data = json.loads(body)

                # 处理 URL 验证（首次配置 webhook 时飞书会发送）
                if data.get("type") == "url_verification":
                    return {"challenge": data.get("challenge")}

                # 处理事件
                header = data.get("header", {})
                event_type = header.get("event_type", "")
                event = data.get("event", {})

                logger.info(f"收到事件: {event_type}")

                if event_type == "im.message.receive_v1":
                    # 异步处理消息，避免超时
                    import asyncio
                    asyncio.create_task(self._handle_message(event))
                else:
                    logger.info(f"未处理的事件类型: {event_type}")

                return {"code": 0, "msg": "success"}

            except Exception as e:
                logger.error(f"处理事件失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health():
            """健康检查"""
            return {"status": "ok", "service": "SignAgent Feishu Webhook"}

    async def _handle_message(self, event: dict):
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
            sender_id = sender.get("sender_id", {}).get("open_id", "")

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
            async for text in self.agent.chat(question=question):
                result.append(text)

            answer = "".join(result)

            # 发送回复
            await self._send_reply(message_id, answer)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            import traceback
            traceback.print_exc()

    async def _send_reply(self, message_id: str, content: str):
        """
        发送回复消息

        Args:
            message_id: 原始消息 ID
            content: 回复内容
        """
        try:
            token = await self._get_access_token()

            url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "content": json.dumps({"text": content}),
                "msg_type": "text"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                result = response.json()

                if result.get("code") == 0:
                    logger.info(f"回复发送成功: {message_id}")
                else:
                    logger.error(f"回复发送失败: {result}")

        except Exception as e:
            logger.error(f"发送回复失败: {e}")

    async def _get_access_token(self) -> str:
        """
        获取飞书访问令牌

        Returns:
            访问令牌
        """
        global access_token, token_expires_at

        import time
        current_time = int(time.time())

        # 如果 token 还有效，直接返回
        if access_token and current_time < token_expires_at:
            return access_token

        # 获取新 token
        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()

            if result.get("code") == 0:
                access_token = result.get("tenant_access_token")
                token_expires_at = current_time + result.get("expire", 7200) - 300
                logger.info("获取 access_token 成功")
                return access_token
            else:
                logger.error(f"获取 access_token 失败: {result}")
                raise Exception(f"获取 access_token 失败: {result.get('msg')}")
