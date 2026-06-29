---
name: sre-add-api
description: SRE 查询工具 - 新增接口标准化流程
---

# SRE 查询工具 - 新增接口指南

本指南用于向 `sre_query` 工具新增接口，**无需修改 Python 代码**，只需配置文件。

## 目录结构

```
src/tools/sre/
├── config/
│   ├── apis.yaml            # 接口配置
│   └── field_meanings.yaml  # 字段含义
└── enums/                   # 枚举定义（如有）
```

## 标准化流程

### 步骤 1: 在 apis.yaml 添加接口配置

**文件**: `src/tools/sre/config/apis.yaml`

```yaml
apis:
  # ... 已有接口 ...

  # 新增接口
  new-api-id:
    name: 接口名称
    description: 接口描述
    base_url: "http://api.example.com"
    endpoint: "/api/endpoint"
    method: GET
    auth:
      app: sreAgent  # 认证参数，null 表示无需认证
    parameters:
      param1:
        type: string          # 类型: string/integer/boolean
        required: true        # 是否必填
        description: "参数说明"
        api_key: param1Key    # 传给 API 的参数名
      param2:
        type: integer
        required: false
        description: "可选参数说明"
        api_key: param2Key
    required_any: [param1, param2]  # 可选：至少需要一个
    default_params:
      pageSize: 50            # 可选：默认参数
    response:
      type: object            # object 或 list
      data_path: data         # 数据路径，如 "data.list"
```

**配置说明：**

| 字段 | 说明 |
|------|------|
| `name` | 接口名称（用于文档） |
| `description` | 接口描述（用于文档） |
| `base_url` | API 基础 URL |
| `endpoint` | API 路径 |
| `method` | HTTP 方法（GET/POST） |
| `auth` | 认证参数，null 表示无需认证 |
| `parameters` | 参数定义 |
| `parameters.*.type` | 参数类型：string/integer/boolean |
| `parameters.*.required` | 是否必填 |
| `parameters.*.api_key` | 传给 API 的参数名 |
| `required_any` | 至少需要一个的参数列表 |
| `default_params` | 默认参数 |
| `response.type` | 响应类型：object/list |
| `response.data_path` | 数据路径，用 "." 分隔 |

### 步骤 2: 在 field_meanings.yaml 添加字段含义（可选）

**文件**: `src/tools/sre/config/field_meanings.yaml`

```yaml
# 格式: [中文含义, 枚举类型名或null]

# 接口专属字段
new-api-id.field1: [字段1含义, null]
new-api-id.field2: [字段2含义, EnumType]

# 通用字段（所有接口共用）
newField: [字段含义, null]
```

**说明：**
- 如果字段有枚举类型，填写枚举类型名（如 `ContractTypeEnum`）
- 如果字段无枚举类型，填写 `null`
- 通用字段会自动匹配所有接口

### 步骤 3: 添加枚举定义（如有枚举字段）

**创建枚举文件**: `src/tools/sre/enums/new_enum.py`

```python
# -*- coding: utf-8 -*-
"""新枚举定义。"""

NEW_ENUM = {
    1: "状态1",
    2: "状态2",
    3: "状态3",
}
```

**注册枚举**: `src/tools/sre/enums/__init__.py`

```python
from .new_enum import NEW_ENUM

ENUM_REGISTRY = {
    ...,
    "NewEnum": NEW_ENUM,
}
```

### 步骤 4: 添加测试

**文件**: `tests/test_sre_query.py`

```python
class TestHandleRequest:
    @pytest.mark.asyncio
    @patch("src.tools.sre.handlers.call_api")
    async def test_handle_new_api(self, mock_call_api):
        """测试新接口。"""
        mock_call_api.return_value = {
            "data": {"field1": "value1", "field2": 2}
        }

        result = await handle_request("new-api-id", {
            "action": "new-api-id",
            "param1": "test"
        })

        assert result["field1"] == "value1"
        assert result["field2"] == 2
```

### 步骤 5: 运行测试

```bash
python3 -m pytest tests/test_sre_query.py -v
```

### 步骤 6: 完成

**无需修改任何 Python 代码！** 新接口已可用。

---

## 完整示例

### 场景：新增「根据订单号查询用户信息」接口

**Step 1: apis.yaml**
```yaml
apis:
  order-user-info:
    name: 根据订单号查询用户信息
    description: 查询订单关联的用户信息
    base_url: "http://i.cms.home.ke.com"
    endpoint: "/api/order/user-info"
    method: GET
    auth: null
    parameters:
      order_id:
        type: string
        required: true
        description: "订单号"
        api_key: orderId
    response:
      type: object
      data_path: data
```

**Step 2: field_meanings.yaml**
```yaml
order-user-info.userId: [用户ID, null]
order-user-info.userName: [用户名, null]
order-user-info.phone: [手机号, null]
order-user-info.userType: [用户类型, UserTypeEnum]
```

**Step 3: 添加枚举（如有）**
```python
# src/tools/sre/enums/user_type.py
USER_TYPE_ENUM = {
    1: "个人用户",
    2: "企业用户",
}
```

**Step 4: 测试**
```python
@pytest.mark.asyncio
@patch("src.tools.sre.handlers.call_api")
async def test_handle_order_user_info(self, mock_call_api):
    mock_call_api.return_value = {
        "data": {"userId": "u123", "userName": "张三", "userType": 1}
    }

    result = await handle_request("order-user-info", {
        "action": "order-user-info",
        "order_id": "ORDER123"
    })

    assert result["userId"] == "u123"
```

**Step 5: 运行测试**
```bash
python3 -m pytest tests/test_sre_query.py -v
```

---

## 验证清单

- [ ] apis.yaml 配置正确
- [ ] field_meanings.yaml 字段含义正确（可选）
- [ ] 枚举定义正确（如有）
- [ ] 测试用例通过
- [ ] 实际调用验证

---

## 常见问题

### Q: 如何确定 response.data_path？

A: 查看 API 返回的 JSON 结构，找到数据所在的路径。

例如：
```json
{
  "code": 200,
  "data": {
    "list": [...]
  }
}
```
数据路径为 `data.list`

### Q: 如何处理分页？

A: 在 `default_params` 中添加分页参数：
```yaml
default_params:
  pageSize: 50
  currentPage: 1
```

### Q: 如何处理 POST 请求？

A: 设置 `method: POST`，参数会以 JSON body 形式发送。

### Q: 如何处理多个认证参数？

A: 在 `auth` 中添加多个参数：
```yaml
auth:
  app: sreAgent
  token: xxx
```
