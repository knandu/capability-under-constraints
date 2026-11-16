# Externalize state, not claims of understanding

**Decision: ADOPT durable traversal/checkpoint state and bounded recovery.**
November 16, 2026, 17:49:14 -06:00 (`9de324f` through `e602ddb`).

The implementation is [harness/documents.py](../harness/documents.py), with
byte-cursor tools and observable engine/UI integration. It is not duplicated here.

The application owns the source identity, byte cursor, successful chunk ranges,
notes and merge lineage, stage, attempts, and checkpoint. The model receives
bounded work rather than being asked to remember an entire traversal in chat.
Chat/model context is disposable; successful intermediate work is not.

The stages are traversal/chunk summarization, hierarchical note merging, and final
answer. Progress reports expose source bytes covered, chunks, active notes, calls,
and elapsed/budget state. Pause/resume uses a durable checkpoint and verifies the
source identity rather than silently proceeding over a changed file.

The motivating failure was real: all 108,640 source bytes had been processed in
36 chunks, yet merging could repeatedly exhaust a 4,000-token output limit.
Neither 100% traversal nor saved notes meant the run had completed.
This is a historical user-observed symptom, not a new semantic benchmark.
Private document/checkpoint content is deliberately not redistributed.

An output-limit response is incomplete. Its partial body is visible but is not
committed as a completed note. Compact intermediate-note targets, adaptive output
budgeting within the context limit, reduced merge fan-in, and bounded retry/pause
replace repeatedly spending the same budget on the same oversized operation.
A failed merge retains its source notes. Settings can be changed and a checkpoint
resumed rather than losing all completed traversal.

The accompanying regression tests exercise synthetic long-line/UTF-8 cursor
paging, checkpoint behavior, incomplete chunk/merge/final responses, compact
notes, and bounded recovery. They test control/state properties, not the quality
of a real document summary.

**Coverage means bytes supplied to successful summarization requests, not facts
understood or retained.** Hierarchical summaries can lose qualifications, merge
incompatible claims, or omit facts. There was no broad semantic-fidelity study,
and a resumed/finalized run is not proof of a faithful final answer.
