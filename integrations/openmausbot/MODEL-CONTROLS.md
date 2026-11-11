# Bot model and thinking controls

The installed OpenMausBot custom ACP driver already supports models and model
variants. DSH exposes `reasoning_effort`; Antigravity exposes `thought_level`.
Both appear as model-specific thinking choices in the workbench. No installed
product files need modification.

## Safe native chat cards

Tell **大管家** or **通用助手** **打开模型设置**, or name the Bot you want to edit.
They handle settings directly; this does not start a Plan/Code project.
The operator shows a native chat card: choose the provider/model, then its
real thinking options and scope. Scope defaults to **仅当前任务**. A runtime
change also asks for or prefills the project directory and explains the fresh
task. Cancel or an unsubmitted card does not change settings.

The operator generates each card with `bot-model.py widget`. Its JSON output
is passed verbatim to `mcp__agents__show_widget`, not pasted as prose. When no
Bot was named the first card chooses one; when the Bot is known it proceeds
directly to the model picker. The model picker deduplicates catalogs, keeps the
current DSH role's profile, and chooses the neutral assistant profile when
switching from Antigravity to DSH.

For the new Plan/Code team, a temporary Antigravity task first offers the Bot's
own default DSH profile when it has one. A native Antigravity Bot instead uses
`omb-wf-assistant`, whose profile preserves the role/skill catalog supplied by
the workbench Bot and handoff. `omb-assistant` is only the compatibility fallback
on an installation without the new profile. This does not change any saved Bot
default or move an existing conversation.

Actions are `model_settings_target`, `model_settings_model`,
`model_settings_apply`, and `model_settings_cancel`. The first model submission
contains `values.model_choice`; pass it unchanged to `widget --choice`. The
apply action carries Bot/thread/instance/model in `payload` and thinking/scope/
project in `values`. The operator checks the live catalog and invokes the
safe `switch` command only after this submission. `scope=default` is the only
case that sets `--make-default`; absent or invalid scope must not apply anything.
The cards themselves never call an API or change model settings.
All Bots are valid targets. A Bot cannot edit the busy task that is currently
handling its own settings request: use 通用助手 for an idle 大管家, or 大管家
for an idle 通用助手. Do not stop work or bypass the guard just to change a model.

## Refresh and inspect

```sh
python3 scripts/bot-model.py refresh
python3 scripts/bot-model.py list
```

Refresh discovers each agent's real advertised catalog without sending a model
prompt. It creates temporary native sessions, which can appear in DSH history.
A catalog entry is not proof of login, quota, or successful inference. Check the
provider badge: WorkBuddy, WorkBuddy Global and DeepSeek official are different
routes. User-authorized quota fallback (2026-11-10) is now limited to the
DSH request-boundary chain in [model-fallback/README.md](model-fallback/README.md).
Do not silently invent other providers, or mistake a waiting notice for quota.

## Change one task

Use the exact catalog model ID and one of its own thinking IDs. For example:

```sh
python3 scripts/bot-model.py switch \
  --bot BOT_ID --thread THREAD_ID --instance omb-wf-assistant \
  --model '["workbuddy","deepseek-v4.1-flash"]' --thinking high
```

The default scope is the explicit task. An explicit `--make-default` updates the
Bot default and preserves every other existing task's previous effective model.
All the Bot's tasks must be idle for that operation. A private recovery journal
containing only model settings is saved before the default change. If preserving
an old task fails, the tool restores the original default and verifies all old
tasks. If the server is unreachable during rollback, the command fails and keeps
the journal. Restore it after the service is available:

```sh
python3 scripts/bot-model.py recover --file /ABSOLUTE/PATH/TO/RECOVERY.json
```

This is a compensating recovery, not an atomic cross-request database transaction.
The native header picker was actually tested: changing its thinking selector
changed the Bot default and made the selected task follow it, even when that
task previously had its own model. It can move other following tasks. Use this
tool for task-only changes or when old tasks' previous models must be preserved.

Only advertised levels are accepted. The absence of levels means the agent has
not offered an adjustable thinking control for that model, not that every level
can be requested. Changing a selection records the next turn's request; inspect
the real runtime acknowledgement before claiming it was used. The native raw
API can save an unsupported `variant` and reject it only when the next native
turn is configured; this tool rejects it before changing saved settings.

## Change between DSH and Antigravity

```sh
python3 scripts/bot-model.py switch \
  --bot BOT_ID --thread THREAD_ID --instance agy-gemini \
  --model gemini-3.8-flash --thinking high \
  --project /ABSOLUTE/PROJECT --role 'Independent reviewer'
```

This creates a fresh task in the same Bot with Ask approval, preserves the old
thread, and writes `.workflour/runtime-handoffs/NEW_THREAD.md` in the project.
The confirmation card states the Ask mode explicitly: this operation does not
carry the old task's Full permission into the new runtime.
The result contains `thread_id` and `next_prompt`: the settings operator sends that
prompt to the **new** thread to load the role and shared records. The script
does not itself send a model prompt or claim that the handoff has been read.
Select the returned new task in the workbench before continuing.

The native workbench picker can change engines inside an existing task; it does
not enforce this fresh-task policy. Use the safe command/script above for a
runtime change, or first create a new task manually and explicitly load its
handoff. Roles and project scope come from the Bot instructions plus project
records; changing engines is not a filesystem or long-term memory sandbox.

In the native picker, each instance has a provider/model group. DSH groups can
initially show only two DeepSeek-official entries; expand **Show all 17 models**
(**显示全部 17 个模型**) to see the WorkBuddy entries. Do not mistake the first
visible official entries for the WorkBuddy quota route.

## Verified catalog shape

Gemini uses the base `gemini-3.8-flash` model and `low`, `medium`, `high` variants.
Legacy Antigravity model IDs with `-high` suffix are not the new config-option
model IDs. DSH's custom ACP model IDs are JSON pairs, such as
`["workbuddy","glm-5.3"]`. Keep them opaque. The workbench's displayed model
names are human-readable; the CLI examples deliberately use exact protocol IDs.

Source and capability checks: [custom ACP implementation](https://github.com/milind-soni/OpenMausBot/blob/main/server/drivers/acp/custom.ts),
[DSH ACP](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/acp/acp/README.md),
[ACP session config options](https://agentclientprotocol.com/protocol/v1/session-config-options).
