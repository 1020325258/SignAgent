"""
飞书集成模块 - 基于 lark-cli

使用飞书官方 lark-cli 工具进行消息收发。
"""

import asyncio
import json
import subprocess
import logging
from typing import Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeishuMessage:
    """飞书消息"""
    message_id: str
    chat_id: str
    sender_id: str
    content: str
    message_type: str = "text"


class FeishuLarkCli:
    """基于 lark-cli 的飞书集成"""

    def __init__(self, chat_id: Optional[str] = None):
        """
        初始化飞书集成

        Args:
            chat_id: 默认聊天 ID，如果不指定则需要在每次调用时提供
        """
        self.chat_id = chat_id
        self._verify_lark_cli()

    def _verify_lark_cli(self):
        """验证 lark-cli 是否已安装"""
        try:
            result = subprocess.run(
                ["lark-cli", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"✅ lark-cli 已安装: {result.stdout.strip()}")
            else:
                logger.warning("⚠️ lark-cli 未正确安装，请运行: npx @larksuite/cli@latest install")
        except FileNotFoundError:
            logger.error("❌ lark-cli 未找到，请运行: npx @larksuite/cli@latest install")
            raise

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        message_type: str = "text"
    ) -> dict:
        """
        发送消息到飞书

        Args:
            text: 消息内容
            chat_id: 聊天 ID，如果不指定则使用默认值
            message_type: 消息类型

        Returns:
            命令执行结果
        """
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("必须指定 chat_id")

        cmd = [
            "lark-cli", "im", "+messages-send",
            "--chat-id", target_chat_id,
            "--text", text,
            "--format", "json"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"✅ 消息已发送到 {target_chat_id}")
                return {"success": True, "output": result.stdout}
            else:
                logger.error(f"❌ 发送失败: {result.stderr}")
                return {"success": False, "error": result.stderr}

        except subprocess.TimeoutExpired:
            logger.error("❌ 发送超时")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"❌ 发送异常: {e}")
            return {"success": False, "error": str(e)}

    def get_messages(
        self,
        chat_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """
        获取聊天消息

        Args:
            chat_id: 聊天 ID
            limit: 获取消息数量

        Returns:
            消息列表
        """
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("必须指定 chat_id")

        cmd = [
            "lark-cli", "im", "+messages-list",
            "--chat-id", target_chat_id,
            "--limit", str(limit),
            "--format", "json"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout) if result.stdout else []
            else:
                logger.error(f"❌ 获取消息失败: {result.stderr}")
                return []

        except Exception as e:
            logger.error(f"❌ 获取消息异常: {e}")
            return []

    def create_bot_message_handler(self, callback):
        """
        创建消息处理器（用于实时监听）

        Args:
            callback: 消息处理回调函数
        """
        # 使用 lark-cli 的事件订阅功能
        # 这需要配置飞书事件回调
        logger.info("消息处理器已创建，需要配置飞书事件回调")


class FeishuBot:
    """飞书机器人，集成 SignAgent"""

    def __init__(self, agent, chat_id: Optional[str] = None):
        """
        初始化飞书机器人

        Args:
            agent: SignAgent 实例
            chat_id: 默认聊天 ID
        """
        self.agent = agent
        self.feishu = FeishuLarkCli(chat_id)

    async def handle_message(self, message: FeishuMessage) -> str:
        """
        处理接收到的消息

        Args:
            message: 飞书消息

        Returns:
            回复内容
        """
        try:
            # 调用 SignAgent 处理
            result = []
            async for text in self.agent.chat(question=message.content):
                result.append(text)

            return "".join(result)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return f"抱歉，处理消息时出现错误: {str(e)}"

    async def reply_to_message(self, message: FeishuMessage, reply: str):
        """
        回复消息

        Args:
            message: 原始消息
            reply: 回复内容
        """
        self.feishu.send_message(
            text=reply,
            chat_id=message.chat_id
        )

    async def run_polling(self, interval: int = 5):
        """
        轮询模式运行（用于测试）

        Args:
            interval: 轮询间隔（秒）
        """
        logger.info(f"🚀 飞书机器人已启动，轮询间隔: {interval}秒")

        last_message_id = None

        while True:
            try:
                messages = self.feishu.get_messages(limit=1)

                if messages and messages[0].get("message_id") != last_message_id:
                    last_message_id = messages[0]["message_id"]

                    # 解析消息
                    msg = FeishuMessage(
                        message_id=messages[0].get("message_id", ""),
                        chat_id=messages[0].get("chat_id", ""),
                        sender_id=messages[0].get("sender", {}).get("id", ""),
                        content=messages[0].get("body", {}).get("content", ""),
                    )

                    # 处理消息
                    reply = await self.handle_message(msg)

                    # 发送回复
                    await self.reply_to_message(msg, reply)

                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                logger.info("👋 机器人已停止")
                break
            except Exception as e:
                logger.error(f"轮询异常: {e}")
                await asyncio.sleep(interval)


def start_feishu_bot(agent, chat_id: str):
    """
    启动飞书机器人

    Args:
        agent: SignAgent 实例
        chat_id: 聊天 ID
    """
    bot = FeishuBot(agent, chat_id)
    asyncio.run(bot.run_polling())
