# Trusted validation results

No generated candidate was read or replayed. Original pilot scores are untouched.

- Five scheduler tests passed.
- All 100 trusted control/seed runs scored and passed in 65.038 seconds; source hashes stayed unchanged during the run.
- Pinned-image Docker reference calibration index 0 passed, with 757 callbacks in 71.513 seconds (71.801 seconds including harness setup/cleanup).
- The complete Docker case result equals the corresponding host reference case exactly. Docker before/after source hashes match.

| Trusted implementation | Passes | Output losses exercised | Seeds with added link deferrals | Case seconds |
|---|---:|---:|---:|---:|
| reference | 20/20 | 20/20 | 5/20 | 11.882 |
| alternate_wire_schema | 20/20 | 20/20 | 5/20 | 12.577 |
| drain_before_handoff | 20/20 | 20/20 | 5/20 | 13.074 |
| deferred_move | 20/20 | 20/20 | 5/20 | 13.694 |
| early_ack | 20/20 | 20/20 | 5/20 | 13.325 |

The inactive-link seeds remain in the pack. A generic output loss can affect housekeeping rather than a critical message; report the observed trigger, not an assumed fault depth. The first Docker case itself had zero additional link deferrals. Only one actual Docker case was authorized for this initial instrument check, so the whole-pack isolated cost is not yet measured.

No seeds, fault rules, oracle rules or runtime hooks changed in response to validation outcomes. After both validation runs, one README sentence was changed from an unnecessary future-authorization formulation to “root-run controlled replay.” All executable and scenario bytes remain those validated. The final seal binds this wording change explicitly.

Validation demonstrates positive-control compatibility of a finite schedule distribution. It does not establish absence of false positives for every valid protocol, exhaustive distributed correctness, semantic generalization, team necessity, or poor model performance. The 16 evaluation indices reuse the same four eight-call templates; they are correlated environment repetitions. The seed pack is public, so “evaluation” is a declared split rather than a secrecy guarantee.
