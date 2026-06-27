# SignAgent - 签约系统助手

基于 Claude Code SDK 的签约系统智能助手，通过飞书 SDK 长连接直接对接飞书机器人。

## 架构说明

```
用户 (飞书) → 飞书服务器 → SignAgent (长连接) → Claude Code SDK → 回复
```

**优势：**
- ✅ 无需公网 IP
- ✅ 无需 ngrok
- ✅ 无需 cc-connect
- ✅ 直接使用飞书 SDK 长连接

## 前置条件

- Python 3.10+
- Node.js 18+（用于安装 Claude Code）
- 飞书账号

## 安装步骤

### 1. 安装 Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

验证安装：
```bash
claude --version
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置飞书应用

#### 3.1 创建飞书应用

1. 打开飞书开放平台：https://open.feishu.cn/app
2. 点击 **创建企业自建应用**
3. 填写应用名称（如：SignAgent 签约助手）

#### 3.2 启用机器人能力

1. 进入 **应用能力** → **机器人**
2. 点击 **启用机器人**

#### 3.3 配置事件订阅

1. 进入 **事件与回调** → **事件配置**
2. **配置方式** 选择：**使用长连接方式接收事件**
3. 点击 **添加事件**，搜索并添加：`im.message.receive_v1`（接收消息）

#### 3.4 配置权限

1. 进入 **权限管理**
2. 添加以下权限：
   - `im:message` — 获取与发送单聊、群组消息
   - `im:message:send_as_bot` — 以应用的身份发消息

#### 3.5 发布应用

1. 进入 **版本管理与发布**
2. 创建版本并发布
3. 等待审核通过（企业自建应用通常自动通过）

#### 3.6 获取应用凭证

1. 进入 **凭证与基础信息**
2. 复制 **App ID** 和 **App Secret**

### 4. 配置环境变量

复制配置文件：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：
```env
# Claude API 配置
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_AUTH_TOKEN=your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6

# 签约系统项目目录
SIGN_AGENT_PROJECT_DIR=/Users/zqy/work/AI-Project/SignAgent

# 飞书应用配置
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

**配置说明：**

| 配置项 | 说明 |
|--------|------|
| `ANTHROPIC_AUTH_TOKEN` | Claude API 密钥 |
| `SIGN_AGENT_PROJECT_DIR` | 签约系统项目目录的绝对路径 |
| `FEISHU_APP_ID` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 飞书应用密钥 |

## 启动服务

```bash
cd /Users/zqy/work/AI-Project/SignAgent
python3 main_feishu_sdk.py
```

启动成功后会显示：
```
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  连接方式: 飞书 SDK 长连接（无需公网 IP）                    ║
║  状态: 已连接飞书服务器                                      ║
╚══════════════════════════════════════════════════════════════╝
```

## 使用方法

### 在飞书中与机器人对话

1. 打开飞书 App
2. 找到你创建的机器人（如：SignAgent 签约助手）
3. 直接发送消息即可

### 对话示例

```
签约系统有哪些合同模板？
帮我分析一下合同签署的流程
签约失败是什么原因？
这个项目的目录结构是怎样的？
```

### 查看日志

启动服务的终端会显示实时日志，包括：
- 收到的消息
- Claude Code 的处理过程
- 回复发送状态

## 项目结构

```
SignAgent/
├── src/
│   ├── __init__.py           # 包初始化
│   ├── agent.py              # Agent 核心实现（基于 Claude Code SDK）
│   ├── feishu_sdk.py         # 飞书 SDK 长连接集成
│   └── feishu_webhook.py     # 飞书 Webhook 集成（备用）
├── sdk-reference/            # Claude Agent SDK 参考代码
├── main_feishu_sdk.py        # 启动脚本（推荐）
├── main.py                   # 启动脚本（多模式）
├── requirements.txt          # 依赖包
├── .env.example              # 配置示例
├── .env                      # 配置文件（需手动创建）
└── README.md                 # 本文件
```

## 工作原理

### 飞书 SDK 长连接

SignAgent 使用飞书官方 SDK 的长连接方式接收消息：

1. **启动时**：SignAgent 通过 WebSocket 连接到飞书服务器
2. **用户发消息**：飞书服务器通过 WebSocket 推送消息给 SignAgent
3. **处理消息**：SignAgent 调用 Claude Code SDK 处理消息
4. **发送回复**：SignAgent 通过飞书 API 发送回复

### 为什么不需要公网 IP？

```
传统方式：飞书服务器 → HTTP 回调 → 你的服务器（需要公网 IP）
长连接方式：SignAgent → WebSocket 连接 → 飞书服务器（出站连接，不需要公网 IP）
```

SignAgent **主动连接**飞书服务器，就像浏览器访问网站一样，只需要能上网就行。

## 故障排查

### 问题：机器人没有回复

1. 检查 SignAgent 是否正在运行
2. 查看终端日志是否有错误信息
3. 确认飞书应用已发布并启用

### 问题：SSL 证书错误

如果出现 `SSL: CERTIFICATE_VERIFY_FAILED` 错误，SignAgent 已内置了 SSL 验证禁用，通常不需要额外处理。

### 问题：权限错误

确保飞书应用有以下权限：
- `im:message` — 获取与发送单聊、群组消息
- `im:message:send_as_bot` — 以应用的身份发消息

### 问题：事件订阅未生效

1. 确认 **配置方式** 选择的是 **长连接**（不是 Webhook）
2. 确认已添加事件：`im.message.receive_v1`
3. 重新发布应用版本

## 后台运行（可选）

### 使用 screen

```bash
# 创建 screen 会话
screen -S signagent

# 启动服务
python3 main_feishu_sdk.py

# 分离会话：Ctrl+A, D

# 重新连接
screen -r signagent
```

### 使用 systemd（Linux）

创建 `/etc/systemd/system/signagent.service`：
```ini
[Unit]
Description=SignAgent Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/Users/zqy/work/AI-Project/SignAgent
ExecStart=/usr/bin/python3 main_feishu_sdk.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable signagent
sudo systemctl start signagent
sudo systemctl status signagent
```

## 相关链接

- [Claude Code SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [飞书开放平台](https://open.feishu.cn/)
- [飞书 SDK 文档](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development)

## License

MIT
