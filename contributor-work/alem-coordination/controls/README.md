# Simple scripted comparison

The assistant wrote [`visible_sync/controller.py`](visible_sync/controller.py)
as a simple comparison controller during task construction. Its code was fixed
before its first evaluation. When actors are already next to a visible hard
synchronization resource, it tries to
make them face and use that same resource together. In other situations, it
keeps the frozen policy's proposed action.

The controller reads the official local observation vector and uses ordinary
move and `Do` actions. It has no access to hidden simulator state and no free
communication channel. It does not attempt construction or global planning.
This is a simple comparison, not an optimal controller or a model-generated
result.

Evaluate it once on all 20 evaluation worlds using the same frozen runner used
for submitted controllers, and retain every outcome. Its purpose is to check
whether an obvious, small timing change already improves coordination. Do not
tune it using those evaluation outcomes or treat a weak result as evidence that
an LLM is weak. The pass-through controller, which returns the official policy's
proposal unchanged, remains the reproducible reference baseline.

The observation positions used by the code come from the pinned symbolic
renderer: 99 spatial cells × 97 channels = 9,603 values, followed by a 54-value
team dashboard, 24 direction indicators, 16 inventory values, six potion values,
eight intrinsic values and four facing values.
