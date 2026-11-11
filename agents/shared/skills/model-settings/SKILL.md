---
name: model-settings
description: Show native model/thinking settings and apply explicitly submitted task or Bot defaults safely.
---

Use `/Users/a1/Documents/a/workflour/scripts/bot-model.py`, not hand edits to
profiles, native databases or global defaults. Discover actual Bot/thread IDs
and current settings first. Do not change anything on opening or cancellation.

For settings, run `python3 /Users/a1/Documents/a/workflour/scripts/bot-model.py widget --bot ID --thread ID
[--project PATH]` and pass its widget/fallback_text to the actual show_widget
tool. After model_settings_model is submitted, call widget with payload.bot,
payload.thread and --choice values.model_choice to render the model's actual
thinking tiers and scope. The model_settings_apply payload gives bot/thread/
instance/model/cross_runtime; its values give thinking/scope/project. Validate
against the live catalog, then call safe `switch` with those exact values.
Only scope=default adds --make-default; scope defaults to task. Do not execute
switch merely because the user picked a model on the first card.

Across DSH/Antigravity, switch creates a fresh task and a durable handoff. Send
its next_prompt to the returned new thread. Preserve the role in Bot soul and
project records, and keep the old task. Never invent unsupported thinking tiers.
The new task uses Ask approval; do not claim that it inherits the old Full
permission. The workbench header picker changes Bot defaults: use these safe
cards when the user wants only the current task to change.
Read back settings and report actual results without claiming inference access
to a model that has only been listed in a catalog.

Never loosen the busy-task guard. A Bot cannot synchronously change the task
currently executing its own settings turn. In the new team, 大管家 and 通用助手
handle settings directly without starting a Plan/Code project. Every Bot can
be a settings target. To configure 大管家, use 通用助手 after 大管家 is idle;
to configure 通用助手, use 大管家 after the assistant is idle. Legacy deployments
may use 项目总控 for the same operator role. For a self-target request,
explain this and give the other Bot's entry instead of applying to a busy task.
An independent idle settings task on the target Bot is also permitted when the
user explicitly requests one. No request for settings authorizes a coding job.
