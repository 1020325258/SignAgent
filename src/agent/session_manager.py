# -*- coding: utf-8 -*-
"""会话管理模块（文件存储）。"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器（文件存储）。"""

    def __init__(
        self,
        storage_dir: str = "./sessions",
        session_ttl: int = 3600 * 24,  # 24 小时过期
    ):
        """
        初始化会话管理器。

        Args:
            storage_dir: 会话存储目录
            session_ttl: 会话过期时间（秒）
        """
        self.storage_dir = storage_dir
        self.session_ttl = session_ttl
        self.active_clients: Dict[str, ClaudeSDKClient] = {}

        # 创建存储目录
        os.makedirs(storage_dir, exist_ok=True)

    def generate_session_id(self, user_id: str) -> str:
        """
        生成会话 ID。

        Args:
            user_id: 用户标识（飞书 open_id）

        Returns:
            会话 ID
        """
        return f"signagent_user_{user_id}"

    def _get_session_path(self, session_id: str) -> str:
        """获取会话文件路径。"""
        return os.path.join(self.storage_dir, f"{session_id}.json")

    async def get_client(
        self,
        session_id: str,
        options: ClaudeAgentOptions,
    ) -> ClaudeSDKClient:
        """
        获取或创建客户端。

        Args:
            session_id: 会话 ID
            options: Claude Agent 配置

        Returns:
            ClaudeSDKClient 实例
        """
        # 1. 检查内存中的活跃客户端
        if session_id in self.active_clients:
            client = self.active_clients[session_id]
            try:
                if client.is_connected:
                    return client
            except Exception:
                pass

        # 2. 检查文件中的会话
        session_info = self.load_session(session_id)
        if session_info:
            try:
                # 恢复会话
                client = ClaudeSDKClient.from_session(session_info, options=options)
                self.active_clients[session_id] = client
                logger.info(f"恢复会话: {session_id}")
                return client
            except Exception as e:
                logger.warning(f"恢复会话失败，创建新会话: {e}")

        # 3. 创建新客户端
        client = ClaudeSDKClient(options=options)
        self.active_clients[session_id] = client
        logger.info(f"创建新会话: {session_id}")
        return client

    def save_session(self, session_id: str, client: ClaudeSDKClient) -> None:
        """
        保存会话到文件。

        Args:
            session_id: 会话 ID
            client: ClaudeSDKClient 实例
        """
        try:
            session_info = client.get_session_info()
            session_data = {
                "session_id": session_id,
                "session_info": session_info,
                "updated_at": datetime.now().isoformat(),
            }
            filepath = self._get_session_path(session_id)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存会话: {session_id}")
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        从文件加载会话。

        Args:
            session_id: 会话 ID

        Returns:
            会话信息，不存在返回 None
        """
        filepath = self._get_session_path(session_id)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # 检查是否过期
            updated_at = datetime.fromisoformat(session_data["updated_at"])
            if (datetime.now() - updated_at).total_seconds() > self.session_ttl:
                logger.info(f"会话已过期: {session_id}")
                self.delete_session(session_id)
                return None

            return session_data.get("session_info")
        except Exception as e:
            logger.error(f"加载会话失败: {e}")
            return None

    def delete_session(self, session_id: str) -> None:
        """
        删除会话。

        Args:
            session_id: 会话 ID
        """
        try:
            filepath = self._get_session_path(session_id)
            if os.path.exists(filepath):
                os.remove(filepath)
            if session_id in self.active_clients:
                del self.active_clients[session_id]
            logger.info(f"删除会话: {session_id}")
        except Exception as e:
            logger.error(f"删除会话失败: {e}")

    async def close_client(self, session_id: str) -> None:
        """
        关闭客户端。

        Args:
            session_id: 会话 ID
        """
        if session_id in self.active_clients:
            client = self.active_clients[session_id]
            # 保存会话
            self.save_session(session_id, client)
            # 关闭客户端
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"关闭客户端失败: {e}")
            del self.active_clients[session_id]
