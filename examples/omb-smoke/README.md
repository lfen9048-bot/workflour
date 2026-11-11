# textstats —— 统计文本文件的行数和字符数

一个小到可以一眼看完的命令行工具：读入一个 UTF-8 文本文件，把「多少行、多少个字符」以 JSON 打印到标准输出。适合放进脚本里做检查（比如「这篇稿子够不够 800 字」），也可以当作 Python 命令行程序 + 单元测试的入门范例。

本目录所有示例输出都是在 macOS + Python 3.14.7 上实际运行得到的原始输出，可以直接照着复现。

## 1. 用途

- 统计一个文本文件的**行数**（`lines`）和**字符数**（`characters`）。
- 结果是一个单行 JSON，方便被其它脚本用 `json.loads` 直接解析。
- 出错时不会静默失败：往 stderr 写明原因，并返回非零退出码。

它**不做**的事：不统计单词数、不区分中英文、不判断文件是否为二进制、不读标准输入。

## 2. 运行要求

| 项目 | 要求 |
|---|---|
| Python | 3.9 及以上即可（已在 3.9.6、3.12.14、3.14.7 上实测通过） |
| 第三方库 | 无，只用标准库 `json`、`sys` |
| 输入文件 | 必须是**合法的 UTF-8** 文本，否则报错退出（见第 5 节） |
| 操作系统 | 脚本没有平台相关代码，Windows 的 `\r\n` 换行也能正确处理（见 4.3）。本次实测环境是 macOS |

## 3. 命令

在本目录（`examples/omb-smoke`）下执行：

```bash
# 统计示例文件
python3 textstats.py sample.txt

# 统计任意 UTF-8 文本（相对路径、绝对路径、含空格或中文的路径都可以）
python3 textstats.py ~/Documents/稿子.txt
```

参数只有一个：文件路径。不给参数或给多个参数都会打印用法并以退出码 `2` 结束。

本目录内的完整文件清单：

| 文件 | 作用 |
|---|---|
| `textstats.py` | 主程序 |
| `test_textstats.py` | 单元测试（4 个用例） |
| `sample.txt` | 示例输入，供本文档复现 |
| `HANDOFF.md` | 编码方留下的交接说明（改动清单、原始测试记录） |
| `README.md` | 本文档 |

## 4. 输出说明

### 4.1 实际输出

```console
$ python3 textstats.py sample.txt
{"lines": 3, "characters": 18}
```

退出码 `0`。JSON 是**单行**输出，末尾带一个换行；键的顺序固定为 `lines` 在前、`characters` 在后。

### 4.2 两个字段的精确定义

`sample.txt` 的内容是：

```
hello
world
你好，世界
```

共 3 行文字，每行结尾都有一个换行符。

| 字段 | 定义 | 本例为何是这个数 |
|---|---|---|
| `lines` | `len(text.splitlines())`，即按行切分后的行数 | 3 行文字 → `3`。末尾那个换行符**不会**额外算出一个空行 |
| `characters` | `len(text)`，即解码后整个字符串的长度，**包含换行符** | hello(5) + `\n`(1) + world(5) + `\n`(1) + 你好，世界(5) + `\n`(1) = `18` |

所以「3 行、18 个字符」并不矛盾：18 里面有 3 个是换行符，真正的可见字符是 15 个。这也解释了为什么它和 `wc -c` 的 28 不一样 —— `wc -c` 数的是**字节**，一个汉字在 UTF-8 里占 3 个字节，5 个汉字就是 15 字节。

> 一句话记住：`lines` 数「行」，`characters` 数「字符 + 换行符」，不是字节数。

### 4.3 几个边界情况的实际结果

| 文件内容 | 输出 | 说明 |
|---|---|---|
| 空文件（0 字节） | `{"lines": 0, "characters": 0}` | 空文件算 0 行 |
| `abc`（无结尾换行） | `{"lines": 1, "characters": 3}` | 最后一行没有换行符也算一行 |
| `\n`（只有一个换行） | `{"lines": 1, "characters": 1}` | 一个空行 |
| `\n\n` | `{"lines": 2, "characters": 2}` | 两个空行 |
| `a\r\nb\r\n`（Windows 换行） | `{"lines": 2, "characters": 4}` | 见下方说明 |

关于 Windows 换行（`\r\n`）：程序用文本模式打开文件，Python 会自动把 `\r\n` 归一化成 `\n`，所以 4 个字符是 `a`、`\n`、`b`、`\n`，行数也正常是 2。单独一个 `\r`（老式 Mac 换行）同样会被归一化。

## 5. 错误情况

出错时**标准输出为空**，错误信息写到 stderr，进程以非零退出码结束。这一点对脚本很重要：判断成功与否请看退出码，不要看输出里有没有「错误」两个字。

