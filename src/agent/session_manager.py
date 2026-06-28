# -*- coding: utf-8 -*-
"""会话管理模块（文件存储）。"""

import os
import json
import uuid
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
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id

        # 创建存储目录
        os.makedirs(storage_dir, exist_ok=True)

        # 加载已有的用户会话映射
        self._load_user_sessions()

    def _load_user_sessions(self):
        """加载用户会话映射。"""
        mapping_file = os.path.join(self.storage_dir, "user_sessions.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    self.user_sessions = json.load(f)
                logger.info(f"加载了 {len(self.user_sessions)} 个用户会话映射")
            except Exception as e:
                logger.error(f"加载用户会话映射失败: {e}")

    def _save_user_sessions(self):
        """保存用户会话映射。"""
        mapping_file = os.path.join(self.storage_dir, "user_sessions.json")
        try:
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump(self.user_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户会话映射失败: {e}")

    def get_or_create_session_id(self, user_id: str) -> str:
        """
        获取或创建用户的会话 ID。

        Args:
            user_id: 用户标识（飞书 open_id）

        Returns:
            会话 ID (UUID)
        """
        # 检查是否已有会话
        if user_id in self.user_sessions:
            session_id = self.user_sessions[user_id]
            # 检查会话文件是否存在且未过期
            if self._is_session_valid(session_id):
                return session_id

        # 创建新会话
        session_id = str(uuid.uuid4())
        self.user_sessions[user_id] = session_id
        self._save_user_sessions()
        logger.info(f"为用户 {user_id} 创建新会话: {session_id}")
        return session_id

    def _is_session_valid(self, session_id: str) -> bool:
        """检查会话是否有效（存在且未过期）。"""
        session_file = os.path.join(self.storage_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            return False

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            updated_at = datetime.fromisoformat(session_data["updated_at"])
            if (datetime.now() - updated_at).total_seconds() > self.session_ttl:
                logger.info(f"会话已过期: {session_id}")
                return False

            return True
        except Exception:
            return False

    def save_session(self, user_id: str, session_id: str) -> None:
        """
        保存会话信息。

        Args:
            user_id: 用户标识
            session_id: 会话 ID
        """
        try:
            session_data = {
                "user_id": user_id,
                "session_id": session_id,
                "updated_at": datetime.now().isoformat(),
            }
            filepath = os.path.join(self.storage_dir, f"{session_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存会话: {session_id}")
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def delete_session(self, user_id: str) -> None:
        """
        删除用户会话。

        Args:
            user_id: 用户标识
        """
        if user_id in self.user_sessions:
            session_id = self.user_sessions[user_id]
            # 删除会话文件
            filepath = os.path.join(self.storage_dir, f"{session_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            # 删除映射
            del self.user_sessions[user_id]
            self._save_user_sessions()
            logger.info(f"删除用户会话: {user_id}")

    def create_client(self, session_id: str, options: ClaudeAgentOptions, resume: bool = False) -> ClaudeSDKClient:
        """
        创建客户端。

        Args:
            session_id: 会话 ID
            options: Claude Agent 配置
            resume: 是否恢复会话

        Returns:
            ClaudeSDKClient 实例
        """
        if resume:
            options.resume = session_id
        else:
            options.session_id = session_id

        return ClaudeSDKClient(options=options)
