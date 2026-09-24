# Exploratory competing-reservation probes

These three fixed schedules were authored after the main pilot was frozen and
generation began, before its final or held-out outcomes were available. They
address a concurrency gap identified in the independent pre-inference review.
No generated candidate source or failure was used to construct them. They are
an exploratory coverage investigation, not a replacement for the preregistered
pilot and not an independently sampled benchmark.

A legacy reservation leaves two units each of X and Y. Following the transfers,
two overlapping calls request X:2/Y:1 and X:1/Y:2 before either is delivered.
The judge accepts either legal winner. Both committing would oversell; both
returning out_of_stock merely because of mutually temporary holds has no valid
sequential explanation. Reversed invocation/delivery and finite replay/send/ACK
loss complete the three cases. Each case retries both identities.

The frozen trusted reference passes 3/3. Independent history controls accept
either winner and reject both commits or both spurious rejections. The reference
serializes overlapping bundles at the gateway, which is permitted. These probes
do not force a particular distributed deadlock or exhaust all message orders.

The [isolated reference replay](reference-result.json) also passes 3/3 in
162.805 seconds with 1,601 callbacks and unchanged verified sources. This is
instrument validation, not a model result.

Before interpreting model outcomes, validate the reference through Docker:

```sh
python3 diagnostics/concurrency/run.py --candidate families/reservation/reference
```

Use Python 3.11+ and the already available pinned image. The runner checks the
trusted runtime/driver manifest, executes each callback through separate-store
Docker isolation, checks source and candidate hashes again, and prints JSON.
Never import model-generated modules into the host interpreter.

After the declared model study completes, evaluate **every** final candidate
unchanged on all three probes. There are no new model calls, repairs or selected
replacement candidates. Report all outcomes under an exploratory label and
preserve every original public/held-out score. Invalidity, timeouts and
infrastructure remain unscored. Any future incorporation into the research
workload requires a new declared version; the current three-family primary
controller still uses its original three final traces per family.
