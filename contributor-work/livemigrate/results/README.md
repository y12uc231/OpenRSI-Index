# LiveMigrate pilot results

All four preregistered runs completed successfully. Requested local model:
`gpt-6-astra`, reasoning `ultra`. The provider exposes no immutable model
snapshot ID. These results **do not demonstrate frontier-model weakness**.

| Family | Mode | Held-out traces passed | Invalid/incomplete | Input + output tokens | Elapsed seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Amount representation | Three-agent team | 3/3 | 0 | 142,568 | 360.466 |
| Amount representation | Centralized diagnostic | 3/3 | 0 | 194,023 | 893.563 |
| Tenant request identity | Three-agent team | 3/3 | 0 | 131,055 | 219.272 |
| Tenant request identity | Centralized diagnostic | 3/3 | 0 | 184,912 | 764.029 |

Every run also passed both public checks. Held-out final-state, operation-history
and completion checks all passed. No infrastructure incident affected these
four runs. Each family contains three correlated stress traces; there are two
semantic families, not twelve independent tasks. One run per arm gives no
estimate of generation variance or broad model population performance.

Both arms used six calls. Team calls run in two concurrent rounds; centralized
calls can revise all three files six times sequentially. Adaptive depth, output
schemas, realized token use and wall time differ. This is a feasibility diagnostic,
not a controlled claim about teamwork advantage or efficiency.

## Provenance and replay

- Amount family source: `728c2a5c70667a879c1bbfe548502432508aa526`.
- Identity family source: `6d93c9a538f370dc25eeb1a839cf78462cfcbea0`.
- Protocols: `../pilot/PROTOCOL.md` and `../pilot/IDENTITY-PROTOCOL.md`.
- Each result directory contains the sanitized result, complete source hash
  manifest, and exact final three candidate files. Every source hash was checked
  against `git show` at its recorded revision before publication: 23 hashes per
  amount run and 50 per identity run. Candidate hashes also match the frozen
  submitted artifacts.
- Usage includes input and output once. Cached input and reasoning tokens are
  subsets, not extra additions. Raw prompts, private reasoning, provider events,
  personal paths and authentication metadata are excluded.

From the appropriate frozen checkout's LiveMigrate directory, replay a published
candidate with the pinned Docker image already present:

```sh
python3 isolated.py --candidate /absolute/export/candidate --suite heldout
python3 isolated.py --task-root families/identity --candidate /absolute/identity-export/candidate --suite heldout
```

The operation-history checker can detect deliberately wrong programs that a
final-state-only check misses, but that instrument property did not translate
into failures for this local model. Preserve this negative research finding.
The separate-owner reservation prototype is a new, explicitly disclosed design
iteration; these successful earlier families are not removed from the record.

## Third-family reference validation

The [separate-owner reservation reference](reservation-reference-001/result.json)
passes all four declared schedules in 297.171 seconds through the actual Docker
boundary: 3,071 callbacks, all eight client calls resolved per schedule, zero
static/trace violations and a valid exhaustively checked observed history in
each case. Replay, lost fulfillment acknowledgement and output loss after source
fencing were all observed. This is a trusted reference result, **not a model score**.

Source revision: `6a5c4e9c0750be7ef39f8216f073946e6fa4f667`. All 18 recorded
reference/task/driver hashes remained unchanged during the run and were verified
against that Git revision. The [declared model study](../pilot/RESERVATION-PROTOCOL.md)
uses this frozen version and reports every arm separately when complete.

## Third-family model results

All three declared arms completed and passed every original held-out case.

| Requested model | Mode | Held-out traces passed | Invalid/incomplete | Input + output tokens | Elapsed seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| gpt-6-astra, ultra | Six sequential all-role revisions | 3/3 | 0 | 355,843 | 2,997.021 |
| gpt-6-astra, ultra | Sequential protocol-first team | 3/3 | 0 | 247,816 | 2,811.229 |
| gpt-6-sol, ultra | Sequential protocol-first team | 3/3 | 0 | 252,455 | 2,049.876 |

The complete sanitized results and exact candidates are available for
[Astra centralized](reservation-astra-centralized-001/result.json),
[Astra team](reservation-astra-team-001/result.json), and
[Sol team](reservation-sol-team-001/result.json). Every arm also passed both
public checks 1/1. Every held-out case resolved all eight client calls, with no
static or permanent trace violations. Replay, lost
acknowledgement and post-fence output loss were observed in the designated cases.
This is another saturation observation, not evidence that these models perform
poorly. The three cases are correlated schedules of one semantic task, and one
generation per arm cannot establish broad model performance or generation variance.

All 112 recorded source hashes match the frozen task revision above; the three
published candidate hashes match the final submitted sources in each arm. Raw
prompts, private reasoning and local metadata remain excluded. Each source export
records its separate manual privacy-review status; candidate code is never rewritten.

The [three separately sealed concurrency probes](../diagnostics/concurrency/README.md)
are exploratory follow-up coverage. Every unchanged final candidate also passed
all three probes, with no new inference or selected replacements:

| Arm | Exploratory probes passed | Replay seconds |
| --- | ---: | ---: |
| [Astra centralized](reservation-astra-centralized-001/exploratory-concurrency.json) | 3/3 | 123.729 |
| [Astra team](reservation-astra-team-001/exploratory-concurrency.json) | 3/3 | 199.432 |
| [Sol team](reservation-sol-team-001/exploratory-concurrency.json) | 3/3 | 135.016 |

The candidates resolved all five calls per probe with valid observed histories,
zero permanent violations, and the intended replay/send/acknowledgement faults.
The runner verified frozen trusted sources, exact case bytes and candidate
hashes before and after evaluation. These additional correlated schedules also
show no model failure; their scores remain separate from the original study.
