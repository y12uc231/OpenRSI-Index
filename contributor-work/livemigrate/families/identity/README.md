# Identity migration family

This second executable family was selected before the first family's model outcomes. Its scenarios and controls were independently authored before its own model calls. The reference and synthetic control checks establish implementation feasibility and oracle sensitivity only. See `../../pilot/IDENTITY-PROTOCOL.md` for the separately frozen pilot.

The family changes request uniqueness from a global raw key to a tenant-scoped pair. It preserves pre-migration operation IDs and external effects while allowing newly legal post-retirement work. This differs from the first family's amount-representation migration. Candidate DB layout, post-retirement operation-ID encoding, and new event layout remain implementation choices that DB/API/consumer workers must reconcile.

The API contract and immutable v1 implementation define behavior. The runtime keeps independent request, account-balance, and physical-effect ledgers. Consumers cannot mutate the sink, and accepted outbox history is immutable. Correct final database state does not excuse an earlier duplicate credit, wrong tenant effect, rejected valid work, or transient unauthorized balance change.

Trusted local validation:

```sh
python3 runtime.py --candidate reference --suite all
python3 -m unittest discover -s tests -v
```

Do not run generated code through the default in-process invoker. From the LiveMigrate root, use `python3 isolated.py --task-root families/identity --candidate families/identity/reference --suite all`. This generic Docker route was independently checked: the reference passes all four traces and 162 callbacks. No model calls or paid API calls are part of these commands.

Implementation provenance: the transaction-dispatch, status-reporting, and permanent-trace architecture was adapted from the personal checkout's `contributor-work/livemigrate/runtime.py`. This family's schemas, legacy implementation, reference, admission oracle, dynamic ID binding, scenarios, and tests were authored separately from the order-service family. See the research `REQUEST-ID-BLUEPRINT.md` and `NEXT-FAMILIES.md` notes for design rationale. The reference's compact JSON scoped IDs are an implementation choice, not required answers.

One public and three held-out trace variants are still one family. Their shared implementation and small count do not support independent-task or broad generalization claims. The repository-level prior-art audit applies to the combined instrument; it does not establish that tenant identity migration is a new software problem. Model difficulty and teamwork benefit remain empirical questions.
