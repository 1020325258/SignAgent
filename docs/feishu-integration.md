# 飞书集成方案

## 方案选择

有两种方式可以接入飞书：

### 方案 1：使用 lark-cli（推荐）

**优点：**
- 官方维护，稳定性好
- 专门为 AI Agent 设计
- 200+ 命令，覆盖消息、文档、日历等
- 内置安全防护
- 无需处理复杂的 OAuth 流程

**安装：**
```bash
npx @larksuite/cli@latest install
```

**使用方式：**
```bash
# 发送消息
lark-cli im +messages-send --chat-id "oc_xxx" --text "Hello"

# 读取消息
lark-cli im +messages-list --chat-id "oc_xxx"
```

### 方案 2：直接使用飞书开放平台 API

**优点：**
- 更灵活的控制
- 可以自定义所有逻辑

**缺点：**
- 需要自己处理 OAuth、签名验证等
- 开发工作量大

## 推荐架构

```
用户飞书消息 → lark-cli 接收 → SignAgent 处理 → lark-cli 回复
```

## 实现步骤

### 1. 安装 lark-cli

```bash
npx @larksuite/cli@latest install
```

### 2. 配置飞书应用

```bash
lark-cli config init --new
```

这会引导你创建飞书应用并获取 App ID 和 App Secret。

### 3. 登录授权

```bash
lark-cli auth login --recommend
```

### 4. 在 SignAgent 中集成

使用 subprocess 调用 lark-cli 命令：
```python
import subprocess

def send_feishu_message(chat_id: str, text: str):
    subprocess.run([
        "lark-cli", "im", "+messages-send",
        "--chat-id", chat_id,
        "--text", text
    ])
```

或者使用 lark-cli 的 Agent Skills 直接集成到 Claude Code SDK 中。
