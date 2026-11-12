# 任务

审核下面预约系统的库存更新逻辑与测试。材料足够进行静态判断，但没有工具，不能声称执行。产品没有要求新增 UI、日志平台或测试库。

## 契约

- `quantities` 为仓库中的可用件数，ID 为字符串，数量为非负整数。
- 一批预约全部满足才扣库存并返回 `reserved`；任意项不足或 ID 未知，返回 `unavailable`，整批库存必须保持原值。
- 同一个 ID 可在一批中出现多次，表示多笔数量，要累计检查。
- 用户确认前取消返回 `cancelled`，库存不变。`audit_sink` 是可选扩展；不提供时预约依然有效。

## 完整代码

```python
def reserve(quantities, requests, *, confirmed=True, audit_sink=None):
    if not confirmed:
        return "cancelled"
    for item, amount in requests:
        if amount > quantities.get(item, -1):
            return "unavailable"
        quantities[item] -= amount
    if audit_sink is not None:
        audit_sink(tuple(requests))
    return "reserved"
```

## 当前测试及日志

```python
def test_reserved_without_audit():
    stock = {"a": 3}
    assert reserve(stock, [("a", 2)]) == "reserved"
    assert stock == {"a": 1}

def test_cancel():
    stock = {"a": 3}
    assert reserve(stock, [("a", 2)], confirmed=False) == "cancelled"
    assert stock == {"a": 3}

def test_repeated_item():
    stock = {"a": 5}
    assert reserve(stock, [("a", 1), ("a", 2)]) == "reserved"
    assert stock == {"a": 3}
```

日志：第 1、2 项通过，第 3 项失败：实际 `{'a': 2}`，预期 `{'a': 3}`。没有整批不足场景的执行证据。

## 输出

最多 450 字：`业务缺陷 / 测试本身问题 / 最小可复现输入与预期 / 已有合法行为 / 结论限制`。每项明确证据来自代码、已有日志还是你建议的新测试；不要为迎合错误断言改变已确认的数量规则。
