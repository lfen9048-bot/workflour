# 任务

请独立审核这次“保存草稿”改动，仅使用下面材料。没有工具，不要声称运行测试。最多报告三个具有具体证据的问题；可以得出没有问题，区分缺陷与测试建议。正常取消与非必需预览均是已确认产品行为。

## 契约

- 用户主动取消：返回 `cancelled`，不调用写入，不显示错误。
- 写入失败：返回 `error`，不能显示保存成功；不得改旧草稿。
- 写入成功后返回 `saved`。
- 缩略预览是可选扩展；未安装扩展时返回空预览，保存功能仍可正常工作。已有扩展运行出错不是“未安装”。

## 完整被审代码

```python
def save(text, *, cancelled, writer):
    if cancelled:
        return {"state": "cancelled"}
    try:
        writer(text)  # writer 契约：失败抛 OSError，旧文件不变
    except OSError:
        pass
    return {"state": "saved"}

def preview(text, plugin=None):
    if plugin is None:
        return ""
    return plugin.render(text)
```

## 当前测试与执行记录

```python
def test_saved():
    writes = []
    assert save("draft", cancelled=False, writer=writes.append) == {"state": "saved"}
    assert writes == ["draft"]

def test_cancelled():
    def unexpected(_): raise AssertionError("writer called")
    assert save("draft", cancelled=True, writer=unexpected) == {"state": "cancelled"}

def test_no_preview():
    assert preview("draft") == ""
```

维护者提供的日志：以上 3 项测试通过。未提供其他执行记录。

## 输出

按 `结论 / 实际缺陷（触发→实际→要求） / 合法行为 / 最小补测 / 证据限制` 输出，总计不超过 400 字。不能将建议补充的测试写成原测试已经执行过。
