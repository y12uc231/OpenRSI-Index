# Could this become an independent research paper?

Literature checked on **24 September 2026**. This is a research assessment,
not a paper submission or a claim of established novelty. The contributor has
chosen to submit the evaluation task to OpenRSI. The original task, pilot and
results remain unchanged.

The main review was prepared before the six-call continuation. Its outcomes
are reported separately in the [research note](README.md). The section on
selection and repeated feedback below was added during the declared diagnostic.

**There is a plausible paper here, but “an LLM improves multi-agent Python code
through repeated evaluations” is already established.** The closest papers do
that directly, including a second-level researcher that improves the code
generation process itself. More Sol iterations can produce a stronger
controller and useful evidence, but iteration count is not a new method.

A more defensible direction is to study **when an executable, locally informed
coordination controller can improve an already trained multi-agent policy,
and whether the same controller transfers to other frozen policies and new
worlds**. A paper would need either a distinct method that improves this process
or a substantial, reproducible finding about its limits. The present small
pilot establishes neither yet.

## What exactly is being compared

There are two different agents in our setup. The **researcher** is the language
model that writes code between experiments. The **game actors** run that code
around a frozen recurrent MARL policy. They do not invoke the language model at
every game step. Each actor receives only its own permitted observation and
policy outputs, retains private memory, and chooses a legal action.

