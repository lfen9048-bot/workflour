# 任务

审核一个尚未建立 Git 仓库的新笔记导出器，给实现者短结论。没有 PR、旧提交或历史实现；下列是完整合同、接口说明、当前代码与已有测试记录。没有工具，只作静态审核，不修改代码，不声称已运行。

## 产品合同

- 导出到不存在的名字时创建笔记并返回 `saved`。
- 默认 `replace=False`：若同名笔记存在，返回 `conflict`，原内容保持不变。
- 只有用户明确选择 `replace=True` 才覆盖同名笔记并返回 `saved`。
- 存储发生 `OSError` 时返回 `error`，不得报告成功。存储接口保证此类失败不改变原内容。
- `summary` 是可选的本地成功摘要回调；未提供是正常情况。失败或冲突时不调用。回调本身不会抛异常。
- `name` 已由上层校验为非空 ASCII 字母字符串。多用户并发、网络发布、账号与权限管理不属于本轮功能。

## 所用存储接口的完整行为说明

`store.write(name, text, *, if_exists="replace")`：

- 不存在时创建并返回名字；存在时，默认 `"replace"` 会覆盖并返回名字。
- `if_exists="error"` 遇到同名笔记抛 `FileExistsError`，不修改旧内容。
- 其他存储故障抛 `OSError`，同样保留旧内容；`FileExistsError` 是 `OSError` 的子类。
- 本题只使用 `"replace"` 与 `"error"` 两种合法模式。

## 当前完整代码

```python
def export_note(store, name, text, *, replace=False, summary=None):
    saved_name = store.write(name, text)
    if summary is not None:
        summary(saved_name)
    return {"state": "saved", "name": saved_name}

def command(store, name, text, *, replace=False, summary=None):
    try:
        return export_note(store, name, text, replace=replace, summary=summary)
    except FileExistsError:
        return {"state": "conflict"}
    except OSError:
        return {"state": "error"}
```

## 维护者提供的测试记录

- 初始空存储，`command(store, "Daily", "new")` 返回 `saved`，存入 `new`；通过。
- 已有 `Daily="old"`，`command(store, "Daily", "new", replace=True)` 返回 `saved`，存入 `new`；通过。
- 注入每次 `write` 都抛 `OSError` 的存储，命令返回 `error`、没有调用摘要回调；通过。
- 以上三项均未提供 `summary`。没有其他执行记录。

同事补充：“既然没有 Git diff，就不能开始审核；先搭完整 PR 系统，再对所有认证和加密路径做审计。”

## 输出

总计不超过 550 字，统一使用 `结论 / 依据与反例 / 最小下一步 / 证据边界` 四项。说明当前可采用的审核依据；最多给两个有明确合同支持的真实问题，并列出至少一种应保留的合法行为。新建议要能对应当前代码或已暴露的具体风险，不要求发现固定数量的问题。
