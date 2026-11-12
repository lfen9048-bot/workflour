# 任务

评估两个组件的性质测试设计。它们是同一题的两个子题，不要求安装库或运行代码；请从契约判断哪些性质有效、单独不足、或不符合契约。给小的具体反例或独立样例，不要声称测试已执行。

## A：外部计数帧

正式格式为：2 字节无符号长度，**网络字节序（大端）**，随后原样拼接每个 1 字节事件码。事件码为 0–255，长度不超过 65535，重复事件有意义，输入列表不能被修改。空帧长度字段为 0。

```python
def encode(items):
    return len(items).to_bytes(2, "little") + bytes(items)

def decode(frame):
    n = int.from_bytes(frame[:2], "little")
    if len(frame) != n + 2:
        raise ValueError("length mismatch")
    return list(frame[2:])

def round_trip(items):
    return decode(encode(items)) == items
```

现有有限检查对 `[ ]`、`[7]`、`[7,7,2]` 的 `round_trip` 都为真。团队因此提出：“两端互逆即可证明符合外部格式，重复项也不用另外考虑。”

## B：显示标签

契约明确允许丢弃首尾空白、把任意连续空白合并为一个 ASCII 空格并用 `casefold()` 统一大小写；输入只含 ASCII 字母与 ASCII 空白。不能丢掉字母或改变字母次序。这是显示标签，不用于身份验证或安全过滤。

```python
def canonical(text):
    return " ".join(text.split()).casefold()
```

拟用性质：
1. `canonical(canonical(x)) == canonical(x)`。
2. `canonical(x) == x`，因为应保留输入。
3. 只要不抛异常就认为实现正确。
4. 结果不含首尾/连续空白，而且除空白及大小写外的 ASCII 字母序列保留。

## 输出

最多 550 字。按 `A现有证据限制 / A独立约束与具体样例 / B逐条判断 / 无新依赖的有限验证方案 / 未验证范围` 输出。准确区分有效但不足的性质、错误性质和固定样例；不能把有限枚举说成已证明所有输入。
