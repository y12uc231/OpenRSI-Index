# Run the evaluator in one container

This deployment runs the evaluator inside **one ordinary Linux container**.
One trusted engine runs the game and computes scores. Three separate actor
processes execute the submitted controller, each with its own files and memory.

The entry point does not call Docker or require a Docker socket, sidecar,
privileged container, or added capability. You can launch the outer container
locally. RSI-Harness can place the same files in its normal evaluation container.

The original `controller/` code and frozen researcher pilot records are
unchanged. Their scores keep their original deployment identities. This port
preserves the controller callbacks, checkpoint, reward, world seeds, legal
actions, natural termination, 10,000-step ceiling, and random-number stream
splitting. [ENGINE.patch](ENGINE.patch)
shows the deployment changes: private source staging and an optional one-world
check. Neither changes the game or scoring rules.

## Requirements and entry point

Use the [portable baseline build](../baseline/README.md), which pins the source,
weights, and dependencies. The validated image is Linux arm64, with this local
immutable image ID:

```text
sha256:9282bdeb7b8debc675830cf464028cba51b9a7b83afd8c1f4c098f67edd73176
```

Both this image and the original worker image report Python **3.12.14**.
Each run also records a hash of the copied actor runtime files. A matching
Python version alone does not prove identical behavior for every controller.

Prepare these locations inside the container:

| Path | Contents |
| --- | --- |
| `/app` | Unchanged, hash-verified upstream source |
| `/assets` | Pinned checkpoint and configuration files |
| `/task` | Task runtime files from the allowlist below |
| `/results` | A fresh, empty output directory |

Source, assets, runtime files, and the submitted candidate input must be
read-only to the actor users. Start the trusted verifier as root:

```sh
python -I -B /task/native/probe.py
python -I -B /task/native/run.py --candidate /task/controller/reference --suite evaluation --output /results
```

The first command checks the operating-system restrictions without running a
policy. The second evaluates the public pass-through controller. To evaluate
another submission, point `--candidate` at its directory containing the single
submitted `controller.py`. The evaluator copies that file into each actor's
private directory.

| Option or limit | Meaning |
| --- | --- |
| `--suite evaluation` | All 20 evaluation worlds |
| `--suite dev` | Four development worlds |
| `--proof-first-world` | One-world deployment check; never a task score |
| Operator deadline | 10,800 seconds by default |
| Callback I/O deadline | 30 seconds |

Every invocation needs an empty `/results`. Preserve the previous output before
running again. Timeouts, startup failures, changed inputs, and incomplete runs
are unscored. Invalid candidate callbacks also produce a null primary score.
After successful initialization, a closed reply pipe with an observed process
exit is candidate-invalid. Startup failures, unknown exits, other OS errors,
and timeouts remain infrastructure/incomplete outcomes.

The measured outer container had networking disabled, a four-CPU quota, a
16 GiB memory cap, and a 256-process limit. It dropped `NET_RAW` and added no
capabilities. Capabilities are Linux privileges: the root bootstrap requires
the ordinary defaults `SETUID`, `SETGID`, `SYS_CHROOT`, and `MKNOD`, plus support
for installing a seccomp filter. It stops if these are unavailable, rather
than falling back to less isolated actors.

Current RSI-Harness supports this root verifier inside its ordinary
unprivileged main/Judge container. Final task packaging must preserve that
supported configuration.

## Python startup and repeat runs

Different processes need different startup settings:

| Process | Settings | Purpose |
| --- | --- | --- |
| Supervisor and probe | `-I -B` | Ignore current-directory, script-directory, and user Python import paths |
| Trusted engine | Empty environment, `PYTHONHASHSEED=0`, `-P -s -B` | Keep deterministic hashing, exclude unsafe import paths and user packages, retain installed JAX dependencies |
| Actors | Empty environment, `PYTHONHASHSEED=0`, `-P -B -S` | Keep deterministic hashing, exclude unsafe import paths and all site initialization |

The engine receives explicit CPU and cache settings. It does not inherit
Python path settings. The kernel probe verifies the actors' startup behavior.

Task helpers are loaded from their exact source bytes, so an unchecked Python
bytecode cache cannot replace them. For each engine invocation, the evaluator
copies the verified Alem package and baseline modules into a new private
directory, owned by the verifier, and removes it afterward. Shared `/tmp` is
never added to the import path. This also allows repeated invocations in the
same container.

## Actor isolation and limits

Each world starts three fresh Python processes. Each actor enters a **chroot**:
a private filesystem root containing only Python standard-library files and
their dynamic libraries, the message driver, its own controller, `/dev/null`,
and private `/tmp` storage.

Actors cannot see `/proc`, the simulator, checkpoint, scores, task tree, or peer
directories. Their paths do not contain world IDs, and original command-line
metadata is cleared before importing candidate code. Child processes inherit
only the intended standard streams; messages use a bounded, framed format.

Before candidate import, the bootstrap clears extra group memberships, switches
each actor to a different non-root user and group, pins it to one CPU, clears
the environment, and prevents it from gaining new privileges. It also installs
**seccomp**, a kernel filter that denies selected system calls.

The filter blocks network sockets; SysV and POSIX interprocess communication;
process creation and re-execution; changes to CPU affinity; tracing and access
to another process's memory; namespace and mount operations; and `io_uring`.
The probe checks IPv4, IPv6, and Unix socket denial, IPC denial, fork/exec
denial, fixed affinity, read-only source, fresh private state, and absence of
world IDs in bootstrap frames. Tables exist for x86_64 and aarch64, but the
recorded kernel tests ran on arm64 only.