The environment itself is prior work: [Alem, first submitted 6 June 2026](https://arxiv.org/abs/2606.08340v1),
with [official source](https://github.com/alem-world/alem-env) and released
policies. It already supplies procedural worlds, coordination requirements,
communication, MARL baselines and direct language-agent evaluations. Its
language-agent leaderboard is not a matched comparison for our controller
track. Neither that leaderboard nor our low baseline reward establishes
failure by an outer research agent.

The following twelve works are the closest method comparisons found in this
review. Dates come from arXiv submission/version records or the publisher,
not search-engine “published ago” labels. A preprint is identified as such;
reported results are the authors' findings, not replications performed here.

## Twelve close comparisons

| Work and verified date | What it already does | Difference from the proposed paper, and consequence |
| --- | --- | --- |
| **1. Beyond Scalar Rewards: Dense Feedback for LLM Policy Synthesis in Sequential Social Dilemmas**, Víctor Gallego. [Paper, v3](https://arxiv.org/abs/2603.19453v3); first submitted **19 March 2026**, revised **30 June 2026**; accepted NExT-Game/ICML 2026 workshop. [Author code](https://github.com/vicgalle/llm-policies-social-dilemmas). | Repeatedly generates shared Python game policies, evaluates them in self-play, and feeds results back to the LLM. Compares scalar reward with additional social metrics. | A direct overlap with our code–evaluation–revision loop. Section 2.2 explicitly gives its policies **full environment state** and helpers; they are complete policies, not controllers around a pretrained MARL network. Our restricted local information and frozen learned base define a different setting, but neither iteration nor richer feedback is new. |
| **2. Discovering Cooperative Pipelines: Autoresearch for Sequential Social Dilemmas**, Víctor Gallego. [Paper](https://arxiv.org/abs/2605.30003v1), **28 May 2026**; accepted AID-Wild/ACM CAIS 2026 workshop. [Author code](https://github.com/vicgalle/autoresearch-social-dilemmas). | An outer coding researcher edits the inner policy generator's prompts, feedback, helper functions and iteration rules. It evaluates modifications and retains improvements under a fixed welfare objective. | Rules out a broad claim that an automated researcher designing a multi-agent policy-synthesis pipeline is new. Its generated policies also receive full state (§2.2), and the study concerns complete programmatic policies rather than adaptation of fixed MARL weights. Adding a second optimizer loop here would need a distinct reason and comparison. |
| **3. GenSwarm: Scalable Multi-Robot Code-Policy Generation and Deployment via Language Models**, Ji et al. [Publisher paper](https://www.nature.com/articles/s44182-025-00065-w), **9 January 2026**, *npj Robotics*. | Generates executable multi-robot control code, deploys it, and refines it using feedback. Some tasks use fully distributed local control; others add one-time centralized assignment. Local sensing and motion APIs constrain execution. | We cannot claim the first LLM-generated decentralized controller, or dismiss this system as entirely centralized. Its instruction-to-robot skill generation differs from optimizing a residual around a released recurrent MARL policy under a fixed reward. That distinction needs empirical substance, not just a different environment name. |
| **4. MATES: Learning Multi-Agent Interactions by Transforming Observations for Frozen Single-Agent Policies**, Abboud and Gal. [Paper, v1](https://arxiv.org/abs/2609.26010v1), **22 September 2026**, preprint. | Trains small observation adapters that allow frozen solo policies to act in multi-agent tasks. It evaluates several tasks and learning algorithms, including transfer to team sizes not used during training. | Freezing a competent policy while adapting coordination is already the central idea. MATES uses learned input transformations and MARL updates; our candidate is executable action-selection code around an already multi-agent policy, with no gradient updates. We must show why code adaptation is useful relative to trained adapters, rather than claim freezing itself as the contribution. |
| **5. Message Action Adapter Framework in Multi-Agent Reinforcement Learning (MAAF)**, Park and Choi. [Publisher paper](https://www.mdpi.com/2076-3417/14/21/10079), **November 2024**, *Applied Sciences* 14(21), 10079. [Author-institution record](https://pure.kaist.ac.kr/en/publications/message-action-adapter-framework-in-multi-agent-reinforcement-lea/); [released code](https://github.com/leobumjin/MAAF). | Separates observation-based base behavior from a message-conditioned action adapter, trained in stages. The adapter combines with base action logits to isolate communication's contribution. | Communication-conditioned residual behavior is not new. Our distinction is how the adapter is obtained and deployed: LLM-written executable code, fixed game communication rights, and no policy-weight training. MAAF varies optimization choices, so it should not be described as uniformly freezing every component. The source review supports the framework comparison, not a matched Alem result. |
| **6. Improving Policies via Search in Cooperative Partially Observable Games (SPARTA)**, Lerer et al. [Paper](https://arxiv.org/abs/1912.02318v1), **5 December 2019**; AAAI 2020. | Improves an agreed cooperative policy using action-time search, belief tracking and Monte Carlo rollouts. It studies both one searching agent and coordinated multi-agent search, with a bounded-error improvement guarantee under its assumptions. | Cooperative policy improvement without retraining is old. Our actor has no simulator oracle and cannot run SPARTA's trusted environment rollouts. That is a meaningful access/compute distinction, not a claim that code overrides inherit SPARTA's guarantee. SPARTA is a conceptual comparator; an oracle-enabled implementation would belong in a separately labeled information/compute condition. |
| **7. Code as Policies: Language Model Programs for Embodied Control**, Liang et al. [Paper, v4](https://arxiv.org/abs/2209.07753v4); first submitted **16 September 2022**, revised **25 May 2023**; ICRA 2023. [Project and code links](https://code-as-policies.github.io/). | An LLM writes executable robot policies and feedback loops using perception and control APIs, including hierarchical function generation. | Executable controller code, spatial reasoning, and separating code generation from cheap runtime execution are established. Our challenge is the interaction between several local controllers and a fixed learned MARL policy, rather than the mere replacement of per-step LLM inference by Python. |
| **8. Automated Design of Agentic Systems (ADAS)**, Hu, Lu and Clune. [Paper, v2](https://arxiv.org/abs/2408.08435v2); first submitted **15 August 2024**, revised **2 March 2025**; ICLR 2025. [Author code](https://github.com/ShengranHu/ADAS). | A meta-agent searches executable agent designs, using an archive of past candidates and measured performance. It studies transfer across tasks and models. | A code-generating meta-agent, an archive, and repeated selection are not novel mechanisms by themselves. Our runtime actors are fixed RL models rather than the language-model workflows ADAS designs. An ADAS-style search is an appropriate strong search baseline after matching its budgets and permitted feedback. |
| **9. AlphaEvolve: A coding agent for scientific and algorithmic discovery**, Novikov et al. [White paper](https://arxiv.org/abs/2506.13131v1), **16 June 2025**. | Uses LLM-generated code changes, an evolutionary candidate population, and automated evaluators to improve algorithms. | “LLM proposes, evaluator scores, retain the best” is an established optimization procedure. Applying it to Alem can be useful, but alone is an application result. A new search method must beat a reasonably implemented evolutionary code-search baseline, or the paper should center a new scientific finding rather than new optimization machinery. |
| **10. Discovering Multiagent Learning Algorithms with Large Language Models**, Li et al. [Paper, v3](https://arxiv.org/abs/2602.16928v3); first submitted **18 February 2026**, revised **7 May 2026**. | Applies AlphaEvolve to CFR and PSRO algorithm design. It compares across an 18-game suite and studies how smaller, distilled algorithmic cores generalize better than complex evolved mechanisms. | LLM discovery of multi-agent algorithms is already demonstrated. This paper evolves learning/solution algorithms rather than local controllers around fixed trained game policies. It raises the evidence bar: explain and test the discovered mechanism, including transfer and simplification, rather than publishing only a high-scoring program. |
| **11. Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents (DGM)**, Zhang et al. [Paper, v3](https://arxiv.org/abs/2505.22954v3); first submitted **29 May 2025**, revised **12 March 2026**. | A coding agent modifies its own implementation, evaluates descendants, and maintains an archive for further improvement. | Self-modifying agent code and evolutionary improvement are established. Our present researcher modifies a separate game controller; it does not modify its own research procedure. Calling repeated Sol revisions “recursive self-improvement” would therefore overstate both what is implemented and what is new. |
| **12. TTHE: Test-Time Harness Evolution**, Nie et al. [Paper, v1](https://arxiv.org/abs/2607.08124v1), **9 July 2026**, preprint. | Changes executable harnesses around a frozen LLM during evaluation, using execution-derived proxy feedback without gold labels or weight updates. Selected harnesses persist across inputs. | Gradient-free adaptation around a frozen model during deployment is not new. Our system adapts game-control code using real development rewards, then freezes it for final evaluation. A controller changing private memory during a game is not the same as its source code being evolved during evaluation; these should not be conflated. |

## The closest overlap changes the novelty claim

The first Gallego paper is particularly important: its current title differs
from the older repository title, *Cooperation and Exploitation in LLM Policy
Synthesis for Sequential Social Dilemmas*. Those are versions of one work,
not independent evidence. *Discovering Cooperative Pipelines* is a separate
paper. Its full-state policy interface is explicit in the
[first paper's §2.2](https://arxiv.org/html/2603.19453v3#S2.SS2) and the
[follow-up's §2.2](https://arxiv.org/html/2605.30003v1#S2.SS2).

Their full-state access leaves a real information-boundary distinction for us.
However, GenSwarm already demonstrates locally executed multi-robot code, while
MATES and MAAF already separate an existing policy from coordination adaptation.
Combining those ingredients is a plausible research direction, not automatic
evidence of a major new method.

The strongest claim justified **now** is:

> We provide a reproducible implementation and initial measurements of
> LLM-generated local action controllers around a fixed recurrent MARL policy
> in Alem, under explicit observation, communication and evaluation rules.

That is an implementation and pilot claim. A stronger paper claim would need
evidence such as:

> A specified controller-synthesis method discovers reusable local coordination
> rules that improve multiple frozen MARL policies on new worlds, outperform
> matched code-search alternatives, and preserve individual task competence.

The second statement is a **research target, not a result we currently have**.
Do not claim “first,” “unique,” or “no prior work anywhere” from this review.

## Terms that could otherwise overstate the work

- **Frozen does not mean unused.** Our API lets a controller ignore the trained
  proposal and choose any legal action. A successful program might replace
  the base policy rather than improve it. Calling it a *residual* is only a
  description until dependency on the base is measured; it is not enforced
  by the current rules.
- **No gradient updates does not mean no learning.** Searching code with
  environment feedback is a form of learning/optimization. State that neural
  weights stay fixed, rather than imply that the method uses no experience.
- **No simulator oracle does not mean no planning.** A controller can plan
  paths through its observed map or reason with a model written in its own
  code. The enforceable claim is that it cannot query the evaluator's state
  or future transitions while acting. Development rollouts are still available
  to the researcher and must count toward its budget.
- **Decentralized execution does not mean decentralized design.** A single
  researcher can centrally write a shared program. Each runtime actor then
  has separate observations and memory. That differs from several research
  LLMs negotiating a solution, which requires a separate comparison.
- **Fixed public worlds do not establish generalization.** The original twenty
  worlds and their outcomes are public. Further optimization can honestly
  improve that workload, but an independent generalization claim needs a newly
  declared evaluation that is not used for revision or selection.

## What would make this a paper rather than task packaging?

The most useful next question is not simply whether Sol can raise the score.
It is **what kind of local intervention transfers, when it helps, and when it
damages the competence already present in a trained team**.

A concrete method worth testing could separate a local coordination decision
from the base action: the controller decides when to commit to a shared task,
how long to wait, when to abandon it, and when to return control to the trained
policy. A search procedure could evaluate these decisions separately rather
than repeatedly rewriting an unrestricted whole policy. Commitment, waiting
and state machines are not individually new. Any novelty would have to lie in
the specific synthesis/selection method or a supported finding about their
transfer, efficiency or failure modes.

For a convincing independent paper, the evidence should address these questions:

| Question | Evidence needed |
| --- | --- |
| Does the proposed method outperform ordinary extra compute? | Compare against continued direct Sol refinement and a reasonable archive/evolutionary code search, using matched researcher and environment budgets. Record retries, invalid candidates and all evaluation queries. |
| Is the pretrained policy actually useful? | Compare use of the proposal/logits against an explicitly defined controller-only or restricted-input condition. Inspect whether a supposedly residual method mostly becomes a new standalone policy. Do not forbid a strong replacement baseline just to protect the story. |
| Does the result transfer? | Freeze selection before new-world evaluation. Test other training seeds/checkpoints where compatible, and preferably another coordination setting or environment. Merely replaying the same controller on the same deterministic worlds measures reproducibility. |
| Is the mechanism coordination rather than longer survival alone? | Report survival, attempts, successes, communication costs and base/total reward alongside coordination reward. Use controlled component removals to test the claimed mechanism; avoid inferring causality from a persuasive code explanation. |
| Is the gain robust to research randomness? | Repeat independent researcher trajectories and report variation as well as paired world-level differences. One successful extension is a promising example, not an estimate of expected researcher performance. |
| Is there a reusable finding? | Simplify the final program, test the proposed rule independently, and report conditions where it fails. A transferable small rule or a clear tradeoff can carry a paper more convincingly than a large, unexplained program tuned to one workload. |

Adapter training such as MAAF/MATES and simulator search such as SPARTA have
different access and cost requirements. They should be adapted carefully or
reported as separate comparison conditions. Do not present their published
scores from unrelated games as numerical baselines for Alem, and do not claim
state of the art without matched experiments.

The current +0.9434 percentage-point Sol result is a valid initial outcome.
It is not enough by itself to support a broad method claim: it comes from one
short researcher trajectory, one pretrained checkpoint and a fixed public
workload. More iterations are worthwhile as an explicitly separate exploratory
extension. They must not erase the original attempts, turn newly observed
evaluation worlds into an allegedly untouched test set, or make the original
three-call comparison appear budget-matched to the extension.

## Selection errors and repeated feedback are also established concerns

A reversal between development and evaluation rankings is not itself a new
theory of generalization. [The Ladder](https://proceedings.mlr.press/v37/blum15.html)
(Blum and Hardt, ICML 2015) studies reliable leaderboard estimates when repeated
submissions adapt to earlier scores. [Generalization in Adaptive Data Analysis
and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)
(Dwork et al., NeurIPS 2015) explains how repeated data reuse can cause
overfitting and gives methods with formal protection under their assumptions.

Our four development worlds are explicitly used for search and selection. They
are not an untouched test set. We do not implement these papers' protections,
and returning only aggregate scores does not provide their guarantees. A
ranking mismatch in one fixed experiment also does not establish that adaptive
overfitting caused it; finite world sampling and ordinary controller variation
remain possible explanations.

An independent paper about this issue would need a stronger empirical result:
for example, a repeatable failure pattern in controller search, an explanation
tested by controlled comparisons, and a selection method whose benefit survives
new independent searches and untouched evaluation worlds. Reporting the whole
trajectory is useful evidence, but discovering one reversal is not sufficient
novelty by itself.

## Search scope and remaining uncertainty

The search covered primary papers, author/project pages and released code for
LLM policy synthesis, executable multi-robot control, frozen-policy adapters,
cooperative search, automated agent design and code evolution. Focused queries
also combined `Alem` with `frozen`, `controller`, `adapter`, `residual`,
`policy synthesis` and `AlphaEvolve`, including arXiv, GitHub and the official
Alem project domain.

Within those indexed results, this review did **not identify an external
released implementation with the exact combination** of Alem, a frozen
pretrained recurrent MARL policy, locally isolated executable action adapters,
native communication costs, and an outer LLM research loop. This is a bounded
search observation. It does not exclude unindexed code, unpublished work or an
equivalent method described with different terminology. The broader ingredients
and several very close combinations are already published, as the table shows.

Direct HTML retrieval of the MAAF publisher page was unreliable in this
session; its indexed publisher text, author-institution record and author-linked
code supported the comparison above. No claim here depends on reproducing its
experiments or resolving every optimization variant. OpenReview's PDF endpoint
also presented a browser challenge; the corresponding Gallego claims were
verified from the primary arXiv full texts instead.

No model calls, training, benchmark runs, source-code changes, publication or
commits were performed for this review. Only this new literature report was
added. The report does not use or search the contributor's earlier research.
