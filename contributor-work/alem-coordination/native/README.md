# Native single-container deployment route

This is a separately validated deployment port. It runs one trusted engine and three private actor processes **inside one ordinary Linux container**. The native entry point never calls Docker, uses a Docker socket, creates a sidecar, adds a capability, or requests privileged execution. The operator can launch that single container locally to validate the route; a Harness environment can instead place the same files in its normal main/Judge image.

The original `controller/` files and frozen researcher pilot records are unchanged. Their original deployment identity must remain attached to their scores. This port preserves the callback protocol, native reward, checkpoint, world seeds, action rights, horizon, and PRNG split. `ENGINE.patch` records the only engine change: an explicitly marked first-world deployment-proof option. Ordinary `--suite evaluation` still runs all twenty worlds; `--suite dev` runs four. A one-world proof is not a task score.

## Requirements and entry point

The validated environment image is the existing portable baseline build, local immutable ID `sha256:9282bdeb7b8debc675830cf464028cba51b9a7b83afd8c1f4c098f67edd73176` (Linux arm64). See `../baseline/README.md` for its pinned source, weights, and build recipe. Both that environment and the original separately pinned worker image report Python **3.12.14**. The port records the copied actor runtime tree digest; matching a Python version alone is not a claim that arbitrary controllers are deployment-equivalent.

Inside the ordinary container, install the unchanged upstream source at `/app`, weights at `/assets`, the task runtime files listed in the content allowlist below at `/task`, and a fresh empty output directory at `/results`. Trusted source, assets, harness, and submitted candidate input must be read-only to actor UIDs. Run as the supported root verifier bootstrap:

```sh
python -B /task/native/probe.py
python -B /task/native/run.py --candidate /task/controller/reference --suite evaluation --output /results
```

The candidate directory contains exactly the submitted `controller.py` that is copied into each actor root. The same command accepts another candidate directory. For an explicitly labeled deployment smoke, add `--proof-first-world`; do not use that option for the twenty-world task score. The default operator ceiling is 10,800 seconds; callback I/O has the unchanged thirty-second deadline. Timeout, provenance mismatch, startup failure, or incomplete evaluation is unscored. Normal completion with a candidate-invalid callback retains that classification and a null primary score.

A local outer-container validation needs only normal default capabilities; the measured command drops `NET_RAW`, has networking disabled, and requests four CPUs / sixteen GiB. No capability is added. The bootstrap requires default `SETUID`, `SETGID`, `SYS_CHROOT`, and `MKNOD` to be available, and seccomp filter installation to succeed. If they are unavailable it fails closed; it does not silently fall back to same-user processes. Current upstream Harness admits a root verifier in its ordinary unprivileged main/Judge container; final submission packaging must keep that supported configuration.

## Actor boundary

Each world starts three new Python processes. Each actor receives a copied private chroot containing only standard-library files and their dynamic libraries, the typed driver, its own candidate file, `/dev/null`, and private `/tmp`. It has no `/proc`, simulator, checkpoint, score file, task tree, or peer directory. No world identifier appears in the actor path; original argument metadata is reset before candidate import. File descriptors are closed by normal subprocess execution except the intentional standard streams; the driver uses framed, bounded messages.

The bootstrap enters the chroot, clears supplementary groups, changes to a distinct non-root UID/GID, pins one CPU, clears the environment, and applies no-new-privileges and an additional seccomp filter before candidate import. That filter denies network sockets and related operations, SysV and POSIX message queues/shared memory/semaphores, process creation/re-execution, affinity changes, tracing, cross-process memory operations, namespace/mount operations, and io_uring. The actual probe verifies socket creation denial for IPv4, IPv6 and Unix sockets, SysV/POSIX IPC denial, fork/exec denial, immutable affinity, read-only candidate source, fresh private state, and absence of a world identifier in bootstrap frames. Supported syscall tables are x86_64 and aarch64; actual kernel probes recorded here are arm64.

