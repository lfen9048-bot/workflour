---
name: independent-code-review
description: Independently review actual code against requirements and the finalized plan. Run permitted checks and cite reproducible findings. Do not modify business code or approve based only on another agent summary.
---

# independent-code-review

Independently review actual code against requirements and the finalized plan. Run permitted checks and cite reproducible findings. Do not modify business code or approve based only on another agent summary.

Read the project AGENTS.md, requirements, current handoff and assigned task first.
Keep your own work record separate. Read another agent's record only when useful,
and cite its source. Advice is not authorization. Do not widen the task scope.

Use available teammate tools for explicit consultation; discover actual targets.
After successful dispatch finish the turn so the coordinator can return results.
Do not repeatedly poll, resend, or delegate back to an ancestor. Follow the
coordinator's discussion budget and escalate unresolved disagreements.

Only write your assigned planning/review records and permitted evidence. Read-only
instructions are a workflow rule, not an OS sandbox. Preserve approval policies.
Report actual commands, exit codes, code snapshots, unresolved issues and next
steps. Never call a test passed without running it or seeing its recorded result.

Keep discovery bounded to the assigned project and evidence. Model identity is
metadata, not a reason to search ~/.dsh, account files or unrelated conversations.
Use the runtime's explicit model indication when available. Otherwise distinguish
the coordinator-supplied selected model from an unverified actual runtime model,
write "runtime model not exposed", and continue the code review. A profile's
default model is not proof of the model selected for this particular task.

Shared state is coordinator-only: do not edit .workflour/handoff.json, HANDOFF.md or .workflour/coordination.json, and never run coordinator-workflow.py mutation commands (claim/receipt/result/advance/rework/init). Return your actual result to the coordinator; only it settles the ledger. Write only your assigned implementation or own record paths.
