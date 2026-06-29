# -*- coding: utf-8 -*-
"""SRE 查询工具测试。"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from src.tools.sre.handlers import handle_request, validate_params, build_params
from src.tools.sre.formatters import format_result, format_user_info, translate_enum
from src.tools.sre.config import get_api_config, get_available_actions


# ── 配置测试 ──────────────────────────────────────────────────

class TestConfig:
    """配置相关测试。"""

    def test_get_available_actions(self):
        """测试获取可用 action 列表。"""
        actions = get_available_actions()
        assert "contract" in actions
        assert "contract_node" in actions
        assert "contract_user" in actions
        assert "contract_log" in actions
        assert "decrypt" in actions
        assert "user-phone-query" in actions

    def test_get_api_config(self):
        """测试获取 API 配置。"""
        config = get_api_config("contract")
        assert config is not None
        assert config["name"] == "查询合同信息"
        assert config["endpoint"] == "/sre/contract"

    def test_get_api_config_unknown(self):
        """测试获取未知 action 的配置。"""
        config = get_api_config("unknown-action")
        assert config is None


# ── 参数验证测试 ──────────────────────────────────────────────

class TestValidation:
    """参数验证测试。"""

    def test_validate_contract_with_code(self):
        """测试 contract 参数验证 - 有 contract_code。"""
        config = get_api_config("contract")
        args = {"action": "contract", "contract_code": "C123"}
        error = validate_params("contract", args, config)
        assert error is None

    def test_validate_contract_with_order_id(self):
        """测试 contract 参数验证 - 有 project_order_id。"""
        config = get_api_config("contract")
        args = {"action": "contract", "project_order_id": "123456789012345678"}
        error = validate_params("contract", args, config)
        assert error is None

    def test_validate_contract_without_params(self):
        """测试 contract 参数验证 - 无参数。"""
        config = get_api_config("contract")
        args = {"action": "contract"}
        error = validate_params("contract", args, config)
        assert error is not None
        assert "需要以下参数之一" in error

    def test_validate_contract_node_with_code(self):
        """测试 contract_node 参数验证。"""
        config = get_api_config("contract_node")
        args = {"action": "contract_node", "contract_code": "C123"}
        error = validate_params("contract_node", args, config)
        assert error is None

    def test_validate_contract_node_without_code(self):
        """测试 contract_node 参数验证 - 无 contract_code。"""
        config = get_api_config("contract_node")
        args = {"action": "contract_node"}
        error = validate_params("contract_node", args, config)
        assert error is not None
        assert "contract_code" in error

    def test_validate_decrypt_with_text(self):
        """测试 decrypt 参数验证。"""
        config = get_api_config("decrypt")
        args = {"action": "decrypt", "encrypted_text": "abc123"}
        error = validate_params("decrypt", args, config)
        assert error is None

    def test_validate_user_phone_query(self):
        """测试 user-phone-query 参数验证。"""
        config = get_api_config("user-phone-query")
        args = {"action": "user-phone-query", "phone": "15524175708"}
        error = validate_params("user-phone-query", args, config)
        assert error is None


# ── 参数构建测试 ──────────────────────────────────────────────

class TestBuildParams:
    """参数构建测试。"""

    def test_build_contract_params(self):
        """测试构建 contract 参数。"""
        config = get_api_config("contract")
        args = {"action": "contract", "contract_code": "C123"}
        params = build_params("contract", args, config)
        assert params["contractCode"] == "C123"
        assert params["app"] == "sreAgent"

    def test_build_contract_params_with_order_id(self):
        """测试构建 contract 参数 - 使用 order_id。"""
        config = get_api_config("contract")
        args = {"action": "contract", "project_order_id": "123456789012345678"}
        params = build_params("contract", args, config)
        assert params["projectOrderId"] == "123456789012345678"

    def test_build_user_phone_query_params(self):
        """测试构建 user-phone-query 参数。"""
        config = get_api_config("user-phone-query")
        args = {"action": "user-phone-query", "phone": "15524175708"}
        params = build_params("user-phone-query", args, config)
        assert params["bizId"] == "15524175708"
        assert params["pageSize"] == 50
        assert params["currentPage"] == 1
        assert "app" not in params  # 用户接口不需要 app 参数


# ── 格式化测试 ────────────────────────────────────────────────

class TestFormatters:
    """格式化测试。"""

    def test_format_empty_result(self):
        """测试空结果格式化。"""
        result = format_result("contract", None)
        assert result == "查询结果为空"

    def test_format_empty_list(self):
        """测试空列表格式化。"""
        result = format_result("contract", [])
        assert result == "查询结果为空"

    def test_format_object(self):
        """测试对象格式化。"""
        data = {
            "contractCode": "C123",
            "status": 5,
            "type": 1,
        }
        result = format_result("contract", data)
        assert "C123" in result
        assert "合同编号" in result

    def test_format_list(self):
        """测试列表格式化。"""
        data = [
            {"contractCode": "C123", "status": 5},
            {"contractCode": "C456", "status": 3},
        ]
        result = format_result("contract", data)
        assert "C123" in result
        assert "C456" in result
        assert "2 条" in result

    def test_format_user_info(self):
        """测试用户信息格式化。"""
        data = [{"userId": "ucid_123", "userName": "张三", "phone": "15524175708"}]
        result = format_user_info(data)
        assert "ucid_123" in result
        assert "张三" in result

    def test_format_user_info_empty(self):
        """测试空用户信息格式化。"""
        result = format_user_info([])
        assert "未找到" in result

    def test_translate_enum(self):
        """测试枚举值翻译。"""
        result = translate_enum("ContractStatusEnum", 5)
        assert "5=" in result

    def test_translate_enum_unknown(self):
        """测试未知枚举值翻译。"""
        result = translate_enum("UnknownEnum", 999)
        assert result == "999"


# ── 接口调用测试 ──────────────────────────────────────────────

class TestHandleRequest:
    """接口调用测试。"""

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self):
        """测试未知 action。"""
        with pytest.raises(ValueError) as exc_info:
            await handle_request("unknown-action", {})
        assert "未知的操作类型" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_missing_params(self):
        """测试缺少必填参数。"""
        with pytest.raises(ValueError) as exc_info:
            await handle_request("contract", {"action": "contract"})
        assert "需要以下参数之一" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_contract_query(self, mock_call_api):
        """测试查询合同信息。"""
        mock_call_api.return_value = {
            "success": True,
            "data": {"contractCode": "C123", "status": 5}
        }

        result = await handle_request("contract", {
            "action": "contract",
            "contract_code": "C123"
        })

        assert result["success"] is True
        assert result["data"]["contractCode"] == "C123"
        mock_call_api.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_user_phone_query(self, mock_call_api):
        """测试根据手机号查询用户ID。"""
        mock_call_api.return_value = {
            "data": {
                "list": [{"userId": "ucid_123", "userName": "张三"}]
            }
        }

        result = await handle_request("user-phone-query", {
            "action": "user-phone-query",
            "phone": "15524175708"
        })

        assert "data" in result
        assert result["data"]["list"][0]["userId"] == "ucid_123"

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_contract_node(self, mock_call_api):
        """测试查询合同节点。"""
        mock_call_api.return_value = {
            "success": True,
            "data": [{"nodeType": 1}, {"nodeType": 2}]
        }

        result = await handle_request("contract_node", {
            "action": "contract_node",
            "contract_code": "C123"
        })

        assert result["success"] is True
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_decrypt(self, mock_call_api):
        """测试解密接口。"""
        mock_call_api.return_value = {
            "success": True,
            "data": "13800138000"
        }

        result = await handle_request("decrypt", {
            "action": "decrypt",
            "encrypted_text": "encrypted_xxx"
        })

        assert result["success"] is True
        assert result["data"] == "13800138000"


# ── 集成测试 ──────────────────────────────────────────────────

class TestIntegration:
    """集成测试（需要网络访问）。"""

    @pytest.mark.skip(reason="需要内网访问")
    @pytest.mark.asyncio
    async def test_real_contract_query(self):
        """测试真实合同查询。"""
        result = await handle_request("contract", {
            "action": "contract",
            "project_order_id": "826041310000003912"
        })
        assert result["success"] is True
        formatted = format_result("contract", result["data"])
        assert "合同编号" in formatted

    @pytest.mark.skip(reason="需要内网访问")
    @pytest.mark.asyncio
    async def test_real_user_phone_query(self):
        """测试真实手机号查询。"""
        result = await handle_request("user-phone-query", {
            "action": "user-phone-query",
            "phone": "15524175708"
        })
        assert "data" in result
        formatted = format_user_info(result["data"]["list"])
        assert "用户ID" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