Actor virtual memory is capped at 384 MiB, JSON memory at the unchanged 65,536 bytes, open files at 64, and each written file at 16 MiB. **Resource difference:** private `/tmp` uses one fixed writable scratch file on the ordinary container filesystem, not the original general-purpose per-actor 16 MiB tmpfs. The earlier proof used a writable directory; the final native route instead precreates exactly one writable regular file, `/tmp/scratch`, with root-owned read-only parent directories. New files, removal, and rename are forbidden by permissions. RLIMIT_FSIZE therefore bounds each actor’s regular scratch disk to 16 MiB. General temporary-file APIs therefore differ from the Docker route. Hardware/timing side channels and aggregate trusted-process resources remain limitations; do not claim equivalence to separate container namespaces or a complete malicious-code sandbox. The scientific rule still forbids clocks/entropy/external state; that rule is not presented as complete kernel enforcement.

## Trust and provenance

`run.py` verifies the exact frozen source file inventory/content hashes and pinned checkpoint file hashes before and after evaluation, without requiring Git inside the image. It hashes candidate, original controller files, and native Python files as well. The engine writes a private intermediate result; the coordinator emits `result.json` with `provenance_verified: true` only after normal completion and unchanged inputs. `feedback.json` remains aggregate-only. Detailed logs/results are operator artifacts, not automatically public.

This closes the nested-Docker requirement for execution. It does not by itself establish the trustworthiness of arbitrary Work-snapshot contents. The Judge loads the complete Work snapshot. Judge-only injected tests and expected hashes may verify task-owned harness files, source, assets, and this adapter against their declared content. Internal self-consistency alone is insufficient. Inherited interpreter/runtime libraries and other platform files remain a Work-snapshot trust residual; this adapter does not replace them with a clean Base environment. Root verification capabilities belong only to the trusted bootstrap, never candidate processes. Pass-through parity supports this route for the measured controller; it does not prove every legal standard-library controller behaves identically under the two deployments.

No training, LLM calls, new checkpoint selection, or benchmark-case change occurs in deployment validation.

## Minimal Base / Judge content allowlist

Do not copy the whole contributor checkout, repository history, or operator output into a generated Work image. Build the environment dependencies using the pinned baseline recipe, then include only these task inputs:

- At `/app`: the 291 regular source files enumerated by `baseline/source-manifest.json`, verified byte-for-byte; omit `.git` and all untracked files.
- At `/assets`: only the 20 checkpoint/config files enumerated by `baseline/asset-manifest.json`, with exact pinned hashes.
- At `/task/baseline`: `source-manifest.json` and `asset-manifest.json`.
- At `/task/controller`: `launcher.py` (trusted reusable framing/validation helpers only), `controller_driver.py`, `wire.py`, `feedback.py`, `engine.py` and `CONTRACT.md`; plus `reference/controller.py` as the public pass-through starting point.
- At `/task/native`: `run.py`, `sandbox.py`, `actor_bootstrap.py`, `engine_entry.py`, `engine.py`, `probe.py`, `README.md` and `ENGINE.patch`. The optional offline test file is operator validation only.
- Public task instructions: the declared task design, action/observation contract and upstream license/attribution files. Include a writable candidate work directory with the public starter `controller.py`; copy its final submitted file into the private actor roots at evaluation time.

Exclude `controller/evidence/`, contributor `results/` directories, pilot records, model prompts/responses/events, native validation outputs, Git history, and all private operator logs. Initialize `/results` empty. The Judge still loads the complete Work snapshot; this allowlist describes initial Base content, not candidate-only Judge materialization. Judge-only injected tests and expected hashes may verify task-owned files. Within that inherited environment, the actor bootstrap selects the submitted candidate file and the narrow driver/stdlib subset for each child jail. It does not replace the outer snapshot or make inherited runtime libraries independently trusted.

The world IDs and upstream world generator are public, and published study outputs already exist. This is a fixed public workload, not a secret or unseen generalization split. The allowlist prevents automatically supplying per-world evaluation outcomes in the task environment; it does not make already-public outcomes secret. Normal researcher feedback remains aggregate-only.

## Measured deployment evidence

The final full twenty-world pass-through validation is in [evidence/README.md](evidence/README.md). All twenty native state/latent/action trace hashes match the frozen Docker baseline exactly, with mean coordination reward fraction 0.18522013239562513. The measured ordinary-container runtime was 145.39 seconds at four CPUs / sixteen GiB. These are deployment-parity measurements, not new researcher performance results. The attempt ledger preserves earlier infrastructure and trace-mismatch diagnostics.
