# 任务

用户：“把今天 Alpha 项目已经确认的验收进度记到知识库，其他项目不要动。还没确认的事标明，不要帮我验收。” 当前没有工具，请给最小拟修改内容，不能声称已写入文件。

知识库目录清单及完整相关内容如下。当前项目为 `Alpha`，项目手写区 `Projects/Alpha/`。`Auto/` 是只读观察器生成区。

## 当前事实

任务 `A-12`：实现报告与技术审核已回传；测试记录 `evidence/test-a12.json` 显示 18 项通过；Plan 正在核对体验，尚未提供体验结论；用户没有验收。用户今天只提出“将来可能加导出”，没有确认将它加入 A-12。

## 文件

`Projects/Alpha/Status.md`
```markdown
---
project: Alpha
owner: Lin
tags: [project, active]
---
# Alpha 进度
当前：实施中。
需求：[[Requirements#A-12]]
个人备注：下周与客户约时间，保留此句。
```

`Projects/Alpha/Requirements.md`
```markdown
# 需求
## A-12
本轮：未完成筛选、刷新后保存选择。
```

`Projects/Beta/Status.md`
```markdown
# Beta
当前：等待报价。
```

`Auto/Alpha.md`
```markdown
# 自动状态
阶段: review
生成时间: 2026-11-11 20:01
```

## 输出

最多 400 字加必要修改片段：`拟修改路径 / 最小内容改动 / 状态依据与未确认项 / 保留边界`。已有元数据、链接和个人备注应保留；自动区若落后，说明差异而不是手改。不要创建全库索引、迁移目录、把愿望写成已立项，或新增其他项目任务。
