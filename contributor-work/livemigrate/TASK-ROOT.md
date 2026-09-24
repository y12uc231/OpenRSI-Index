# Running another migration family

`--task-root` selects a trusted task folder. Omitting it preserves the original
amount-conversion family. Relative paths are resolved against the working
directory. From the `livemigrate` folder, after the identity family is installed:

```sh
python3 pilot/run.py --task-root families/identity --mode team --output /absolute/new/identity-team-run
python3 pilot/run.py --task-root families/identity --mode centralized --output /absolute/new/identity-control-run
python3 isolated.py --task-root families/identity --candidate families/identity/reference --suite public
```

The selected task folder supplies `API_CONTRACT.md`, `starter/{db,api,consumer}.py`,
`reference/immutable_v1.py`, `runtime.py`, and `scenarios.py`. Only the contract,
immutable v1 source, and starter/current candidate sources enter model prompts.
The runtime and scenarios load by exact path on the host, with a scoped
`scenarios` import so a previously loaded family cannot leak into the next one.
Task files are trusted evaluator code; this option is not a sandbox for an
untrusted evaluator implementation.

The core folder still supplies the pilot, Docker isolation wrapper, callback
driver, and audited Codex transport. Candidate containers mount only the three
candidate files, an optional copied public legacy helper, the core driver, and
one working SQLite directory. Neither task root nor core root is mounted.
The callback RPC supports any JSON-safe cursor,
including string cursors, without changes to the driver.

For independently persisted services, `MultiStoreInvoker` pools containers by
exact database file. Each node must have its own database directory; stores are
never mounted together. New `on_message(conn,message)` callbacks may write their
own database for any role. The existing `consumer.consume` remains read-only at
both SQLite and filesystem boundaries. The pool is limited to 16 live stores,
prunes removed scenario databases and closes every child on exit.

The trusted CLI selects only `reference/immutable_v1.py`, already present in the
public model packet, and copies it as read-only `legacy.py`. The driver loads it
under the module name `legacy`. No candidate-supplied path selects a helper and
no reference directory is mounted. Read-only source is not deep Python object
immutability: monkeypatching helper behavior is prohibited and semantic behavior
is checked by the independent host oracle.

`source-sha256.json` includes the core Python/Markdown/JSON sources and the
transport. A non-default family additionally contributes every such task file
under `task/` keys, including its runtime, schedules, and reference source.
Run summaries record both resolved roots. Model calls and scoring budgets are
unchanged by this routing option.

An external `--adapter-command` may return the legacy schema object directly, or
the strict JSON envelope `{"response": {...}, "metadata": {...}}`. Envelope
metadata is written to `metadata.json`; `response.json` always contains only the
schema response. Usage accounting expects `metadata.usage` to be a list of usage
objects with integer `input_tokens` and `output_tokens`; cached input is a subset
and is not added a second time. A legacy response creates no usage metadata.
Only the explicitly selected adapter program supplies this envelope.
The adapter stdin also includes optional `metadata_path`, an absolute local
sidecar path. An adapter may write available usage there on failure, then exit
nonzero. This path is controller bookkeeping and must never be sent to the
model. Failure reports include available usage and count sidecars explicitly
marked `usage_complete: false`; missing usage is never inferred as zero.

`--inference-timeout 1800` sets a 30-minute per-call transport deadline for a
prepared GPU adapter; the default remains 480 seconds for either backend. The
run summary records the selected deadline. A failed public-check transport is
also retained as `infrastructure_affected: true`, even if final judging later
succeeds; such a run did not receive the complete intended feedback schedule.

Routing tests use synthetic fixtures and no model calls:

```sh
python3 -m unittest tests.test_task_routing tests.test_isolation -v
```
