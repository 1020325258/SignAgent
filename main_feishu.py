"""
SignAgent 飞书 Webhook 服务

直接对接飞书开放平台，接收消息并回复。
"""

import os
import sys
from fastapi import FastAPI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent import SignAgent
from src.feishu_webhook import FeishuWebhook

# 创建 FastAPI 应用
app = FastAPI(
    title="SignAgent - 签约助手",
    description="基于 Claude Code SDK 的签约系统智能助手",
    version="1.0.0",
)


def create_agent() -> SignAgent:
    """创建 SignAgent 实例"""
    project_dir = os.getenv("SIGN_AGENT_PROJECT_DIR", ".")
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    return SignAgent(project_dir=project_dir, api_config=api_config)


# 初始化 Agent
agent = create_agent()

# 初始化飞书 Webhook
feishu_webhook = FeishuWebhook(app, agent)


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "service": "SignAgent",
        "description": "签约系统智能助手"
    }


def start_server():
    """启动服务器"""
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  服务地址: http://{host}:{port}                            ║
║  健康检查: http://{host}:{port}/health                     ║
║  Webhook:  http://{host}:{port}/webhook/event              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