| Actor resource | Limit |
| --- | --- |
| Virtual memory | 384 MiB |
| Declared JSON memory | 65,536 bytes |
| Open files | 64 |
| Writable scratch storage | One regular file, at most 16 MiB |

The only writable regular file is `/tmp/scratch`. Its parent directories are
root-owned and read-only, so an actor cannot create, remove, or rename files.
`RLIMIT_FSIZE` bounds the scratch file to 16 MiB.

This differs from the original Docker workers' general-purpose 16 MiB temporary
filesystem. An earlier native proof also used a writable directory. Code using
general temporary-file APIs may therefore behave differently on this route.

Shared hardware, timing side channels, and the combined resources of trusted
processes remain limitations. These restrictions do not establish equivalence
to separate container namespaces or a complete malicious-code sandbox. The
research rules prohibit clocks, OS entropy, and undeclared external state;
kernel controls do not fully enforce that scientific rule.

## What the verifier checks—and what it trusts

`run.py` checks the exact upstream file inventory, source hashes, and pinned
checkpoint hashes before and after evaluation. It also hashes the candidate,
original controller files, and native Python files. Git is not required inside
the image.

The engine writes a private intermediate result. The supervisor sets
`provenance_verified: true` in `result.json` only after normal completion and
unchanged inputs. Here, provenance means the recorded identity and integrity
of those inputs. Only aggregate feedback is written to `feedback.json`;
detailed results and logs are operator artifacts, not automatically public.

**Judge loads the complete Work snapshot.** Work is the researcher's workspace;
Judge is the evaluation phase. This adapter does not replace that snapshot
with a clean Base environment. Base is the task's initial environment.

Judge-only injected tests and expected hashes may check task-owned code,
source, assets, and the adapter against their declared content. The adapter's
own before/after consistency checks are not enough to establish that arbitrary
Work contents are trustworthy. Inherited Python, libraries, and other platform
files remain a trust limitation. Root privileges belong to the trusted
bootstrap, never the candidate actors.

Matching trajectories establish deployment parity for the measured controllers.
They do not prove that every legal standard-library controller behaves
identically on both routes. Deployment validation involves no training, LLM
calls, checkpoint reselection, or changes to benchmark cases.

## Minimal Base / Judge content allowlist

Build dependencies using the pinned baseline recipe. Include only these task
inputs in the initial environment:

- At `/app`: the 291 regular source files in `baseline/source-manifest.json`,
  verified byte-for-byte. Omit `.git` and all untracked files.
- At `/assets`: only the 20 checkpoint/config files in
  `baseline/asset-manifest.json`, with their exact pinned hashes.
- At `/task/baseline`: `source-manifest.json` and `asset-manifest.json`.
- At `/task/controller`: `launcher.py` for trusted framing/validation helpers,
  `controller_driver.py`, `wire.py`, `feedback.py`, `engine.py`, `CONTRACT.md`,
  and the public starting point `reference/controller.py`.
- At `/task/native`: `run.py`, `runtime_support.py`, `sandbox.py`,
  `actor_bootstrap.py`, `engine_entry.py`, `engine.py`, `probe.py`, `README.md`,
  and `ENGINE.patch`. The optional offline test file is for operator validation.
- Public task instructions: the task design, action/observation contract, and
  upstream license/attribution files. Provide a writable candidate work
  directory with the public starter `controller.py`; copy the final submitted
  file into private actor roots for evaluation.

Exclude the whole contributor checkout, `controller/evidence/`, contributor
`results/` directories, pilot records, model prompts/responses/events, native
validation outputs, Git history, and private operator logs. Start `/results`
empty.

This allowlist describes **initial Base content**, not a candidate-only Judge
snapshot. Judge still receives the complete Work snapshot. Its injected tests
and expected hashes may verify task-owned files. Inside that environment, the
bootstrap copies only the submitted controller and narrow driver/stdlib subset
into each actor root; it does not make inherited runtime libraries independently
trusted.

World IDs, the generator, and published study outputs are public. This is a
fixed public workload, not a secret test set or an unseen-world generalization
test. The allowlist avoids automatically supplying per-world evaluation
outcomes, but cannot make published outcomes secret. Normal researcher
feedback remains aggregate-only.

## Measured deployment evidence

The [evidence guide](evidence/README.md) distinguishes the original measurements
from the corrected runtime validated on **24 September 2026**:

| Runtime | Pass-through: 20 worlds | Unchanged Sol controller: 20 worlds |
| --- | ---: | ---: |
| Original native deployment | 145.39 s | 130.38 s |
| Corrected deployment, consecutive runs in one container | 125.29 s | 128.68 s |

All four checks matched their original Docker trajectories exactly. The
reference coordination reward stayed at **0.18522013239562513**; Sol stayed at
**0.19465409219264984**. These are reward fractions, not pass rates. The checks
used four CPUs and sixteen GiB.

The older artifacts retain their original source hashes and six-test record;
they do not certify later code. The corrected runtime has thirteen offline
regressions. Its [fresh validation record](evidence/post-audit-validation.json)
contains all forty matching trajectories from the two consecutive suites.
The [audit report](../AUDIT.md) describes the fixes and remaining limits.
Earlier infrastructure failures and trace mismatches remain in the attempt
ledger. None of these deployment checks is a new researcher-performance attempt.
