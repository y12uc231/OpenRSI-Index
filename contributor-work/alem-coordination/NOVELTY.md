# What this task adds to existing research

This proposal adds **an OpenRSI research task with a reproducible evaluation
procedure**. The researcher writes controller code to improve a pretrained
three-agent team in the existing Alem environment. It does not introduce a new
game or invent the idea of improving a frozen policy—a trained model whose
weights stay fixed.

The review below was checked on 24 September 2026. It draws on public research
and released evaluation assets.

| Existing work | What it already shows | What this proposal adds, and does not claim |
| --- | --- | --- |
| [Alem, June 2026](https://arxiv.org/abs/2606.08340), [official source](https://github.com/alem-world/alem-env) | Generated multi-agent worlds with synchronization, handovers and construction, plus language-model and multi-agent reinforcement-learning baselines. | We use that existing environment. Our contribution is a research task in which a submitted controller is tested around a released policy, with a reproducible feedback loop. |
| [SPARTA](https://arxiv.org/abs/1912.02318) | Search at evaluation time can improve cooperative play around a learned policy. | Improving frozen policies and planning cooperatively are established ideas. Our controller cannot query the simulator or inspect its hidden state while choosing actions. |
| [MAAF](https://www.mdpi.com/2076-3417/14/21/10079) | A multi-agent adaptation framework can change behavior using messages, including variants with a frozen base policy. | Adaptation based on communication is prior work. We propose a particular controller artifact and a fixed CPU evaluation procedure. |
| [MATES, September 2026](https://arxiv.org/abs/2609.26010) | Learned observation adapters transfer frozen solo policies to multi-agent tasks. | Our starting policy is already trained for multiple agents. The submitted code changes each agent's local action and communication decisions under fixed observations, without gradient training. The general idea of an adapter is not new. |
| [Multi-Agent Collaboration for Automated Research, March 2026](https://arxiv.org/abs/2603.29632) | Comparisons of single researchers, subagents and research teams on ML optimization under fixed budgets. | Comparing research teams is established work. We contribute this specific executable coordination-improvement task, not the first study of multi-agent research. |

The [current official leaderboard](https://alem-world.github.io/leaderboard.html)
shows that coordination can still improve in Alem. However, its language-agent
evaluation differs from this task's frozen-policy controller evaluation. Our
18.9308% figure is a new CPU measurement of a released HyperMARL checkpoint under
the recorded current configuration. It is not a leaderboard entry or an LLM
score.

The OpenRSI public-catalog audit examined 45 Discussion titles and bodies and
found no equivalent Alem frozen-policy coordination-controller proposal. A
focused web search for Alem frozen controllers and automated-research
evaluations also found no exact released equivalent. These searches have a
limited scope: they cannot establish that no equivalent exists in a paper,
private repository, comment or unpublished experiment. Any submission should
keep this qualification.

The task's originality and a future method's originality are separate questions.
A successful controller would still need comparisons against relevant
coordination baselines before making a new-method claim. Likewise, a low starting
reward does not show that a frontier research agent will find this task hard.
That requires measured researcher attempts under a stated budget.
