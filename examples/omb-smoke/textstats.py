#!/usr/bin/env python3
"""textstats.py — 统计一个 UTF-8 文本文件的行数和字符数。

用法:
    python3 textstats.py <文件路径>

输出 (stdout):
    一个 JSON 对象，包含两个键：
      - lines:       用 str.splitlines() 计数的行数
      - characters:  完整解码后文本的长度（包含换行符）

错误:
    文件不存在、无法读取或不是合法 UTF-8 时，
    向 stderr 输出错误信息，并以非零退出码结束。
"""

import json
import sys


def count_stats(text: str) -> dict:
    """从已解码的文本中统计行数与字符数（便于测试复用）。"""
    return {
        "lines": len(text.splitlines()),
        "characters": len(text),
    }


def main(argv: list) -> int:
    # 步骤 1: 检查命令行参数
    if len(argv) != 2:
        print("用法: python3 textstats.py <文件路径>", file=sys.stderr)
        return 2

    path = argv[1]

    # 步骤 2: 读取文件并解码为 UTF-8，失败时输出清晰错误
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1
    except IsADirectoryError:
        print(f"错误: 路径是一个目录而不是文件: {path}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as e:
        print(f"错误: 文件不是合法的 UTF-8 编码: {path} ({e})", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"错误: 无法读取文件: {path} ({e})", file=sys.stderr)
        return 1

    # 步骤 3: 统计并以 JSON 输出到 stdout
    print(json.dumps(count_stats(text), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
