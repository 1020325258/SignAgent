"""
签约助手 API 服务

提供 HTTP API 接口，支持飞书 cc-connect 集成。
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from .agent import SignAgent

# 加载环境变量
load_dotenv()

# 创建 FastAPI 应用
app = FastAPI(
    title="签约助手 API",
    description="基于 Claude Code SDK 的签约系统智能助手",
    version="1.0.0",
)

# 全局 Agent 实例
agent: SignAgent = None


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    allowed_tools: list[str] = ["Read", "Glob", "Grep", "Bash"]


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str
    cost_usd: float = 0.0


class ContractAnalysisRequest(BaseModel):
    """合同分析请求"""
    contract_type: str


class SignFlowRequest(BaseModel):
    """签约流程解释请求"""
    flow_name: str


class TroubleshootRequest(BaseModel):
    """问题排查请求"""
    issue_description: str


@app.on_event("startup")
async def startup():
    """应用启动时初始化 Agent"""
    global agent

    project_dir = os.getenv("SIGN_SYSTEM_PROJECT_DIR", ".")
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config)
    print(f"✅ 签约助手已启动，项目目录: {project_dir}")


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "签约助手"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    与签约助手对话

    Args:
        request: 聊天请求

    Returns:
        聊天响应
    """
    if not agent:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    try:
        result = []
        async for text in agent.chat(
            question=request.question,
            allowed_tools=request.allowed_tools,
        ):
            result.append(text)

        return ChatResponse(answer="".join(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-contract", response_model=ChatResponse)
async def analyze_contract(request: ContractAnalysisRequest):
    """
    分析合同模板

    Args:
        request: 合同分析请求

    Returns:
        分析结果
    """
    if not agent:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    try:
        result = await agent.analyze_contract(request.contract_type)
        return ChatResponse(answer=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/explain-flow", response_model=ChatResponse)
async def explain_flow(request: SignFlowRequest):
    """
    解释签约流程

    Args:
        request: 签约流程解释请求

    Returns:
        流程解释
    """
    if not agent:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    try:
        result = await agent.explain_sign_flow(request.flow_name)
        return ChatResponse(answer=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/troubleshoot", response_model=ChatResponse)
async def troubleshoot(request: TroubleshootRequest):
    """
    排查签约问题

    Args:
        request: 问题排查请求

    Returns:
        排查结果和建议
    """
    if not agent:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    try:
        result = await agent.troubleshoot(request.issue_description)
        return ChatResponse(answer=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start_server():
    """启动服务器"""
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))

    print(f"🚀 启动签约助手服务: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
