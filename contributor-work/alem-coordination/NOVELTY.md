# Prior art and the bounded contribution

Research checked on 24 September 2026. The source of the idea is current public
research and released evaluation assets, not the contributor's past projects.

| Existing work | What it already establishes | Boundary of this contribution |
| --- | --- | --- |
| [Alem, June 2026](https://arxiv.org/abs/2606.08340), [official source](https://github.com/alem-world/alem-env) | Procedural multi-agent coordination worlds; synchronization, handovers and construction; LLM and MARL baselines. | We do not claim a new environment. We construct an automated-research task with a fixed controller artifact, released policy and reproducible feedback loop. |
| [SPARTA](https://arxiv.org/abs/1912.02318) | Test-time search can improve cooperative play around a learned blueprint. | Frozen-policy improvement and cooperative planning are established ideas. Our narrow research interface has no test-time simulator/state oracle. |
| [MAAF](https://www.mdpi.com/2076-3417/14/21/10079) | A multi-agent adaptation framework can add message-conditioned residual behavior, including variants with a frozen base. | Communication-conditioned adaptation is prior art, not our invention. The candidate research artifact and fixed CPU evaluation contract are the proposed contribution. |
| [MATES, September 2026](https://arxiv.org/abs/2609.26010) | Learned observation adapters transfer frozen solo policies to multi-agent tasks. | Our source policy is already a trained multi-agent policy; the candidate changes decentralized execution/communication logic under fixed observations, without gradient training. This distinction does not make the general adapter concept new. |
| [Multi-Agent Collaboration for Automated Research, March 2026](https://arxiv.org/abs/2603.29632) | Budgeted comparisons of single researchers, subagents and teams on ML optimization. | Outer research-team comparisons are prior art. This contribution is the specific runnable coordination-improvement task, not the first study of multi-agent research. |

The [current official leaderboard](https://alem-world.github.io/leaderboard.html)
provides external evidence of coordination headroom, but its language-agent
protocol differs from the frozen-policy controller track. Our 18.9308% figure
is a new CPU measurement of a released HyperMARL checkpoint under the explicitly
recorded current configuration, not a leaderboard entry or an LLM score.

The OpenRSI public-catalog audit examined 45 Discussion titles and bodies and
found no equivalent Alem frozen-policy coordination-controller proposal. That
is a scoped catalog observation, not proof that the task is absent from every
paper, private repository, comment or unpublished experiment. A further focused
web search for Alem frozen controllers and automated-research evaluations did
not identify an exact released equivalent. Keep this qualification in any
submission.

The strongest defensible novelty claim is **a new OpenRSI research task and
its reproducible evaluation contract**. A successful method would require its
own comparison against relevant coordination baselines. A low starting reward
alone does not establish that the task is difficult for a frontier research
agent; that remains an empirical question.
