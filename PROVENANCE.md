# Provenance and reconstruction

This repository is a curated engineering notebook distilled from a 25-commit
working investigation conducted November 14-16, 2026. Its Git history is organized
around experimental decision gates rather than the literal sequence of setup
fixes, exploratory edits, and instrumentation changes in the working repository.

Original experimental timing is retained through author timestamps. The public
reconstruction was committed separately on November 18, 2026. The source
investigation remains unchanged.

## What the dates mean

Each commit uses `knandu <knandu@live.com>` for both author and committer.
For the ten reconstructed experimental gates, the author timestamp represents
the original source decision checkpoint, including
its `-06:00` offset. The committer timestamp is the actual curation time, not
backdated. This graph did not literally exist during the investigation.

A curation-only closure packages the original native build
controls and publication audit. Both of its timestamps are November 18: that is
when this editorial verification happened, not an additional inference experiment.
It is not backdated to manufacture an eleventh historical decision.

A subsequent curation correction restores an overlooked ignored local prompt-size
aggregate from November 15 and the separately documented November 16 minimal-
harness measurements. The author's November 18 assertion identifies the former
as system-prompt and tool-description overhead; that characterization is retained
alongside the numeric decomposition, including framing and ancillary messages.
The correction's author and committer dates are actual curation dates, not a new
inference experiment or a rewrite of the ten historical gates.

Command lines and experiment controls were mistakenly pruned during
publication-readiness preparation. A post-publication reproduction audit restores
the original native/AIPerf argument vectors, API controls, synthetic test
recipes and historical harness defaults.
It maps the wrapper parameters to the pinned upstream flags and explicitly
distinguishes captured commands from recovered build recipes and unrecovered
literal launch details. This is another current-dated editorial addition, not
a new experiment or a change to the reconstructed historical commits.
[Stage audit](notes/reproduction-audit.md).

The baseline gate uses the November 14 protocol checkpoint, before target
qualification. Later target results enter at the locality gate. Locality and the
closing kernel comparison share a November 15 source checkpoint and therefore
the same author timestamp: they are separate decisions distilled from one bundled
commit, not invented sequential experiment times.

The [machine-readable map](notes/evidence-map.json) records each gate's timestamp,
source commits, and artifact origins. Source SHA references identify the working
record; they are not public remote links. Its final source HEAD was
`40bb069f6dc9e9ca2f9e6469cb423f1a98955a8c`.

## Evidence handling

Numeric CSV rows and selected JSON metric objects are retained with their original
values. Explicit projections remove operational path fields, machine/task names,
deployment arguments, connector inventories, and unrelated metadata. Derived
summaries are labeled and recomputed from retained rows.

The origin map records SHA-256 of original artifact bytes, the transformation,
and SHA-256 of the public result. A hash of an original file is not a claim that
the normalized public file has identical bytes. Some locality and AIPerf records
were available as local raw experiment artifacts, not tracked source blobs.
Those are identified as such; they are not retroactively called committed data.
Source-relative or absolute private filesystem paths are not published.

Focused completion records retain tool names, event counts, stop reasons,
timing, and exact-edit outcomes, not private session streams or model messages.
Short generated-output excerpts illustrate quality findings; the full Tamil
source corpus, private CLI context and real document/checkpoints are not
redistributed. Their original digests remain in the record. The reproduction
follow-up does include authored synthetic benchmark input, controlled CLI work
requests/fixture recipes, and inert context-filler construction. These small
controlled inputs are distinct from the excluded corpus and message captures.

The harness enters in its pre-document source state, then receives the document
workflow, then startup-budget options. Its README and launcher are curated for
portable use; this is not a reproduction of machine-specific service deployment.
Implementation-only source commits are grouped, not cherry-picked.

## Licensing and publication boundary

The notebook and authored code use MIT, following the author's existing public
[tamil-transliterator licensing convention](https://github.com/knandu/tamil-transliterator/blob/master/LICENSE).
This is not a copied llama.cpp license purporting to license the notebook.
[THIRD_PARTY.md](THIRD_PARTY.md) separates referenced runtime/model licenses and
excluded corpus material. Public author identity is normalized intentionally.

No source metadata, branch, index, config, or working-tree content was rewritten.
No new inference experiments, remote administration, publication, remote creation,
or push formed part of this reconstruction.
