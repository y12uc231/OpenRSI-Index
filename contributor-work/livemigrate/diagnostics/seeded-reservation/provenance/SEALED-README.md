# Reservation seeded schedule audit v1

This **separate exploratory diagnostic** retains the frozen pilot's eight business calls, capacities, ownership moves, stable progress windows, immutable legacy helper, audit predicates, and exact finite-history checker. It does not replace or alter any original score, infer global model weakness, add semantic task families, or exhaustively verify a distributed protocol. Generated candidate source was not inspected to choose this pack, and no candidate has been replayed while building or calibrating it.

The pack is fixed as 4 calibration and 16 evaluation indices before trusted validation or any candidate replay. Index i uses original template i modulo 4. Thus each template appears once in calibration and four times in evaluation. Neither seeds nor templates may be dropped because an implementation fails. This entire artifact is public research material: the evaluation label marks a declared role, not a secrecy claim. Future model replay is Docker-only through a root-run controlled replay; the included host runner accepts only the five copied trusted controls.

## Exact generator

`task/schedule_policy.py` is the normative implementation. Seed i is SHA256 of ASCII `reservation-seeded-audit-v1:seed:<i>`, represented as lowercase hex. Hash-to-integer interprets SHA256 bytes as unsigned big endian. Node order is source, gateway, A, B; links are the 12 ordered unequal pairs in nested node order. Each index deterministically chooses:

* Link index = hash(seed + `:link`) modulo 12. Outage starts at round 9 + hash(seed + `:link_start`) modulo 8 and lasts exactly two rounds. Delayed packets remain queued. It applies only to inter-node traffic, and an observed-deferral counter distinguishes overlaps with existing blocking from additional deferrals.
* Output-loss node = node order[hash(seed + `:output_node`) modulo 4]. Eligible ordinal = 1 + hash(seed + `:output_ordinal`) modulo 3. Count that node's nonempty output batches only in rounds 9–21 or 32–59, after the local callback transaction and audit. Drop the selected whole batch (messages and replies) once before delivery. Batches already suppressed by the original template fault are not counted. This models post-commit output loss; it does not revoke database durability. Private message names/bodies are not inspected. The node, round, logical step, and output counts are recorded if it fires.
* Every round, sort the queued packets by hash(seed + `:queue:<round>:<insertion-index>`), with insertion index as a deterministic collision tie-break. Every eligible packet in that pending batch is delivered once (plus any original replay); no artificial sampling or starvation is introduced. Messages created within the round await the next round, as before. One tick per unpaused node per round retains the original template order. Driver messages are included in the queue permutation but cannot be targeted by the added link outage.

The original faults remain: one template replays each unique internal packet once, one loses a successful effect ACK, and one loses source output after an independently observed X fence. Added faults cannot occur in the stable Z window (22–31), partial-abort recovery (60–77), source-paused new-owner window (78–97), or final recovery (98–113). Packet permutation continues through those windows. This offers finite fair recovery; no permanent partition availability is required.

The same seed across different protocols is **not the same physical fault trace**: their output timing, queue insertion order and packet counts differ. It is a shared seeded environment distribution. An output fault or link deferral may be unexercised, or hit housekeeping. Trigger coverage must accompany every score; a selected fault is not evidence that a deep recovery boundary was tested. Callback, queue, SQL and history bounds stay unchanged and retain their original unscored/invalid classifications.

## Validation and artifact boundaries

`RUNTIME.patch` contains only generic scheduling hooks and diagnostic metadata. `task/history.py`, `task/API_CONTRACT.md`, `task/reference/immutable_v1.py`, and all original business scenario contents must remain exact. `upstream-source-hashes.json` records the frozen inputs with before/after copy equality. `seed-manifest.json` records the 20 generated configs and complete scenarios. `prepare_controls.py` copies five already-published trusted implementations: reference, alternate wire/schema, per-SKU drain before handoff, deferred move to tick, and early commit ACK. No model implementation is imported on the host.

Validation uses `test_schedule.py`, all 100 trusted control × seed runs in-process, and initially one actual pinned-image Docker reference run at calibration index 0. All trusted controls must pass the complete fixed pack before model replay. A failure requires diagnosing reference bugs or globally invalid scheduling assumptions; do not quietly discard failing seeds. Any semantic policy change creates a new declared version and repeats trusted validation before any candidate replay.

`validate.py` records per-case outcomes, timing, interpreter version, faults, and before/after source hashes. `SEALED.json` is written only after validation, binding the source tree, fixed seeds, and validation artifacts. The original pilot and current repository are not modified. Docker timing for one case is a pilot cost only, not a claim that all 20 cases fit an OpenRSI research budget. The pinned container does not pull images; it uses the existing local image.

Commands (from this directory, with the configured Python runtime):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_schedule -v
PYTHONDONTWRITEBYTECODE=1 python3 validate.py --output results/trusted-controls.json
PYTHONDONTWRITEBYTECODE=1 python3 validate.py --docker-reference-index 0 --output results/docker-reference-calibration-00.json
```
