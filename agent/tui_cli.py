#!/usr/bin/env python3
"""DeepPulse TUI模式启动入口"""

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.client import load_setting
from agent.tui.app import run_tui


def main():
    """TUI模式主函数"""
    parser = argparse.ArgumentParser(description="DeepPulse - TUI模式")
    parser.add_argument("--model", type=str, help="覆盖配置中的模型名称")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--no-judge", action="store_true", help="禁用评判Agent")

    args = parser.parse_args()

    # 加载配置
    try:
        setting = load_setting()
    except FileNotFoundError:
        print("❌ 未找到 setting.json，请先配置 LLM")
        print("💡 提示: 复制 setting.example.json 为 setting.json 并填入 API Key")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        sys.exit(1)

    # 覆盖模型
    if args.model:
        setting["llm"]["model"] = args.model

    # 禁用评判Agent（通过环境标记）
    if args.no_judge:
        setting["agent"]["enable_judge"] = False
    else:
        setting["agent"]["enable_judge"] = True

    print("✨ 正在启动 DeepPulse TUI...")
    print("💡 提示: Ctrl+Q 退出, Ctrl+R 重置对话, Ctrl+L 清屏")
    print()

    # 启动TUI
    try:
        run_tui(setting=setting, verbose=args.verbose)
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
