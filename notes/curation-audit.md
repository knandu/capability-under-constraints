# Curation and publication audit

Prepared November 18, 2026. Ten historical decision gates are followed by one
explicitly editorial closure, a prompt-overhead evidence correction, later
publication-preparation edits, and a reproduction-controls restoration, not
additional inference experiments.

## Historical log

Every author and committer is `knandu <knandu@live.com>`.
All timestamps below use `-06:00`; all curation times are November 18, 2026.
The [evidence map](investigation-map.md) and [artifact origins](evidence-map.json)
give the corresponding source checkpoints and normalization/digests.

| Commit | Gate | Author date/time | Curation time |
|---|---|---|---|
| e4f070b | Baseline protocol | 2026-11-14 18:28:38 | 10:11:18 |
| 6dedcb8 | Expert locality | 2026-11-15 12:26:46 | 10:12:06 |
| 87607af | Stop kernels | 2026-11-15 12:26:46 | 10:12:08 |
| 7fe695a | Tamil quality boundary | 2026-11-15 13:34:02 | 10:12:11 |
| 57a1e08 | Reject Gemma package | 2026-11-15 14:52:19 | 10:12:13 |
| bb94a28 | Context economics | 2026-11-15 18:32:17 | 10:12:16 |
| 274efa6 | Completion and workload pivot | 2026-11-15 19:05:35 | 10:12:19 |
| 54fa60a | Observable harness | 2026-11-16 00:29:57 | 10:12:48 |
| d1a0f7f | Durable document state | 2026-11-16 17:49:14 | 10:13:32 |
| f467b4d | Qwen3.6 performance adoption | 2026-11-16 23:16:47 | 10:14:13 |

The editorial closure packages this report, native build records, and the explicit
timestamp explanation. Its author/committer times are actual November 18 curation
times. Its hash cannot appear inside its own committed report; the final handoff
includes the complete log, and `git log --reverse --format=fuller` exposes it.

## Later editorial commits

All are November 18, 2026, with identical author and committer times; none is
backdated, and none adds an inference experiment or changes a measurement.

| Commit | Time | Change |
|---|---|---|
| 1b14701 | 10:23:05 | Editorial closure: this report, native build records, timestamp explanation |
| d773b75 | 12:33:11 | Restore measured CLI prompt overhead and author interpretation |
| 7588372 | 12:36:07 | Clarify the context-budget motivation for an observable harness |
| e0daad8 | 13:17:10 | Optional browser DOM check selects a Chromium-based browser from `CHROMIUM_BROWSER` or `PATH` |
| 96485c6 | 13:20:10 | Document that browser selection in the harness README |
| dc90422 | 13:30:29 | Clarify the no-remote statement below; temporarily restore the pinned test bytes |
| ab49bb0 | 13:32:36 | Re-apply the browser selection and record it in the artifact-origin map |
| a04a4eb | 13:45:13 | Show the retained expert-locality progression in the README |
| 303d5be | 13:46:19 | Define controlled placement and matched settings for that progression |
| 47ec4cc | 13:53:58 | Remove a repetition; qualify the Tamil-workload decode rate as a different workload |
| 5199fcb | 14:05:18 | Make the browser-selection normalization note vendor-neutral |
| d664a38 | 14:09:12 | Record these later commits in this audit |

`dc90422` and `ab49bb0` cancel for the two harness files: the browser selection
was briefly reverted to match the pinned digest, then kept with an updated digest.

