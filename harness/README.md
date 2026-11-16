# Minimal observable local-model instrument

A standard-library Python HTTP/SSE application for inspecting a local model/tool
loop. It is not a production service or a general agent framework.
The source enters the curated history before document processing; later gates add
durable document state and explicit startup budgets.

Use Python 3.11+ and an already-running compatible OpenAI-style local endpoint.
From the repository root:

```powershell
python -B harness\harness.py --help
python -B harness\harness.py --base-url http://127.0.0.1:18082/v1 --model qwen3.6-35b-a3b-ud-q4-k-m --context 20480 --max-input 16000 --max-output 4000
```

The second command is the final selected configuration, available at the last
decision gate. It does not launch or download a model. Open the loopback browser
URL printed by the server. Endpoint selection is restricted to loopback.
`start.ps1` is an optional portable launcher; no machine-specific service launcher
or browser profile is included.

The UI exposes configuration, input/context usage, tool observations, streaming,
timing, run status, and explicit completion. Reported usage/timing belongs to the
actual request/transport; streamed reasoning is shown only when supplied, never
invented. Capture is optional and its output is ignored by Git.

The small tool set provides bounded inspection/editing and explicit completion;
read the tool schemas and working-root controls before using it. It is not a
security sandbox. Use only a directory and model endpoint you intend to expose to
the experiment.

System instructions, schemas, observations, history, and completion behavior are
visible experimental variables, not free orchestration. Context accounting is
endpoint/schema-version dependent; no universal fixed token tax is claimed.

Document processing lives in `documents.py`, not a second duplicate implementation
under `document-workflow`. [Workflow notes](../document-workflow/README.md) explain
state ownership and the semantic-fidelity boundary.

Offline regression checks:

```powershell
python -B -m unittest discover -s harness\tests -p test_harness.py
```

Fixtures use synthetic model/tool responses. Browser checks may skip if their
local browser prerequisite is unavailable. Passing these checks is not a live
model quality qualification.
