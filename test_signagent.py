"""
SignAgent 测试脚本

模拟飞书发消息，测试 SignAgent 的功能。
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent import SignAgent


async def test_signagent():
    """测试 SignAgent"""
    print("=" * 60)
    print("SignAgent 测试")
    print("=" * 60)

    # 初始化 Agent
    project_dir = os.getenv("SIGN_AGENT_PROJECT_DIR", ".")
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(project_dir=project_dir, api_config=api_config)
    print(f"✅ Agent 初始化完成")
    print(f"📁 项目目录: {project_dir}")
    print()

    # 测试问题列表
    test_questions = [
        "你好",
        "这个项目的目录结构是怎样的？",
        "SignAgent 是什么？",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"{'=' * 60}")
        print(f"测试 {i}/{len(test_questions)}")
        print(f"问题: {question}")
        print(f"{'=' * 60}")

        try:
            # 收集所有输出
            all_chunks = []
            thinking_steps = []
            final_answer = []

            async for text in agent.chat(question=question):
                all_chunks.append(text)

                # 判断是否是思考过程（工具调用信息）
                if text.startswith("\n📄") or text.startswith("\n🔍") or text.startswith("\n💻") or text.startswith("\n📁"):
                    thinking_steps.append(text.strip())
                elif text.startswith("\n💰"):
                    # 费用信息
                    final_answer.append(text)
                else:
                    final_answer.append(text)

            # 输出结果
            print()
            if thinking_steps:
                print("📝 思考过程:")
                for step in thinking_steps:
                    print(f"  {step}")
                print()

            print("💬 回复:")
            print("".join(final_answer))
            print()

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

        print()

    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_signagent())