The following commit restores command lines and experiment controls that were
mistakenly pruned during publication-readiness preparation (see
[Follow-up: post-publication reproduction controls](#follow-up-post-publication-reproduction-controls)).
It was authored at 14:53:15 as a patch against `7588372` and applied on top
of the commits above; its committer time is the application time. A commit
cannot list its own hash.

## Validation scope

The three harness snapshots were checked before their respective commits:
22, 37, and 38 tests, each with one environment-dependent skip. The final suite
passed 37 tests, including the synthetic browser DOM case; the symlink-escape
case skipped because this Windows account cannot create symlinks. No privilege
change was attempted. This is a declared validation limitation, not a passed
symlink-isolation claim.

After the publication-preparation browser change, the suite runs 38 tests: 37
pass and the browser DOM case skips when no Chromium-based browser is configured.
Pointing it explicitly at the previously used browser timed out after 30 seconds
in this environment; the original implementation showed the same timeout.

`tools/validate_evidence.py` independently recomputes retained locality medians,
kernel means, Tamil coverage counts, Gemma wall-time aggregates, context acceptance
boundaries, AIPerf medians/ratios, and artifact digests. It makes no inference
requests. Original native CMake/compiler configurations are included with only
directory arguments normalized.

Every historical file revision, filename, commit message, author/committer record,
and the final candidate tree were scanned before editorial closure. Git config,
reflogs, URL hosts, email identities, and credential-like contexts were reviewed.
Only approved public identities, public technical URLs, loopback endpoints, and
synthetic negative fixtures remained. Generic auth handling/redaction is code,
not a committed credential. A final post-commit all-history check is part of the
handoff rather than relying only on a scan of HEAD.

## Source before/after

Source HEAD remained `40bb069f6dc9e9ca2f9e6469cb423f1a98955a8c`; working-tree
status remained clean. SHA-256 checks matched for 494 tracked/nonignored files,
four Git metadata files, and ten selected ignored raw-evidence artifacts.
At curation, the new repository had its own Git directory, no object alternates, and no remote.
No global identity configuration was changed.

## Exclusions, TODOs, and readiness

Excluded: private captures/session streams/checkpoints, machine administration,
service/browser configuration, binaries/weights/DLLs, downloaded environments,
full placement logs, full corpus/prompts, third-party model templates, and
unrelated work-system material. Their absence is deliberate; concise evidence
projections and source digests replace operational detail.

Both existing-public-work URLs were verified; the article's actual displayed
title is retained rather than guessing a title/URL. MIT follows the author's
verified public-project convention, with third-party boundaries documented.
There are no unresolved URL or license-selection TODOs.

The earliest baseline raw directory was unavailable; the subsequent original
locality archive supplies all three control repetitions. The initial curation
incorrectly treated the ~4.5K context-overhead figure as unsupported; the follow-up
below corrects that evidence-search error. Semantic document fidelity and
Qwen3.6 language/coding/general-agent quality remain unqualified; no results
were invented to fill those boundaries.

**Ready as a bounded public engineering notebook**, not as a deployment or
general-quality recommendation. Nothing was published, no remote was created,
and nothing was pushed.

## Follow-up: restore measured prompt overhead

The initial curation missed the ignored controlled-prompt aggregate. It was
incorrect to treat the ~4.5K figure as lacking evidence. The recovered aggregate
records 4,557 server prompt tokens matching native-tokenized rendered input,
minus a 48-token work request: **4,509 non-work scaffolding tokens**. The author
identifies this as system prompt + tool description overhead. The retained
decomposition makes clear that ancillary messages and framing are included.

The scan also recovered the separately documented historical minimal-harness
cost of 958 rendered tokens. Both records are now retained with scope, method,
original digests, and an explicitly attributed author assertion. No private
capture body or prompt content was read or redistributed in this follow-up,
and no tokenizer/inference endpoint was called. Offline validation checks the
retained arithmetic and provenance; it does not replay the excluded private input.

## Follow-up: post-publication reproduction controls

Command lines and the wrapper-parameter mapping were mistakenly pruned during
publication-readiness preparation, leaving wrapper parameter names unmapped.
The [stage audit](reproduction-audit.md) corrects that gap across all
ten gates. Saved native/AIPerf commands retain argument order and non-path values;
selected API fields, original synthetic test inputs and historical defaults are
retained with provenance. The source-default extraction is not passed off as a
record of private UI-session settings.

The official exact-revision cache documentation, argument parser and implementation
were retrieved and matched byte-for-byte to the pinned upstream Git blobs.
Both cache flags were upstream features. No local runtime patch is needed to
explain the selected configuration.

Remaining replay boundaries are explicit: excluded private input/context and
external templates; no recovered literal 20K-Q8 baseline server launch vector;
tokenizer repository identifiers without exact snapshot revisions in the command
records. The older 4K launch is not mislabeled as that later runtime.
This recovery did not run inference, rebuild, access the measurement machine or
rewrite historical commits. It is an additive commit on the already published
notebook.
