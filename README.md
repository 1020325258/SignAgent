# SignAgent - 签约系统助手

基于 Claude Code SDK 的签约系统智能助手，通过 cc-connect 连接飞书机器人，实现智能问答。

## 架构说明

```
用户 (飞书) → 飞书机器人 → cc-connect → Claude Code → 签约系统代码
```

- **Claude Code**: AI 编程助手，负责理解问题并分析代码
- **cc-connect**: 桥接工具，连接飞书和 Claude Code
- **SignAgent**: 签约系统项目目录，包含业务代码

## 前置条件

- Node.js 18+
- Claude Code CLI
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

### 2. 安装 cc-connect

```bash
npm install -g cc-connect
```

验证安装：
```bash
cc-connect --version
```

### 3. 配置飞书机器人

运行以下命令，会弹出二维码，用飞书 App 扫码完成授权：

```bash
cc-connect feishu setup --project sign-agent
```

扫码完成后，配置会自动写入 `~/.cc-connect/config.toml`。

### 4. 配置项目目录

编辑 `~/.cc-connect/config.toml`，确保项目配置正确：

```toml
[log]
level = "info"

[[projects]]
name = "sign-agent"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/zqy/work/AI-Project/SignAgent"  # 你的项目路径
mode = "default"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_xxxxxxxxxxxx"        # 飞书应用 ID
app_secret = "xxxxxxxxxxxxxxxx"    # 飞书应用密钥
```

**配置说明：**

| 配置项 | 说明 |
|--------|------|
| `work_dir` | 签约系统项目目录的绝对路径 |
| `mode` | Claude Code 权限模式：`default` / `acceptEdits` / `plan` / `auto` |
| `app_id` | 飞书应用 ID（扫码授权时自动生成） |
| `app_secret` | 飞书应用密钥（扫码授权时自动生成） |

**权限模式说明：**

| 模式 | 说明 |
|------|------|
| `default` | 默认模式，需要确认工具调用 |
| `acceptEdits` | 自动接受文件编辑，其他需要确认 |
| `plan` | 计划模式，只读不写 |
| `auto` | 自动模式，跳过所有确认（谨慎使用） |

## 启动服务

### 方式 1：前台运行（推荐开发调试）

在终端中运行：

```bash
cc-connect
```

### 方式 2：后台运行（推荐生产环境）

```bash
# 安装为系统服务
cc-connect daemon install --config ~/.cc-connect/config.toml

# 启动服务
cc-connect daemon start

# 查看状态
cc-connect daemon status

# 查看日志
cc-connect daemon logs -f

# 停止服务
cc-connect daemon stop
```

### 启动成功标志

看到以下日志表示启动成功：

```
level=INFO msg="platform started" project=sign-agent platform=feishu
level=INFO msg="engine started" project=sign-agent agent=claudecode platforms=1
level=INFO msg="cc-connect is running" projects=1
```

## 使用方法

### 在飞书中与机器人对话

1. 打开飞书 App
2. 找到你创建的机器人
3. 直接发送消息即可

### 常用对话示例

```
# 询问签约流程
签约系统有哪些合同模板？

# 分析代码
帮我分析一下合同签署的流程

# 排查问题
签约失败是什么原因？

# 代码相关
这个项目的目录结构是怎样的？
```

### 聊天命令

在飞书中可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/new [name]` | 开始新会话 |
| `/list` | 列出所有会话 |
| `/switch <id>` | 切换到指定会话 |
| `/current` | 显示当前会话 |
| `/history [n]` | 显示最近 n 条消息（默认 10） |
| `/mode [name]` | 切换权限模式 |
| `/stop` | 停止当前执行 |
| `/help` | 显示帮助信息 |

### 权限确认

当 Claude Code 需要执行工具时，会请求权限：

- 回复 `allow` 或 `允许` — 批准本次请求
- 回复 `deny` 或 `拒绝` — 拒绝本次请求
- 回复 `allow all` 或 `允许所有` — 本会话自动批准所有请求

## 项目结构

```
SignAgent/
├── src/                    # 源代码（如果需要自定义）
├── tests/                  # 测试代码
├── sdk-reference/          # Claude Agent SDK 参考
├── docs/                   # 文档
├── config/                 # 配置示例
└── README.md               # 本文件
```

## 配置文件位置

| 文件 | 位置 | 说明 |
|------|------|------|
| cc-connect 配置 | `~/.cc-connect/config.toml` | 主配置文件 |
| Claude Code 配置 | `~/.claude/` | Claude Code 配置目录 |
| 项目 CLAUDE.md | `SignAgent/CLAUDE.md` | 项目级 Claude 指令（可选） |

## 高级配置

### 添加项目级 Claude 指令

在项目根目录创建 `CLAUDE.md` 文件，添加项目特定的指令：

```markdown
# SignAgent 项目指令

你是一个签约系统助手，专门帮助用户理解和使用签约系统。

## 职责
1. 回答关于签约流程、合同模板、签约状态等问题
2. 解释系统功能和操作步骤
3. 协助排查签约相关的问题

## 注意事项
- 只读操作，不会修改任何代码
- 引用具体的文件路径和代码行号
- 提供准确的业务术语解释
```

### 多项目配置

如果需要管理多个项目，编辑 `~/.cc-connect/config.toml`：

```toml
# 项目 1：签约系统
[[projects]]
name = "sign-agent"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/zqy/work/AI-Project/SignAgent"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_xxx"
app_secret = "xxx"

# 项目 2：其他项目
[[projects]]
name = "other-project"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/path/to/other/project"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_yyy"
app_secret = "yyy"
```

### 切换 API 提供商

如果需要使用不同的 API 提供商：

```bash
# 查看当前提供商
/provider list

# 添加新提供商
/provider add <name> <api-key>

# 切换提供商
/provider switch <name>
```

## 故障排查

### 问题：机器人没有回复

1. 检查 cc-connect 是否正在运行：
   ```bash
   cc-connect daemon status
   ```

2. 查看日志：
   ```bash
   cc-connect daemon logs -f
   ```

3. 确认飞书应用已发布并启用

### 问题：权限错误

确保飞书应用有以下权限：
- `im:message.receive_v1` — 接收消息
- `im:message:send_as_bot` — 发送消息

### 问题：Claude Code 未找到

```bash
# 检查 Claude Code 是否安装
claude --version

# 如果未安装
npm install -g @anthropic-ai/claude-code
```

### 问题：会话冲突

如果提示 "session already in use"：

```
/new
```

开始一个新会话。

## 常用命令参考

```bash
# cc-connect 版本
cc-connect --version

# 启动服务
cc-connect

# 后台服务管理
cc-connect daemon install --config ~/.cc-connect/config.toml
cc-connect daemon start
cc-connect daemon stop
cc-connect daemon restart
cc-connect daemon status
cc-connect daemon logs -f

# 飞书配置
cc-connect feishu setup --project sign-agent

# 升级
npm update -g cc-connect
```

## 相关链接

- [cc-connect GitHub](https://github.com/chenhg5/cc-connect)
- [Claude Code 文档](https://docs.anthropic.com/claude-code)
- [飞书开放平台](https://open.feishu.cn/)

## License

MIT
