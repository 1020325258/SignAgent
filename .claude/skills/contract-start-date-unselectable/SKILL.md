---
name: contract-start-date-unselectable
description: "合同开工日期无法选择排查。当用户提到\"开工日期无法选择\"、\"开工日期选不了\"、\"开工日期灰色\"、\"开工日期不可用\"、\"开工日期异常\"、\"getCalendar\"等关键词时，必须调用此 skill 进行排查，不要直接调用工具。"
---

# 开工日期无法选择排查

## 触发条件

以下场景应使用本 skill：

- 用户询问"开工日期无法选择"
- 用户询问"开工日期选不了"、"开工日期灰色"
- 用户提到"getCalendar 接口异常"
- 用户询问工期/日历相关问题

## 参数提取

从用户问题中提取订单号：

| 参数 | 格式特征 | 示例 |
|------|---------|------|
| **订单号** (project_order_id) | 纯数字，通常 18 位 | `826062712000004573` |

**识别规则**：
1. 提取用户问题中的数字串
2. 18 位纯数字 → 订单号
3. 如果无法识别，询问用户确认订单号

## 排查流程

### 第一步：提取订单号

从用户问题中提取订单号。如果无法提取到有效订单号，询问用户：
```
请提供需要排查的订单号（18位数字）
```

### 第二步：查询 getCalendar 请求日志

使用 `fast_log_query` 工具查询日志，**queryString 使用 Lucene 语法**：

```
fast_log_query(
    queryString='"api/contract/pc/getCalendar" && "{订单号}"',
    size=5
)
```

**示例**：
```
fast_log_query(
    queryString='"api/contract/pc/getCalendar" && "826062712000004573"'
)
```

### 第三步：提取 traceId

从返回的日志中提取 `traceId`。如果有多个 traceId，优先取最新的一个（时间戳最大的那条日志）。

### 第四步：查询全链路日志

使用上一步获取的 `traceId` 查询完整的请求链路日志：

```
fast_log_query(
    queryString='"{traceId}"',
    size=50
)
```

**示例**：
```
fast_log_query(
    queryString='"a1b2c3d4e5f6"'
)
```

**注意**：不要加其他条件，只用 traceId 查询，确保拿到完整的请求链路。

### 第五步：返回结果

将全链路日志返回给用户，提取关键信息：

- 请求参数
- 返回结果
- 是否有异常/错误信息

## 输出格式

```markdown
## 开工日期排查结果

### 查询参数
- **订单号**: {订单号}
- **traceId**: {traceId}

### getCalendar 请求日志
[第二步查询到的 getCalendar 日志]

### 全链路日志
[第四步查询到的完整 traceId 日志]
```

## 注意事项

1. **必须拿到 traceId**：查询 getCalendar 日志是为了提取 traceId，不要跳过这一步
2. **traceId 查询不加过滤**：查询全链路日志时只用 traceId，不要叠加订单号或其他条件
3. **解读日志，不分析原因**：提取请求参数、返回结果等关键信息呈现给用户，不需要分析为什么无法选择
4. **时间范围**：默认 15 小时，用户可指定，通过 `start_time` 和 `end_time` 参数传入（格式：`YYYY-MM-DD HH:MM:SS`）
