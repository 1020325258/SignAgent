# -*- coding: utf-8 -*-
"""SRE 查询工具测试。"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from src.tools.sre.handlers import handle_request, validate_params, build_params, extract_data
from src.tools.sre.formatters import format_result, translate_enum
from src.tools.sre.config import get_api_config, get_available_actions


# ── 配置测试 ──────────────────────────────────────────────────

class TestConfig:
    """配置相关测试。"""

    def test_get_available_actions(self):
        """测试获取可用 action 列表。"""
        # 输入：无
        # 输出：所有可用的 action 列表
        actions = get_available_actions()

        assert "contract" in actions
        assert "contract_node" in actions
        assert "contract_user" in actions
        assert "contract_log" in actions
        assert "decrypt" in actions
        assert "user-phone-query" in actions

    def test_get_api_config(self):
        """测试获取 API 配置。"""
        # 输入：action = "contract"
        # 输出：contract 的 API 配置
        config = get_api_config("contract")

        assert config is not None
        assert config["name"] == "查询合同信息"
        assert config["endpoint"] == "/sre/contract"

    def test_get_api_config_unknown(self):
        """测试获取未知 action 的配置。"""
        # 输入：action = "unknown-action"
        # 输出：None
        config = get_api_config("unknown-action")

        assert config is None


# ── 参数验证测试 ──────────────────────────────────────────────

class TestValidation:
    """参数验证测试。"""

    def test_validate_contract_with_code(self):
        """测试 contract 参数验证 - 有 contract_code。"""
        # 输入：action="contract", contract_code="C123"
        # 输出：验证通过（返回 None）
        config = get_api_config("contract")
        args = {"action": "contract", "contract_code": "C123"}

        error = validate_params("contract", args, config)

        assert error is None

    def test_validate_contract_with_order_id(self):
        """测试 contract 参数验证 - 有 project_order_id。"""
        # 输入：action="contract", project_order_id="123456789012345678"
        # 输出：验证通过（返回 None）
        config = get_api_config("contract")
        args = {"action": "contract", "project_order_id": "123456789012345678"}

        error = validate_params("contract", args, config)

        assert error is None

    def test_validate_contract_without_params(self):
        """测试 contract 参数验证 - 无参数。"""
        # 输入：action="contract"（无 contract_code 和 project_order_id）
        # 输出：验证失败，返回错误信息
        config = get_api_config("contract")
        args = {"action": "contract"}

        error = validate_params("contract", args, config)

        assert error is not None
        assert "需要以下参数之一" in error

    def test_validate_contract_node_with_code(self):
        """测试 contract_node 参数验证。"""
        # 输入：action="contract_node", contract_code="C123"
        # 输出：验证通过（返回 None）
        config = get_api_config("contract_node")
        args = {"action": "contract_node", "contract_code": "C123"}

        error = validate_params("contract_node", args, config)

        assert error is None

    def test_validate_contract_node_without_code(self):
        """测试 contract_node 参数验证 - 无 contract_code。"""
        # 输入：action="contract_node"（无 contract_code）
        # 输出：验证失败，返回错误信息
        config = get_api_config("contract_node")
        args = {"action": "contract_node"}

        error = validate_params("contract_node", args, config)

        assert error is not None
        assert "contract_code" in error

    def test_validate_decrypt_with_text(self):
        """测试 decrypt 参数验证。"""
        # 输入：action="decrypt", encrypted_text="abc123"
        # 输出：验证通过（返回 None）
        config = get_api_config("decrypt")
        args = {"action": "decrypt", "encrypted_text": "abc123"}

        error = validate_params("decrypt", args, config)

        assert error is None

    def test_validate_user_phone_query(self):
        """测试 user-phone-query 参数验证。"""
        # 输入：action="user-phone-query", phone="15524175708"
        # 输出：验证通过（返回 None）
        config = get_api_config("user-phone-query")
        args = {"action": "user-phone-query", "phone": "15524175708"}

        error = validate_params("user-phone-query", args, config)

        assert error is None


# ── 参数构建测试 ──────────────────────────────────────────────

class TestBuildParams:
    """参数构建测试。"""

    def test_build_contract_params(self):
        """测试构建 contract 参数。"""
        # 输入：action="contract", contract_code="C123"
        # 输出：{"contractCode": "C123", "app": "sreAgent"}
        config = get_api_config("contract")
        args = {"action": "contract", "contract_code": "C123"}

        params = build_params("contract", args, config)

        assert params["contractCode"] == "C123"
        assert params["app"] == "sreAgent"

    def test_build_contract_params_with_order_id(self):
        """测试构建 contract 参数 - 使用 order_id。"""
        # 输入：action="contract", project_order_id="123456789012345678"
        # 输出：{"projectOrderId": "123456789012345678", "app": "sreAgent"}
        config = get_api_config("contract")
        args = {"action": "contract", "project_order_id": "123456789012345678"}

        params = build_params("contract", args, config)

        assert params["projectOrderId"] == "123456789012345678"
        assert params["app"] == "sreAgent"

    def test_build_user_phone_query_params(self):
        """测试构建 user-phone-query 参数。"""
        # 输入：action="user-phone-query", phone="15524175708"
        # 输出：{"bizId": "15524175708", "pageSize": 50, "currentPage": 1}（无 app 参数）
        config = get_api_config("user-phone-query")
        args = {"action": "user-phone-query", "phone": "15524175708"}

        params = build_params("user-phone-query", args, config)

        assert params["bizId"] == "15524175708"
        assert params["pageSize"] == 50
        assert params["currentPage"] == 1
        assert "app" not in params


# ── 格式化测试 ────────────────────────────────────────────────

class TestFormatters:
    """格式化测试。"""

    def test_format_empty_result(self):
        """测试空结果格式化。"""
        # 输入：data = None
        # 输出："查询结果为空"
        result = format_result("contract", None)

        assert result == "查询结果为空"

    def test_format_empty_list(self):
        """测试空列表格式化。"""
        # 输入：data = []
        # 输出："查询结果为空"
        result = format_result("contract", [])

        assert result == "查询结果为空"

    def test_format_object(self):
        """测试对象格式化。"""
        # 输入：{"contractCode": "C123", "status": 5, "type": 1}
        # 输出：JSON 格式，枚举值翻译
        data = {
            "contractCode": "C123",
            "status": 5,
            "type": 1,
        }

        result = format_result("contract", data)

        assert "C123" in result
        assert "5=待提交审核" in result  # 枚举值翻译
        assert "1=认购合同" in result

    def test_format_list(self):
        """测试列表格式化。"""
        # 输入：[{"contractCode": "C123", "status": 5}, {"contractCode": "C456", "status": 3}]
        # 输出：JSON 格式，包含 2 条记录
        data = [
            {"contractCode": "C123", "status": 5},
            {"contractCode": "C456", "status": 3},
        ]

        result = format_result("contract", data)

        assert "C123" in result
        assert "C456" in result
        assert "2 条" in result

    def test_translate_enum(self):
        """测试枚举值翻译。"""
        # 输入：enum_name="ContractStatusEnum", value=5
        # 输出："5=待提交审核"（或其他翻译结果）
        result = translate_enum("ContractStatusEnum", 5)

        assert "5=" in result

    def test_translate_enum_unknown(self):
        """测试未知枚举值翻译。"""
        # 输入：enum_name="UnknownEnum", value=999
        # 输出："999"（无法翻译，返回原值）
        result = translate_enum("UnknownEnum", 999)

        assert result == "999"


# ── 接口调用测试 ──────────────────────────────────────────────

class TestHandleRequest:
    """接口调用测试。"""

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self):
        """测试未知 action。"""
        # 输入：action="unknown-action"
        # 输出：ValueError("未知的操作类型")
        with pytest.raises(ValueError) as exc_info:
            await handle_request("unknown-action", {})

        assert "未知的操作类型" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_missing_params(self):
        """测试缺少必填参数。"""
        # 输入：action="contract"（无 contract_code 和 project_order_id）
        # 输出：ValueError("需要以下参数之一")
        with pytest.raises(ValueError) as exc_info:
            await handle_request("contract", {"action": "contract"})

        assert "需要以下参数之一" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_contract_query(self, mock_call_api):
        """测试查询合同信息。"""
        # 输入：action="contract", contract_code="C123"
        # Mock API 返回：{"success": true, "data": {"contractCode": "C123", "status": 5}}
        # 输出：{"contractCode": "C123", "status": 5}
        mock_call_api.return_value = {
            "success": True,
            "data": {"contractCode": "C123", "status": 5}
        }

        result = await handle_request("contract", {
            "action": "contract",
            "contract_code": "C123"
        })

        assert result["contractCode"] == "C123"
        assert result["status"] == 5
        mock_call_api.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_user_phone_query(self, mock_call_api):
        """测试根据手机号查询用户ID。"""
        # 输入：action="user-phone-query", phone="15524175708"
        # Mock API 返回：{"data": {"list": [{"userId": "ucid_123", "userName": "张三"}]}}
        # 输出：[{"userId": "ucid_123", "userName": "张三"}]
        mock_call_api.return_value = {
            "data": {
                "list": [{"userId": "ucid_123", "userName": "张三"}]
            }
        }

        result = await handle_request("user-phone-query", {
            "action": "user-phone-query",
            "phone": "15524175708"
        })

        assert len(result) == 1
        assert result[0]["userId"] == "ucid_123"

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_contract_node(self, mock_call_api):
        """测试查询合同节点。"""
        # 输入：action="contract_node", contract_code="C123"
        # Mock API 返回：{"success": true, "data": [{"nodeType": 1}, {"nodeType": 2}]}
        # 输出：[{"nodeType": 1}, {"nodeType": 2}]
        mock_call_api.return_value = {
            "success": True,
            "data": [{"nodeType": 1}, {"nodeType": 2}]
        }

        result = await handle_request("contract_node", {
            "action": "contract_node",
            "contract_code": "C123"
        })

        assert len(result) == 2
        assert result[0]["nodeType"] == 1

    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_decrypt(self, mock_call_api):
        """测试解密接口。"""
        # 输入：action="decrypt", encrypted_text="encrypted_xxx"
        # Mock API 返回：{"success": true, "data": "13800138000"}
        # 输出："13800138000"
        mock_call_api.return_value = {
            "success": True,
            "data": "13800138000"
        }

        result = await handle_request("decrypt", {
            "action": "decrypt",
            "encrypted_text": "encrypted_xxx"
        })

        assert result == "13800138000"


# ── 集成测试（MCP 工具完整链路） ─────────────────────────────

class TestRealFieldConfig:
    """field_config MCP 工具集成测试。

    调用 sre_query 工具的完整链路，测试实际输出。

    运行方式:
        python3 -m pytest tests/test_sre_query.py::TestRealFieldConfig -v -s
    """

    @pytest.mark.asyncio
    async def test_field_config_sd25(self):
        """圣都2.5 整装正签 (version=2) - MCP 工具完整输出。"""
        from src.tools.sre.tool import sre_query
        result = await sre_query.handler({
            "action": "field_config",
            "business_type": 1,
            "gb_code": 0,
            "company_code": "",
            "contract_type": 3,
            "version": 2,
            "page_num": 0,
            "page_size": 0,
        })
        text = result["content"][0]["text"]
        print(text)
        assert "查询结果" in text

    @pytest.mark.asyncio
    async def test_field_config_sd25_prequote(self):
        """圣都2.5预报价 整装正签 (version=3) - MCP 工具完整输出。"""
        from src.tools.sre.tool import sre_query
        result = await sre_query.handler({
            "action": "field_config",
            "business_type": 1,
            "gb_code": 0,
            "company_code": "",
            "contract_type": 3,
            "version": 3,
            "page_num": 0,
            "page_size": 0,
        })
        text = result["content"][0]["text"]
        print(text)
        assert "查询结果" in text



class TestRealContract:
    """合同查询 MCP 工具集成测试。

    运行方式:
        python3 -m pytest tests/test_sre_query.py::TestRealContract -v -s
    """

    @pytest.mark.asyncio
    async def test_contract_by_order_id(self):
        """根据订单号查询合同 - MCP 工具完整输出。"""
        from src.tools.sre.tool import sre_query
        result = await sre_query.handler({
            "action": "contract",
            "project_order_id": "826041310000003912",
        })
        text = result["content"][0]["text"]
        print(text)
        assert "查询结果" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
