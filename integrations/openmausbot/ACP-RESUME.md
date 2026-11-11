# Harness native session recovery

`run-acp-agent.sh` now runs the same Coder/Doc Harness profiles through a small
Python standard-library stdio bridge. Only an explicit JSON-RPC
`session/load` request becomes `session/resume`; its ID and parameters stay
unchanged. The bridge also handles OpenMausBot reloading an idle session it
already holds on the same connection: it sends a real `session/close`, waits
for success, then sends `session/resume` with the new load request's complete
parameters. The private close response stays internal; the actual resume result
or close error is returned under the original client's ID. Notifications and
requests in the opposite direction are not mistaken for those responses.
stderr and all other frames pass through without logging.

This is an **OpenMausBot-specific alias**, not an implementation of standard ACP
transcript replay. The `loadSession` capability is deliberately left absent.
OpenMausBot already owns its visible chat history; this alias reopens Harness's
persisted Agent so the model keeps prior tool inputs/results and its selected
model. It does not promise to recreate an interrupted shell process.

## Existing implementation checked (2026-11-09)

- Installed Harness `0.2.1-rc.2` includes `AcpSession.resume`, which calls
  `ctx.agents.resume({resumeSessionId, ...})`. The ACP handler checks the saved
  session, checks cwd, and mounts fresh MCP connections. Its `session/resume`
  accepts the same sessionId/cwd/mcpServers fields OpenMausBot sends to load.
- Its `AcpSession.close` drains activity, flushes the durable session and
  disposes the Agent. Agent teardown closes the persistence write handle and
  detaches the live Agent/session; it does not delete the log. A subsequent
  resume restores that same session and mounts the **new request's** MCP
  connections, including fresh credentials supplied by OpenMausBot.
- Installed OpenMausBot `0.1.143` generic ACP `core.js:1091` attempts
  `session/load` when a resume cursor exists, without checking `loadSession`.
  Its built-in DeepSeek driver already uses `resumeMethod: "resume"`, but also
  hardcodes a single `acp` profile and a DeepSeek-key auth check. Switching to it
  would require changing the current WorkBuddy/profile integration. No config
  hook for the custom driver's resume method is exposed by this version.
- The custom driver can also call load on its own still-live session when the
  system/tool configuration changes. Harness rejects that direct resume as
  already active. The bridge only performs close/resume when this connection
  observed a successful native new/resume for that exact session, Harness
  advertised close support, and no session RPC is still in flight. A running
  prompt stays busy until its real response, including after cancellation.
  A busy repeated load is rejected without closing or replaying any prompt.
- The thin alias therefore reuses the installed runtimes and login as-is. It
  adds no third-party package, external service, or recurring cost, and does not
  patch either installed product. The wrapper uses macOS's Python 3.9+.

Sources read:

- [Harness ACP reference](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/acp/acp/README.md)
- [Harness ACP implementation](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/acp/acp/src/index.ts)
- [Existing load/resume discussion](https://github.com/deepseek-ai/deepseek-harness/discussions/6393)
- [OpenMausBot ACP driver](https://github.com/milind-soni/OpenMausBot/tree/main/server/drivers/acp)

Harness is MIT-licensed; installed OpenMausBot metadata says Apache-2.0. Both
upstream repositories were accessible and current source was checked. Runtime
behavior here is pinned to the installed versions, not inferred from the latest
branch. The bridge is a new, project-local implementation; no upstream code was
copied. Recheck it when updating either runtime.

## Validation

`python3 -m unittest discover -s tests -p 'test_acp_resume_bridge.py' -v`

These local tests cover method/ID/parameter preservation, unmodified frames,
stdout/stderr pass-through, large payloads, EOF, signals and child exit status,
plus ownership, in-flight prompts/configuration, private close IDs and their
collisions, notifications, real error propagation and fresh resume parameters.

The reproducible no-prompt probe is:

```sh
python3 tests/acp-reload-smoke.py assistant --output tests/evidence/acp-double-load.json
```

It creates one disposable native session and runs new → load → load → close →
load → close. A temporary local MCP server with no tools records four distinct
mount labels to prove the new request's settings are used. Evidence only saves
IDs, method success, selected model/thinking and mount labels, never native
logs, MCP credentials or conversations. The 2026-11-10 probe passed at
`tests/evidence/bot-controls-20261110/acp-double-load.json` with no prompt sent.
They do not replace the real restart test: the same Harness session ID must be
reused after restarting OpenMausBot, and a value previously learned only through
a tool must be recalled without rereading its input file.

If the saved session is missing, corrupt, still active in another process, or
opened under a different cwd, Harness's original error is returned unchanged.
Unknown sessions are never automatically closed, and the bridge does not kill
another process, change session IDs, cache old MCP mounts or delete logs.
There is no silent fallback in this bridge. Project handoff files remain the
portable boundary between different Agents and a recovery source for genuinely
missing sessions; native resume only restores that Agent's existing session.

## Model controls and fallback revisions

OpenMausBot sends its selected reasoning level again at every turn. That native
setter has no field distinguishing a person's click from automatic setup. The
bridge therefore records the model and reasoning values confirmed by Harness
under `DSH_HOME/workflour-fallback-controls/<session>.json` (mode `0600`). It
commits the initial setup as a baseline before the first prompt, without
creating a manual-change revision. Repeating the same successful setting is
idempotent; a later successful value change advances the revision. Failed
setters do not change it. On resume the saved baseline is retained, and legacy
revision-only files acquire their baseline without resetting the revision.
If recording fails, the error is explicit and an initial prompt is not sent.

This prevents routine per-turn setup from resetting an active fallback or
disabling the default cost-routing policy. It cannot infer a deliberate
same-value click: selecting the already-selected model/level does not force a
fallback reset. The current public task API does not expose its authoritative
native-session binding, so the safe model-control tool does not guess one from
possibly incomplete historical events. A real model/level change remains
detectable; Bot defaults, task permissions, and transcripts are untouched.

The bridge tests also cover initialization, unchanged setters, actual changes,
failed setters, native returned values, restart/resume, legacy marker migration,
and an unavailable or corrupt control-state file.
