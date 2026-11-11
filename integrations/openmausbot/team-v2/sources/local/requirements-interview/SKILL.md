---
name: requirements-interview
description: Clarify materially ambiguous goals, scope, constraints, and success criteria through focused Socratic questions, context-first synthesis, and evidence provenance. Use when the user asks to be interviewed or unresolved decisions would change a plan or implementation; skip an interview for already actionable requests.
---

# Requirements Interview

Reach enough shared understanding to choose and execute the next useful step. Optimize for decisions that change the work, not the number of questions or theoretical completeness.

## Start from available context

Read the request, relevant prior answers, and supplied evidence before asking questions. Investigate factual questions through available code, documents, measurements, or research when proportionate; reserve human questions for intent, priorities, trade-offs, or facts you cannot establish. An inaccessible source remains unavailable, not evidence for a convenient default.

Choose the starting point that fits the context:

- **Sparse context:** ask the question whose answer would most change the intended outcome, scope, or proof of success. Do not invent a detailed solution just to give the user something to approve.
- **Substantial context:** use an inverted interview. Propose a brief understanding of the outcome, primary deliverable, constraints, and material uncertainties, with links to evidence where useful. Invite corrections to the uncertain or conflicting parts instead of restarting with broad discovery questions. Separate supported statements from inferences; do not present a confident synthesis that hides a real alternative.
- **Already actionable:** continue the requested work. An explicit interview request still warrants useful questioning, but stop when further answers would only refine wording or irrelevant details.

For example, given prior discussion and a prototype: “I understand the deliverable as a reusable import tool; the report is one output. The prototype permits partial imports, but I haven't found a decision that this is intended. Should an invalid row reject the whole import or only that row?”

Preserve the user's primary outcome and every requested deliverable. A convenient prototype, report, or handoff must not silently replace the actual product. Incorporate corrections without reopening settled decisions unless new evidence creates a material conflict.

## Keep evidence and decisions distinct

Track only claims whose uncertainty could affect the work. For a simple request, a sentence may suffice; for several interacting claims, use a compact table in the conversation or existing plan:

| Claim or decision | Source / evidence | Status | Consequence if wrong |
| --- | --- | --- | --- |
| The current importer skips invalid rows | Inspected code path and reproduction | Confirmed observation | A change needs compatibility handling |
| Partial imports are acceptable | Inference from current behavior | Unresolved decision | Determines transaction and error behavior |

Record provenance separately from status:

- **Source:** direct user statement or decision, observed code/runtime behavior, a document or external research source, or agent inference. Link or identify the source precisely enough to revisit it. Attribute quoted stakeholder views to their source; they are not automatically the current user's decision.
- **Status:** confirmed, inferred, unresolved, or deliberately deferred. “Confirmed” means supported within the claim's stated scope: observed behavior establishes what happens today, while an explicit decision establishes what should happen. Repeating an inference does not confirm it.
- **Consequence:** explain what design, scope, or verification choice would change. For a deferral, record its boundary and when it needs revisiting; deferring a dependency does not resolve it.

Surface conflicting evidence instead of silently picking one source. Keep proposed defaults identifiable as recommendations. Silence, elapsed time, and approval of an unrelated point do not confirm a decision.

## Choose questions by their effect on the work

Target the uncertainty with the greatest combination of impact and cost of being wrong. Before asking, identify what you would do differently for the plausible answers. If nothing material changes, investigate it yourself, make a labeled low-risk assumption, or leave it for later.

Use questions such as these when they expose a real uncertainty:

- **Outcome:** “What must the user be able to do that they cannot do today?”
- **Premise:** “What requires these to be separate workflows?” or “What evidence connects this proposed change to the reported problem?”
- **Meaning:** “Does ‘completed’ mean submitted, processed, or accepted?”
- **Trade-off:** “If speed and completeness conflict here, which determines acceptance?”
- **Disproof:** “What result would show that this approach failed even if the implementation works as designed?”

Keep questions short and grounded in the user's vocabulary. Explain the consequence and offer a supported recommendation or a few concrete choices when that makes answering easier; leave room to reject the framing. Prefer one dependent decision at a time; batch a few independent questions when it reduces effort. Use an available question tool when appropriate, otherwise ask directly.

Track independent uncertainty areas such as outcome, scope, constraints, deliverables, and verification. When one tangent dominates, check whether a more consequential area remains unresolved. Continue independent investigation while awaiting an answer, but keep work that depends on an unanswered material decision pending.

## Stop and carry the result forward

End the interview when the outcome, scope boundaries, relevant constraints, deliverables, and observable success criteria are clear enough for the next requested step, and no unresolved decision would materially change that step. Do not require a numerical ambiguity score, a fixed question count, or repeated confirmation of settled answers.

Respect a request to stop interviewing. Summarize any material unresolved decision and its consequence, then advance work that does not depend on it. If the user delegates a choice, choose within that authority and record the rationale; otherwise do not invent the missing decision. Minor wording differences and optional edge cases do not justify another round.

Carry the agreed understanding, remaining assumptions, evidence provenance, and any consequential deferrals into the existing plan or handoff. Do not create a separate document merely to maintain a ledger. Preserve the parent task's authorization: a clarification-only request ends with the clarified requirements; when planning or implementation is already authorized, resume it without adding a new approval ceremony.
