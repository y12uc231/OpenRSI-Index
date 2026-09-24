# Sealed reservation schedule diagnostic — portable public package

This is an exploratory schedule-coverage diagnostic for the LiveMigrate reservation prototype. It preserves the original pilot scores. Four calibration seeds and 16 evaluation seeds were declared before any generated candidate replay, using the same four eight-call business templates. These are correlated environment repetitions, not 20 independent tasks. All seeds are public; the evaluation split is a declaration, not a secrecy guarantee.

The normative runtime, schedule generator, schedule policy, history checker, contracts, Docker transport, trusted controls and seed manifest are byte-identical to the sealed diagnostic. The starting source is [personal-fork revision 6a5c4e9c0750be7ef39f8216f073946e6fa4f667](https://github.com/y12uc231/OpenRSI-Index/tree/6a5c4e9c0750be7ef39f8216f073946e6fa4f667/contributor-work/livemigrate). `RUNTIME.patch` is the complete change from `frozen/runtime.py` to `task/runtime.py`; the package checker reconstructs and compares that patch.

## Inspect and verify without replay

Use Python 3.11 or newer with standard-library SQLite support. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 package_integrity.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_schedule test_packaging -v
```

The first command verifies the package, its links to the original seal and 18 frozen upstream files, regenerated cases, and historical validation records. It does not execute a candidate or contact a model. The tests exercise the scheduler and packaging/result validation only. `PACKAGE-SHA256.json` binds this portable package; its hash must accompany new portable replay records. A hash manifest records identity and consistency, not a cryptographic signature from an independent authority.

## Replay a published candidate through Docker

The host needs Docker and Python 3.11+ with `sqlite3.Connection.setlimit`. Acquire the pinned image explicitly before replay; the runner does not download images or model weights:

```sh
docker pull python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62
PYTHONDONTWRITEBYTECODE=1 python3 replay.py \
  --candidate ../published-candidate \
  --index 0 \
  --output ../seeded-replay-records/case-00.json
```

The candidate directory must contain the three published `db.py`, `api.py` and `consumer.py` files. Run once for each index 0–19, retaining failures and unscored records. Each output path must be new; the wrapper refuses to overwrite a record. Keep replay records outside this package. The package and candidate hashes are checked before and after execution. The wrapper reports Python, SQLite and pinned image metadata alongside native results.

Only `replay.py` is the public candidate-execution entry point. It always supplies the frozen Docker invoker. Do not invoke `task/runtime.py` directly on untrusted candidate source: its default in-process invoker exists for trusted control development. Likewise, `provenance/original_replay.py` is an archival copy of the original wrapper, not this package's entry point.

The unchanged transport runs candidate callbacks with networking disabled, a read-only root, dropped capabilities, no-new-privileges, bounded processes and memory, and one store directory mounted per container. It copies only candidate role files and the public immutable legacy helper. The host oracle, other store directories, model credentials, and source tree are not mounted. Consumer read callbacks remain read-only; the reservation `on_message` callback can update only its own store. Containers and callbacks use the original limits. The deterministic environment and history oracle run on the trusted host; this is not a full virtual-machine security claim.

The historical isolated reference measurement took 71.8 seconds for calibration index 0. It is not a measured whole-pack runtime. Use a generous operator deadline and preserve interruption/infrastructure outcomes as unscored. Native `candidate_invalid`, `unscored_audit_bound`, and `unscored_checker_bound` outcomes retain `score: null`.

## Validate completed replay records

Create a small JSON file containing the expected candidate hashes from its already published provenance, with exactly `db`, `api`, and `consumer` keys. Point the validator at a directory containing only the 20 per-index records:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 validate_results.py \
  --results ../seeded-replay-records \
  --candidate-hashes ../candidate-hashes.json
```

It accepts either the exact archived original wrapper or this portable wrapper, verifies the seal and candidate identities, and checks native score/status consistency and schedule provenance. It reports calibration and evaluation separately, including unscored counts and observed fault activation. Missing records fail validation unless `--allow-incomplete` is explicitly supplied; that mode reports the missing indices. Validation does not rerun a candidate and cannot attest that an arbitrary JSON record was honestly produced.

## Existing evidence and limits

The copied `results/` records predate this packaging work: all five trusted controls passed all 20 seeds (100/100 host runs), and one pinned-image Docker reference case passed with a native result identical to the host reference. No candidate replays or model calls were performed to create this portable package. Generated model results are separate artifacts; this package does not imply they failed.

The added policy permutes queue delivery without reading private message bodies, blocks one directed link for two rounds, and loses one bounded nonempty output batch. Existing business calls, capacities, ownership changes, liveness windows and history invariants stay fixed. The original replay, reply-loss and post-fence source-output faults also remain. See `provenance/SEALED-README.md` and `task/schedule_policy.py` for the exact definitions.

Actual message traffic affects which faults activate. Added link deferrals occurred on only five of 20 seeds for each trusted control, and a lost output can be housekeeping rather than a critical message. Report the recorded trigger; do not infer fault severity from the seed label. These finite schedules do not establish exhaustive distributed correctness, semantic generalization, team necessity, or poor model performance.

## Packaging provenance

The original seal's SHA256 is `8ddf3663fc5092b44f7e23ba0ae3c48fbedb90b381a5e414e99751128d24ae37`. `PROVENANCE.json` retains all original source and validation hashes and maps every exact copy. The original seal contained a private absolute root, so its bytes are not redistributed; the public metadata projection omits only that field and therefore has a different hash. The upstream source-hash record similarly omits its original private root while retaining every source hash and the original record hash.

Path-bound construction/control-preparation/validation wrappers are omitted, with their original hashes retained. The original replay wrapper is copied exactly for audit. New `replay.py`, `package_integrity.py`, `validate_results.py`, packaging tests, and this README are portable packaging additions. The new wrapper uses explicit trusted-module paths, adds package/environment provenance, and checks bounded regular candidate files; it neither changes normative cases nor the runtime, oracle, callback transport or scoring. New replay records identify this different wrapper and retain the original wrapper hash. No original sealed files or original model results were modified.
