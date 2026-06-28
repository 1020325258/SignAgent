# -*- coding: utf-8 -*-
"""工具基类模块。"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """MCP 工具基类。"""

    name: str
    description: str

    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具。

        Args:
            args: 工具输入参数

        Returns:
            工具执行结果
        """
        ...

    def format_result(self, result: Any) -> str:
        """格式化结果。

        Args:
            result: 工具返回结果

        Returns:
            格式化后的字符串
        """
        return str(result)
