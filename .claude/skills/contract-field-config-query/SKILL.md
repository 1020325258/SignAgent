---
name: contract-field-config-query
version: 1.0.0
description: "合同表单配置查询 - 查询给前端下发的表单组件配置信息。用于查询合同表单的字段定义、显示规则、校验规则等配置。当用户询问合同表单配置、表单字段配置、表单组件配置时使用。不负责查询合同表单的实际数据（如已填写的表单内容），表单数据存储在 contract_field 表中，需要使用 sre_query(action='contract_field') 查询。"
metadata:
  requires:
    tools: ["sre_query"]
---

# 合同表单配置查询

## ⚠️ 核心规则：必须提供完整 5 个维度

**查询 field_config 必须提供全部 5 个维度，缺少任何一个都无法查询。**

### 维度完整性检查清单

在执行查询前，必须确认以下 5 个维度都已明确：

- ✅ **业态** (business_type)：1=整装, 2=团装, 3=局装, 4=翻新全案
- ✅ **品牌**：被窝 or 圣都（决定 gb_code 和 company_code）
- ✅ **合同类型** (contract_type)：1=认购合同, 2=设计合同, 3=正式套餐合同
- ✅ **版本** (version)：根据品牌确定（见下方说明）

### 缺失维度引导话术

**如果用户未提供完整信息，必须主动询问补充，不能假设或猜测。**

#### 缺少业态时：
```
请告诉我您要查询的业态类型：
1. 整装
2. 团装
3. 局装
4. 翻新全案
```

#### 缺少品牌时：
```
请告诉我您要查询的品牌：
- 被窝（北京地区）
- 圣都（其他城市）
```

#### 缺少合同时：
```
请告诉我您要查询的合同类型：
1. 认购合同
2. 设计合同
3. 正式套餐合同
```

#### 缺少版本时：

**被窝场景**：
```
被窝只有 2.5 版本，将使用 version=1
```

**圣都场景**：
```
请告诉我您要查询的圣都版本：
1. 圣都 2.0 (version=1)
2. 圣都 2.5 (version=2)
3. 预报价配置 (version=3) - 仅上海
```

---

## 触发条件

当用户提到以下关键词时触发此技能：
- 合同表单配置
- 表单配置
- 表单字段配置

## 功能说明

使用 `sre_query` 工具的 `field_config` action 查询合同表单字段配置。

## 查询维度

**必须明确全部 5 个维度**：`business_type`、`gb_code`、`company_code`、`contract_type`、`version`。

### 维度取值规则

| 维度 | 说明 | 取值 |
|------|------|------|
| business_type | 业态 | 1=整装, 2=团装, 3=局装, 4=翻新全案 |
| gb_code | 城市code | 见下方品牌说明 |
| company_code | 分公司code | 见下方品牌说明 |
| contract_type | 合同类型 | 见 ContractTypeEnum（1=认购合同, 2=设计合同, 3=正式套餐合同...） |
| version | 版本号 | 见下方品牌说明 |

### 品牌维度说明

#### 被窝

| 维度 | 取值 | 说明 |
|------|------|------|
| gb_code | 110000 | 被窝只有北京 |
| company_code | V201601528 | 被窝的固定分公司 |
| version | 1 | 表示被窝 2.5 版本（被窝只有 2.5 版本） |

#### 圣都

| 维度 | 取值 | 说明 |
|------|------|------|
| gb_code | 0 | 兜底配置，表示所有城市 |
| company_code | '' (空字符串) | 兜底配置，走默认 |
| version | 1 | 圣都 2.0 版本 |
| version | 2 | 圣都 2.5 版本 |
| version | 3 | 预报价配置（目前只有上海市配置了） |

## 查询示例

### 被窝场景查询

**被窝 + 整装 + 认购合同**：
```
sre_query(action="field_config", business_type=1, gb_code=110000, company_code="V201601528", contract_type=1, version=1)
```

### 圣都场景查询

**圣都 + 整装 + 认购合同 + 圣都 2.0**：
```
sre_query(action="field_config", business_type=1, gb_code=0, company_code="", contract_type=1, version=1)
```

**圣都 + 整装 + 认购合同 + 圣都 2.5**：
```
sre_query(action="field_config", business_type=1, gb_code=0, company_code="", contract_type=1, version=2)
```

**圣都 + 整装 + 认购合同 + 预报价**（仅上海）：
```
sre_query(action="field_config", business_type=1, gb_code=0, company_code="", contract_type=1, version=3)
```

## 分页查询

field_config 返回分页结构，默认每页 50 条。当配置项较多时，需要翻页获取完整数据：

```
# 第1页（默认）
sre_query(action="field_config", business_type=1, gb_code=0, company_code="", contract_type=1, version=2)

# 返回结果末尾会显示分页信息，如：
# **分页信息**: 第 1/3 页 | 每页 50 条 | 共 128 条
# 💡 还有下一页，使用 page_num=2 查询下一页

# 第2页
sre_query(action="field_config", business_type=1, gb_code=0, company_code="", contract_type=1, version=2, page_num=2)
```

### 分页策略

- 返回结果末尾的分页信息会告知总条数、总页数、是否有下一页
- 如果提示"还有下一页"，应继续查询下一页直到"已是最后一页"
- 如需一次性获取更多数据，可增大 `page_size`（如 `page_size=200`）

## 查询所有维度组合

可使用 `dim_combos` action 查询所有存在的维度组合：

```
sre_query(action="dim_combos")
```

## 查询流程

### 第一步：确认维度完整性

检查是否已获取全部 5 个维度（见最上方"核心规则"）。如果缺失，使用引导话术询问用户。

### 第二步：确定品牌相关维度值

- **被窝**：gb_code=110000, company_code="V201601528", version=1
- **圣都**：gb_code=0, company_code="", version 根据版本确定（1=2.0, 2=2.5, 3=预报价）

### 第三步：执行查询

调用 `sre_query` 查询 field_config，传入完整 5 个维度。

### 第四步：处理分页（如需要）

检查返回结果的分页信息，如果还有下一页，继续查询直到获取完整数据。

## 注意事项

1. **维度完整性（最重要）**：必须提供全部 5 个维度，缺少任何一个都无法查询
2. **主动引导**：如果用户没有提供完整信息，必须主动询问补充，不能假设或猜测
3. **品牌区分**：被窝和圣都的 city_code、company_code、version 取值完全不同
4. **版本含义**：version 在被窝和圣都场景下的含义不同（被窝只有 1 个版本，圣都有 3 个版本）
5. **兜底配置**：圣都的 gb_code=0 和 company_code='' 是兜底配置，表示所有没有特殊配置的都走此默认值
6. **预报价配置**：version=3 是特殊配置，目前只有上海市配置了预报价

## 不在本 skill 范围

- **合同表单数据查询**（已填写的表单内容） → 使用 `sre_query(action='contract_field', contract_code='xxx')`
- **合同基本信息查询** → 使用 `sre_query(action='contract')`
- **合同节点查询** → 使用 `sre_query(action='contract_node')`
- **合同操作日志查询** → 使用 `sre_query(action='contract_log')`
