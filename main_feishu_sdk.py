"""
SignAgent 飞书 SDK 长连接服务

使用飞书官方 SDK 的长连接方式，无需公网 IP。
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.feishu_sdk import start_feishu_sdk


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    SignAgent 签约助手                        ║
╠══════════════════════════════════════════════════════════════╣
║  启动方式: 飞书 SDK 长连接                                   ║
║  优势: 无需公网 IP，无需 ngrok                               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    start_feishu_sdk()


if __name__ == "__main__":
    main()
