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

Private session streams, model-message bodies, connector inventories, personal
configuration, and operational paths are not included. These compact outcome
records are projections of focused experiment proofs, not public session captures.
