# Compressed plumbing and deliberate omissions

PowerShell default initialization, shared-MSVC-CRT consistency, and classification
of CUDA host versus device buffers were repaired before trusting placement and
timing. They are measurement-integrity prerequisites, not new optimization claims.
The pinned upstream was unchanged.

Later harness work repaired imported-session completion state, coherent UTF-8/
long-line paging, streaming/progress visibility, and output-limit handling.
The document gate groups those implementation changes around the resulting state
ownership/recovery decision instead of pretending each fix was an experiment.

Peripheral CLI modes, SDK customization restrictions, proxy/capture setup, browser
profiles, scheduled tasks, SSH administration, service activation/rollback scripts,
and machine-specific launchers are not needed to reproduce the engineering
decisions. They are omitted rather than retold as a product tutorial.

Also excluded: weights, binaries, DLLs, downloaded environments, full placement
logs, full prompt/corpus material, private captures and checkpoints, unrelated
sessions, and source Git configuration/identities/remotes. Compact numeric
records, meaningful rejected controls, authored harness code, and selected
generated excerpts survive.

No live inference, new model, quality campaign, kernel/context sweep, or broad
agent evaluation was run during distillation. Offline record checks and synthetic
code regressions are curation validation, not additional investigation results.
