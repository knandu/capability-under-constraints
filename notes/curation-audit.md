# Curation and publication audit

Prepared November 18, 2026. Ten historical decision gates are followed by one
explicitly editorial closure, not an eleventh inference experiment.

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

## Validation scope

The three harness snapshots were checked before their respective commits:
22, 37, and 38 tests, each with one environment-dependent skip. The final suite
passed 37 tests, including the synthetic browser DOM case; the symlink-escape
case skipped because this Windows account cannot create symlinks. No privilege
change was attempted. This is a declared validation limitation, not a passed
symlink-isolation claim.

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
The new repository has its own Git directory, no object alternates, and no remote.
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
locality archive supplies all three control repetitions. An unsupported exact
fixed context-footprint number is omitted. Semantic document fidelity and
Qwen3.6 language/coding/general-agent quality remain unqualified; no results
were invented to fill those boundaries.

**Ready as a bounded public engineering notebook**, not as a deployment or
general-quality recommendation. Nothing was published, no remote was created,
and nothing was pushed.
