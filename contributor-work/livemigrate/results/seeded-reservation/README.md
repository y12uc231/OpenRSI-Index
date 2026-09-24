# Final seeded reservation coverage study

Exploratory follow-up, declared and sealed before replaying generated candidates.
No new model calls, repairs, retries, or replacement generations. The original
pilot scores remain unchanged. All 60 scheduled records are included.

| Unchanged candidate | Calibration (4) | Evaluation (16) | All outcomes |
| --- | --- | --- | --- |
| Astra centralized | 4 passed | 16 passed | 20 passed, 0 unscored |
| Astra team | 4 passed | 16 passed | 20 passed, 0 unscored |
| Sol team | 4 passed | 15 passed, 1 invalid | 19 passed, 1 unscored |

See [summary.json](summary.json) and each arm's complete `case-00.json` through
`case-19.json`. The cases are correlated seeded delivery/fault variants of four
business templates, not 20 independent semantic tasks. The original candidate
source remains in the corresponding sibling result directory. Its hashes are
recorded in every case and in each arm's `candidate-hashes.json`.

Sol case 16 halted with `CandidateError` at owner B, step 303. The saved wrapper
does not retain the underlying callback exception or process-exit detail, so
precise attribution cannot be recovered from these records. The frozen rules
classify this as `candidate_invalid`, with `score: null`; it is not silently
converted to a scored failure. Its 3/3 completion field describes only calls
issued before the halt, not all eight calls in the intended business template.
No diagnostic rerun was used to rewrite that outcome.

The [portable sealed diagnostic](../../diagnostics/seeded-reservation/README.md)
includes contracts, exact task/runtime/transport bytes, seed manifest, trusted
controls, validation provenance and Docker-only replay. The public packaging
manifest hash is
`9460d12184748d072c519a6d701f5873930865c30bad951a7070a47b252139bb`.
These records were produced by the preserved original wrapper, whose hash is
retained in the package. The portable wrapper was verified with packaging tests;
it was not used to manufacture additional candidate results.

The original seal hash is
`8ddf3663fc5092b44f7e23ba0ae3c48fbedb90b381a5e414e99751128d24ae37`.
The study took 1,269.05 seconds with at most four cases running concurrently.
Source and candidate hashes were verified before and after each case. The
per-case records retain actual fault activations; a seed label is not proof that
every configured fault affected critical traffic.

Decision: retire LiveMigrate as the main challenging OpenRSI proposal. These
results preserve a useful evaluation prototype and an honest negative finding;
they do not establish poor performance by most models or a teamwork advantage.
