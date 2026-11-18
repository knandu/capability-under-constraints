# Workload pivot and the completion boundary

**Decision: CONTINUE bounded tool work; STOP instruction-policy tinkering.**
November 15, 2026, 19:05:35 -06:00 (`fd94b24`, `de521e0`).

This deliberately pivots from largely single-shot Tamil rewriting to multi-step
tool/document work. It does not claim that one workload naturally became the
other. The additional question is what fits, completes, and remains inspectable
once orchestration shares the context window.

`tool-context.json` retains three focused read/edit controls. An 8K 201-line
fixture reached 4,036 client context tokens before a tool call, with a 1,407-token
read result. These are case-specific observations, not a fixed harness footprint.
Instructions, tool schemas, history, observations, and orchestration all consume
space; adding tools also adds choices.

`completion.json` projects the four original focused cases: tool names, event
counts, wall time, continuation stop reason, and exact-edit result. Adding
`task_complete` let the read/edit fixture complete. The unprompted identity case
still repeated to the continuation cap; explicit completion direction stopped it.
Successful file mutation and protocol completion are different observations.

`policy-regressions.json` preserves the rejected variants. Conditional/direct/
bounded policy attempts did not produce a dependable improvement: a policy could
finish while undoing the intended edit or triggering additional compaction.
The tool-only control was retained. None of this establishes broad autonomy.

## Measured system and tool scaffolding

A separate controlled CLI study on November 15 captured one request and checked
the server-reported prompt length against the rendered template's native-tokenizer
count. Both were **4,557 tokens**. The synthetic work request was **48 tokens**,
leaving **4,509 non-work tokens**, or **29.36%** of the 15,360-token input budget.
`prompt-overhead.json` retains the original numeric aggregate and selected tool
costs, with capture paths and message/prompt bodies excluded.

The author explicitly identifies this as **system prompt + tool description
overhead**. That is the interpretation used here: the effective system/tool
scaffolding cost for the tested CLI configuration, including associated framing
and ancillary messages, not a pure sum of plain-text description lengths.

| Recorded component | Tokens |
|---|---:|
| System message, including tool guidance | 2,925 |
| Other message content, excluding the work request | 95 |
| Tools and chat-framing residual | 1,489 |
| Total non-work scaffolding | **4,509** |

Removing tool definitions and re-rendering the same request measured a
**1,467-token marginal tool-injection cost** (4,557 minus 3,090). This is a
different decomposition of the same request, not another component to add to
the 1,489 residual. Standalone component and per-tool marginal counts are not
generally additive. The 4,500-token rendered prefix is also distinct from the
4,509-token total non-work cost, which includes surrounding framing.

The later minimal harness has a separate historical measurement documented at
source checkpoint `01b8a84` on November 16: **958 empty-history rendered tokens**
with five tools, comprising 411 system/guidance, 336 combined schemas, and 211
template/boundary delta. `minimal-harness-prompt-cost.json` retains those documented
counts and their provenance. This is corroborating evidence that scaffolding
cost is measurable, **not** a matched CLI-versus-harness speed/quality experiment
or a measurement of current prompt costs.

The scan found the controlled CLI aggregate, its analysis code, the documented
minimal-harness measurements, and the existing case-specific client-context
observations. The inspected customization-verification aggregates added no token
cost measurement. Private captures were not opened, and no new inference was run.
This curation correction restores evidence initially overlooked in an ignored
local artifact; it does not invent an additional historical experiment.

Private session streams, model-message bodies, connector inventories, personal
configuration, and operational paths are not included. These compact outcome
records are projections of focused experiment proofs, not public session captures.
