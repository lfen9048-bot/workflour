# Bot discussion in a coding project

Use the installed OpenMausBot 0.1.143 room and `agents` MCP tools. No additional
message service or vendor patch is required. DeepSeek and Gemini keep their own
models and tools; a room does not merge their complete private histories.

## Prepare the coding role

```sh
./integrations/openmausbot/setup.sh --only deepseek-coder
python3 tests/acp-smoke.py deepseek-coder
```

The independent `omb-deepseek-coder` profile uses WorkBuddy
`deepseek-v4.1-flash` and the `code-collaboration` skill. Existing GLM Coder and
Doc remain available. See [profile details](DEEPSEEK-CODER.md).

Create a room containing DeepSeek Coder and Gemini, choose the project working
directory **before the first message**, and use `mentions` as the default
responder. Give each feature a separate room task. Point both participants to
the project's requirements and handoff files. The current Codex chat can direct
the exercise and read results through the local control API; it is not a
permanent Codex Bot and does not run while this chat is inactive.

## Starting another task or project

A new task gets a new thread and empty native resume cursors. The Bot's model,
skills and standing instructions remain available. Project requirements and
handoff files are separate from the conversation and must be read again.

A new thread is not a complete memory wipe. OpenMausBot can add persistent
memory, recent-work summaries and team context; ordinary private turns can also
recall older conversation passages. Room turns do not automatically recall
private conversations, but can still receive memory notes. `compact` summarizes
or rebuilds the current context; it is not a clean project reset.

For a different project, choose its directory and create a separate room/task
with the correct project bulletin. The retained **Code 协作演练** room and
DeepSeek Coder default directory currently point to `examples/discussion-demo`.
Do not rely on opening a blank task to change those settings. This trial has not
implemented or validated strict cross-project memory isolation.

## Consultation and review are different

For a question, ask the author to call the actual `coordinate_bots` tool with
the teammate's discovered ID, a complete question, and `consult: true`. Include
short code or necessary context. The recipient should answer without starting
an implementation task. `consult` is an instruction, not an OS read-only sandbox.

For an independent review, omit `consult`. Specify the exact project/files,
requirements, permitted checks, and expected findings. Keep one code writer;
the reviewer reports evidence and does not simultaneously edit those files.

After successful dispatch, the initiating Bot must finish its turn. The native
coordinator returns the teammate's result and resumes it automatically. Do not
poll from that same turn, repeatedly resend, or delegate back to an ancestor.
When correcting completed work, request concrete changes with `rework: true`.

`post_to_room` is an announcement: it does not wake room members or return their
answers. Use it for a completed summary, never to request a review.

## Keep a discussion bounded

- Address only the required teammate. Keep progress announcements passive.
- Each request states an outcome and who owns the next action.
- Give the discussion a small agreed round budget; unresolved disagreements go
  to Codex/the coordinator for reproduction and a decision. This project does
  not add a configurable hard three-round counter.
- Preserve native deduplication, ancestor and wait-cycle protections.
- Keep approval modes unchanged; approve a concrete requested operation once
  when it is within the authorized task, rather than granting blanket access.
- Save decisions, remaining issues and the next action in the project handoff.
  Changed code requires fresh review and test evidence.

The ordinary room `@` relay has a one-hop limit; `coordinate_bots` provides the
separate task/result lifecycle needed for consultation and review. The current
custom ACP room context is bounded; important decisions must remain in files.

## Live exercise

The independent exercise is [discussion-demo](../../examples/discussion-demo/README.md).
Its room is named **Code 协作演练**. Raw native traces contain internal capability
credentials and must not be copied into the repository. Safe evidence belongs
under `tests/evidence/discussion-20261109/`; the final summary distinguishes
completed checks from untested behavior.

For a safe read-only check of task delivery and automatic resumption, run:

```sh
python3 tests/omb-discussion-audit.py \
  --thread-id 9904f6a4-4241-4cf9-8ec7-39a108b634f1 \
  --sender-id a6032a2d-22b9-4a93-867e-8303082b5fd0 \
  --recipient-id e4794be2-ea6f-43d6-9b30-ac3060c24b72 \
  --out tests/evidence/discussion-20261109/coordination-audit.json
```

The audit exports only related task metadata. It does not copy message bodies,
native requests, credentials, or model reasoning. Review quality still requires
the actual code, review report and test results.
