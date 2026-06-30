"""
SignAgent 飞书 SDK 长连接服务

使用飞书官方 SDK 的长连接方式，无需公网 IP。
"""

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """配置日志：同时输出到控制台和 logs/ 目录。"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"signagent_{datetime.now():%Y%m%d}.log")

    # 根 logger，捕获所有模块的日志
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 文件 handler：DEBUG 级别，按天轮转，保留 7 天
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # 控制台 handler：INFO 级别
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info(f"日志输出到: {log_file}")


from src.feishu import start_feishu_sdk


def main():
    """主函数"""
    setup_logging()

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
