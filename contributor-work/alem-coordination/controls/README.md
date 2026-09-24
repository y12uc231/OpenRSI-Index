# Scripted comparison

`visible_sync/controller.py` is a simple author-written control, fixed before
its first rollout. It tries to align already-adjacent actors toward the same
visible hard synchronization resource. Elsewhere it retains the frozen policy.
It uses the official local vector and ordinary move/Do actions, with no private
state or free communication. It is not an optimal controller or a model result.

Run all 20 evaluation worlds once under the same frozen candidate-only runner,
retaining every outcome. Do not tune this control against those outcomes or
present its weakness as evidence of an LLM weakness. It tests whether an obvious
small timing intervention already captures the available gain. The official
pass-through remains the materializable reference baseline.

The observation offsets come from the pinned symbolic renderer: 99 spatial
cells × 97 channels = 9603 values, a 54-value team dashboard, 24 direction
indicators, 16 inventory, six potions, eight intrinsics and four facing values.
The control makes no construction or global planning claim.
