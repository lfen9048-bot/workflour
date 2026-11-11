#!/usr/bin/env python3
"""test_textstats.py — textstats.py 的单元测试。

覆盖四种情况:
  1. 空文本文件
  2. 英文多行文本
  3. 中文文本
  4. 文件不存在（应非零退出码并向 stderr 报错）
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# 被测脚本与本测试文件在同一目录
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textstats.py")


def run_script(path: str) -> subprocess.CompletedProcess:
    """以子进程方式运行 textstats.py，模拟真实命令行调用。"""
    return subprocess.run(
        [sys.executable, SCRIPT, path],
        capture_output=True,
        text=True,
    )


class TextStatsTest(unittest.TestCase):
    def _write_temp(self, content: str) -> str:
        """辅助: 把字符串写进一个临时 UTF-8 文件，返回其路径。"""
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_empty_text(self):
        """空文本: 0 行，0 字符。"""
        path = self._write_temp("")
        proc = run_script(path)
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data, {"lines": 0, "characters": 0})

    def test_english_multiline(self):
        """英文多行: splitlines 计行，字符数包含换行符。"""
        text = "hello\nworld\n"
        path = self._write_temp(text)
        proc = run_script(path)
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        # "hello\nworld\n".splitlines() -> ["hello", "world"] = 2 行
        self.assertEqual(data["lines"], 2)
        # 字符数 = 5 + 1 + 5 + 1 = 12（含换行符）
        self.assertEqual(data["characters"], 12)

    def test_chinese_text(self):
        """中文: 中文字符按字符数计（每个汉字算 1 个字符）。"""
        text = "你好世界\n再见\n"
        path = self._write_temp(text)
        proc = run_script(path)
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["lines"], 2)
        # 4 + 1 + 2 + 1 = 8
        self.assertEqual(data["characters"], 8)

    def test_file_not_found(self):
        """文件不存在: 非零退出码，stderr 有错误信息，stdout 为空。"""
        proc = run_script(os.path.join(tempfile.gettempdir(), "no_such_file_xyz.txt"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("不存在", proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
