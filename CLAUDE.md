# SignAgent - 签约系统智能助手

基于 Claude Code SDK 的签约系统智能助手，通过飞书 SDK 长连接对接飞书机器人。

## 参考项目

### 1. 飞书 SDK 示例

**路径**: `feishu-sdk-demo/`
**来源**: https://github.com/larksuite/oapi-sdk-python-demo
**用途**: 飞书 SDK 操作的官方示例代码

**主要内容**:
- `client.py` — 飞书客户端初始化示例
- `quick_start/` — 快速入门示例
- `composite_api/` — 复合 API 调用示例
- `config.py` — 配置管理示例
- `tests/` — 测试示例

**使用场景**:
- 参考飞书 SDK 的 API 调用方式
- 学习消息发送、接收、更新等操作
- 了解飞书卡片消息的构建方式

### 2. Claude Code SDK 示例

**路径**: `sdk-reference/`
**来源**: Claude Agent SDK 官方示例
**用途**: Claude Code SDK 的使用示例和参考

**主要内容**:
- `examples/` — 各种使用示例
  - `mcp_calculator.py` — MCP 工具示例
  - 其他示例代码
- `src/` — SDK 源码参考

**使用场景**:
- 参考 Claude Code SDK 的 API 调用方式
- 学习 MCP 工具的创建和配置
- 了解会话管理、流式输出等功能

## 项目结构

```
SignAgent/
├── config/                 # 配置模块
│   ├── __init__.py         # 配置加载
│   └── tools.yaml          # 工具配置
├── src/
│   ├── agent/              # Agent 核心
│   │   ├── agent.py        # SignAgent 主类
│   │   ├── config.py       # 配置相关
│   │   ├── formatters.py   # 格式化函数
│   │   ├── mcp_factory.py  # MCP 服务器工厂
│   │   └── session_manager.py  # 会话管理
│   ├── feishu/             # 飞书集成
│   │   ├── client.py       # 飞书客户端初始化
│   │   ├── handler.py      # 消息处理
│   │   ├── sender.py       # 消息发送
│   │   └── card_builder.py # 卡片内容构建
│   └── tools/              # MCP 工具
│       ├── base.py         # 工具基类
│       ├── knowledge.py    # 知识库搜索
│       ├── sre.py          # SRE 数据查询
│       └── apollo.py       # Apollo 配置查询
├── skills/                 # 技能文档
├── feishu-sdk-demo/        # 飞书 SDK 示例（参考）
├── sdk-reference/          # Claude Code SDK 示例（参考）
├── main_feishu_sdk.py      # 启动脚本
├── .env                    # 环境变量
└── README.md
```

## 开发规范

### 飞书 SDK 开发

**参考**: `feishu-sdk-demo/`

**消息发送**:
```python
# 参考 feishu-sdk-demo/client.py
import lark_oapi as lark

client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .build()
```

**卡片消息**:
```python
# 参考 feishu-sdk-demo/quick_start/
# 使用 msg_type="interactive" 发送卡片消息
# 卡片内容需要序列化为 JSON 字符串
```

**消息更新**:
```python
# 使用 PATCH 接口更新消息
# 只能更新卡片消息，不能更新文本消息
```

### Claude Code SDK 开发

**参考**: `sdk-reference/examples/`

**MCP 工具创建**:
```python
# 参考 sdk-reference/examples/mcp_calculator.py
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("tool_name", "工具描述", {"param": str})
async def my_tool(args):
    return {"content": [{"type": "text", "text": "结果"}]}

# 创建 MCP 服务器
server = create_sdk_mcp_server(
    name="my_server",
    version="1.0.0",
    tools=[my_tool],
)
```

**会话管理**:
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    session_id="uuid",
    continue_conversation=True,
    ...
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("问题")
    async for msg in client.receive_response():
        ...
```

## 飞书卡片格式

### 支持的 Markdown 语法（markdown 组件）

| 格式 | 语法 |
|------|------|
| 粗体 | `**文字**` |
| 斜体 | `*文字*` |
| 删除线 | `~~文字~~` |
| 行内代码 | `` `代码` `` |
| 链接 | `[文字](url)` |
| 引用 | `> 引用` |
| 列表 | `- 项目` 或 `1. 项目` |
| 分隔线 | `---` |

### 表格组件（纯文本）

飞书表格组件不支持 markdown 语法，需要清理：
- 去掉 `**粗体**` → `粗体`
- 去掉 `*斜体*` → `斜体`
- 去掉 `[链接](url)` → `链接`
- 去掉 `` `代码` `` → `代码`

**参考**: `src/feishu/card_builder.py` 中的 `clean_markdown()` 函数

## MCP 工具

### 当前可用工具

1. **knowledge_search** — 搜索知识库（Ke-RAG）
2. **sre_query** — 查询 SRE 生产环境数据
3. **apollo_query** — 查询 Apollo 配置中心

### 工具配置

**参考**: `config/tools.yaml`

### 添加新工具

1. 在 `src/tools/` 创建新的工具文件
2. 使用 `@tool` 装饰器定义工具
3. 在 `src/agent/mcp_factory.py` 注册工具
4. 在 `src/agent/agent.py` 添加到 `allowed_tools`

## 会话记忆

### 实现方式

- 使用 `ClaudeSDKClient` 实现多轮对话
- 会话持久化到 `./sessions/` 目录
- 24 小时自动过期

### 清除记忆

用户发送以下命令可清除会话：
- `清除记忆`
- `清除会话`
- `重新开始`
- `重置对话`

## Debug 模式

设置环境变量 `DEBUG=true` 可开启调试模式，输出：
- 💭 思考过程
- 🔧 工具调用参数
- ✅ 工具执行结果

## 常见问题

### 飞书表格格式问题

**问题**: 表格中出现 `**粗体**` 等 markdown 标记
**原因**: 飞书表格组件不支持 markdown 语法
**解决**: 使用 `clean_markdown()` 函数清理格式

### 会话记忆不生效

**问题**: 多轮对话没有上下文
**原因**: session_id 配置错误或会话过期
**解决**: 检查 session_id 格式（UUID）和会话文件

### SSL 证书错误

**问题**: `SSL: CERTIFICATE_VERIFY_FAILED`
**解决**: `client.py` 中已禁用 SSL 验证