| 情况 | stderr 实际内容 | 退出码 |
|---|---|---|
| 没给参数 | `用法: python3 textstats.py <文件路径>` | 2 |
| 给了多个参数 | `用法: python3 textstats.py <文件路径>` | 2 |
| 文件不存在 | `错误: 文件不存在: nope.txt` | 1 |
| 路径是目录 | `错误: 路径是一个目录而不是文件: /tmp/tsdir` | 1 |
| 不是合法 UTF-8 | `错误: 文件不是合法的 UTF-8 编码: /tmp/bad.bin ('utf-8' codec can't decode byte 0xff in position 0: invalid start byte)` | 1 |
| 打开失败且不属于上面几种（权限不足、符号链接成环等） | `错误: 无法读取文件: /tmp/noperm.txt ([Errno 13] Permission denied: '/tmp/noperm.txt')` | 1 |

调用示例（含真实输出）：

```bash
$ python3 textstats.py 不存在.txt
错误: 文件不存在: 不存在.txt          # 这行在 stderr
$ echo $?
1
```

括号里的内容是 Python 原始异常的文本，随系统和文件不同而变化，做自动化判断时不要去匹配它，匹配前面的中文前缀就够了。

### 在脚本里调用

用 `subprocess` 调用，靠退出码判断成败，成功后再解析 JSON：

```python
import json
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "textstats.py", "sample.txt"],
    capture_output=True,
    text=True,
)

if proc.returncode != 0:
    print("统计失败:", proc.stderr.strip())
else:
    stats = json.loads(proc.stdout)
    print(f"{stats['lines']} 行, {stats['characters']} 字符")
```

实际输出：

```console
3 行, 18 字符
```

## 6. 测试方法

在 `examples/omb-smoke` 目录下执行：

```bash
python3 -m unittest test_textstats.py -v
```

实际输出（用例顺序按字母排序，耗时每次略有不同）：

```console
test_chinese_text (test_textstats.TextStatsTest.test_chinese_text)
中文: 中文字符按字符数计（每个汉字算 1 个字符）。 ... ok
test_empty_text (test_textstats.TextStatsTest.test_empty_text)
空文本: 0 行，0 字符。 ... ok
test_english_multiline (test_textstats.TextStatsTest.test_english_multiline)
英文多行: splitlines 计行，字符数包含换行符。 ... ok
test_file_not_found (test_textstats.TextStatsTest.test_file_not_found)
文件不存在: 非零退出码，stderr 有错误信息，stdout 为空。 ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.084s

OK
```

退出码 `0`。去掉 `-v` 就是紧凑的点号输出，结果相同：

```console
....
----------------------------------------------------------------------
Ran 4 tests in 0.083s

OK
```

四个用例分别覆盖：空文件、英文多行（`hello\nworld\n` → 2 行 12 字符）、中文（`你好世界\n再见\n` → 2 行 8 字符）、文件不存在（非零退出码 + stderr 有「不存在」+ stdout 为空）。

**测试实现的要点**（读代码时用得上）：每个用例把内容写进临时文件，再用 `subprocess` 起一个真实子进程运行 `textstats.py`，所以测的是命令行行为本身，而不只是内部函数。被测脚本路径由 `__file__` 推导，不依赖当前目录。

> 注意：`python3 -m unittest test_textstats.py` 需要**在本目录下**执行。在别的目录里写绝对路径（`python3 -m unittest /绝对路径/test_textstats.py`）会报 `ModuleNotFoundError` —— 这是 unittest 按模块名导入的规则所致，不是测试写错了。要在别的目录跑，用：
>
> ```bash
> python3 -m unittest discover -s /绝对路径/omb-smoke -t /绝对路径/omb-smoke
> ```

## 7. 已知限制

以下都是当前实现的真实行为，不是猜想，用的时候心里有数即可：

| 现象 | 实际表现 | 原因 |
|---|---|---|
| 带 BOM 的 UTF-8 文件 | `hello\n` 带 BOM 时输出 `{"lines": 1, "characters": 7}`，比预期多 1 | 用 `encoding="utf-8"` 打开，BOM 被当成一个字符计入。Windows 记事本另存的 UTF-8 常带 BOM |
| emoji / 组合字符 | `👨‍👩‍👧\n` 输出 6 个字符；`café` 用组合写法（NFD）比预组合写法（NFC）多 1 | `len()` 数的是 Unicode 码位，不是「看起来的一个字」 |
| 分隔符 | `a\vb`、`a\fb`、`a\x1cb`、含 U+2028 的文本都会被算成 2 行 | `splitlines()` 认多种 Unicode 行分隔符，不只是 `\n` |
| 二进制文件 | 只要字节恰好是合法 UTF-8 就会当文本统计，不报错 | 没有二进制检测 |
| `--help` | 被当成文件名，报 `错误: 文件不存在: --help`，退出码 1 | 没有实现参数解析 |
| 空字符串路径 | `python3 textstats.py ""` 报 `错误: 文件不存在: `（路径为空） | 空串走到「文件不存在」分支，提示略含糊 |
| 标准输入 | 不支持 `-`，`echo hi \| python3 textstats.py -` 报文件不存在 | 只接受文件路径 |

## 8. 相关文档

- `HANDOFF.md` —— 编码方的交接记录：改动文件清单、原始测试粘贴、输入输出约定。
