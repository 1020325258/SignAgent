"""
签约助手启动脚本

支持三种模式：
1. API 模式：提供 HTTP API
2. 飞书模式：对接飞书机器人（使用 lark-cli）
3. 交互模式：命令行交互
"""

import argparse
import asyncio
import sys
import os

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent import SignAgent
from src.api import start_server as start_api_server


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="签约助手")
    parser.add_argument(
        "--mode",
        choices=["api", "feishu", "interactive"],
        default="api",
        help="运行模式: api (HTTP API) 或 feishu (飞书机器人) 或 interactive (交互模式)",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="签约系统项目目录",
    )
    parser.add_argument(
        "--chat-id",
        help="飞书聊天 ID（feishu 模式必需）",
    )

    args = parser.parse_args()

    # 初始化 Agent
    api_config = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-8"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
    }

    agent = SignAgent(
        project_dir=args.project_dir,
        api_config=api_config,
    )

    if args.mode == "api":
        start_api_server()
    elif args.mode == "feishu":
        if not args.chat_id:
            print("❌ feishu 模式需要指定 --chat-id 参数")
            sys.exit(1)
        from src.feishu_larkcli import start_feishu_bot
        start_feishu_bot(agent, args.chat_id)
    elif args.mode == "interactive":
        run_interactive(agent)


def run_interactive(agent: SignAgent):
    """交互模式"""
    print("🤖 签约助手已启动（交互模式）")
    print("输入问题进行对话，输入 'quit' 退出")
    print("-" * 50)

    while True:
        try:
            question = input("\n📝 您的问题: ").strip()

            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 再见！")
                break

            if not question:
                continue

            print("\n🔍 正在分析...")
            asyncio.run(agent.chat_and_print(question))

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()
