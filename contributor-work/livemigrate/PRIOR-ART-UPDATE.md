# External research update — 23 September 2026

This supplements `PRIOR-ART-AUDIT.md` and the separate-owner prototype design.
It uses current external research, not the contributor's prior projects.
These sources further narrow the claim; none of their scores is a LiveMigrate
measurement.

| Primary source | Overlap | Boundary for this contribution |
| --- | --- | --- |
| [DDBench, 14 August 2026](https://arxiv.org/abs/2608.14863) | Agentic repair of historical distributed-system bugs; compares symptom-only input with bounded debugging context. | Distributed source repair and trace-informed debugging are established. Our candidate workload synthesizes cooperating service implementations during an immutable legacy ownership transition. This distinction does not establish global uniqueness. |
| [Specification Portability, 21 August 2026](https://arxiv.org/abs/2608.21208) | Transfers specifications between coding agents for Oracle-to-PostgreSQL migration; measures syntax, structure, similarity and immediate execution. | Specification handoff and migration agents are established. The proposed instrument follows live requests, durable obligations and effects across mixed implementations. The abstract alone is not a source-level audit of every released fixture. |
| [Anthropic multiagent report, 13 August 2026](https://www.anthropic.com/research/multiagent-systems) | Multiple agents share a migration codebase while receiving incompatible language targets and initially lacking awareness of peers. | LiveMigrate gives all authors one consistent objective, full peer visibility and an explicit public contract. We do not introduce conflicting hidden goals to manufacture coordination failures. |
| [ProtocolBench, ICML 2026](https://www.hongyidu.ai/projects/protocolbench) | Compares existing agent communication protocols and learned selection across task utility, timing, overhead and failure robustness. | This task evaluates the correctness of candidate-authored business-service protocols, while the research artifact changes coding-team instructions and dependencies. Neither protocol evaluation nor orchestration search is new by itself. |
| [Maelstrom](https://github.com/jepsen-io/maelstrom) and [Yugabyte Jepsen testing](https://docs.yugabyte.com/stable/benchmark/resilience/jepsen-testing/) | Executable distributed workloads, fault injection, client-history correctness and migration-related tests. | Simulation, linearizability checking and migration testing are established. The bounded contribution is a particular model-facing synthesis task and research protocol. |

The bounded search did not locate a released task with precisely the proposed
immutable legacy, separate inventory owners, atomic bundle obligations and
candidate-written handoff protocol. Search cannot prove absence everywhere.
If a closer released workload is found, revise the novelty statement instead
of redefining the existing work away.

The first two local prototypes were saturated by the requested frontier model
in both diagnostic modes. Their [complete results](results/README.md) stay
published. Separate-owner reservations are a disclosed new design iteration,
not a retrospectively selected subset of those results. Difficulty must be
established on its frozen implementation with strong baselines.
