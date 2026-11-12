# 任务

下面是两个互不共享实施范围的小任务。请分别给最小可用答复。没有工具，只根据材料写计划或补丁；不要声称已改文件或运行。

## A：新 CLI 参数

用户原话：“在 Python 标准库实现的 `taskcli.py` 上加 `--open-only`，仅影响 `list`：过滤 `done: true` 的项，保留未完成项原顺序。`add`、`done` 行为和 JSON 文件格式都不变。没这个参数就保持现在行为。输入损坏按现有退出码 2 与 stderr 提示处理。不要加依赖，也不要网页。”

现有命令：`python taskcli.py list --file tasks.json`。每个记录必有 `id`、`title`、`done`。已知输入 `[ {"id":1,"title":"A","done":true}, {"id":2,"title":"B","done":false}, {"id":3,"title":"C","done":false} ]`。负责人只需要一段可交给主编码的范围和验收，不要求设计内部函数名。

## B：局部改字

用户原话：“只把确认弹窗里按钮‘确定删除’改成‘删除此条’，并让这个按钮的无障碍名字相同；其余不要动。” 当前文件 `ConfirmDelete.jsx` 全文：

```jsx
export function ConfirmDelete({ onDelete, onCancel }) {
  return <dialog open aria-label="删除确认">
    <p>此操作无法撤销。</p>
    <button className="danger" aria-label="确定删除" onClick={onDelete}>确定删除</button>
    <button onClick={onCancel}>取消</button>
  </dialog>;
}
```

## 输出

不超过 350 字加必要补丁。A：`目标/范围/验收/是否需澄清及理由`。B：仅给最小 unified diff 和一句核对说明。不要做 UI 设计、视觉审计、浏览器依赖探测或增设用户没有要求的审批步骤。
