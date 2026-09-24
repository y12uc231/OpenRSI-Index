# What changed in the Sol controllers

These descriptions come from reading the original Sol controller and the six
new controller files as text. No controller was imported or executed for this
review, and no model notes, prompts or reasoning were used. This is a description
of implemented rules, not causal evidence that a rule changed reward or worked
as intended during play.

The **proposal** is the action chosen by the frozen HyperMARL policy. A controller
can replace it using only its own observation, the native teammate dashboard and
its own memory, as defined in the [controller contract](../controller/CONTRACT.md).
Here, a **joint interaction** means several agents acting on the same nearby
target; a **handover** is an interaction another agent must finish before its
timer expires. “No added messages” means the controller does not introduce
communication actions; the frozen policy can still propose them.

## Behavior by candidate

| Controller | Rules visible in the source |
| --- | --- |
| Original Sol | Searches for nearby joint-interaction targets, assigns agents positions around them, and uses short paths, facing changes and matching communication symbols to try to coordinate action `5`; it also tries to finish visible handovers with `5` or a construction action. Health and basic-needs checks, time limits and cooldowns return control to the frozen proposal when its rules do not apply. |
| Call 1 | Removes path planning and added messages: it only attempts a joint interaction when enough healthy agents are already beside the target, first turns or waits, then attempts the interaction on two successive steps. It gives the target an 18-step cooldown afterward, avoids active handovers, and defers to proposed sleep, rest or stair actions. |
| Call 2 | Uses the four communication symbols as directional invitations: when the proposal is a suitable resource or construction interaction, it can signal which neighboring target to use, then responders turn or wait and attempt the interaction on the following step. Compared with call 1, this adds explicit invitations while retaining already-adjacent groups and more extensive health, basic-needs, handover and urgent-action exclusions. |
| Call 3 | Removes added messages again and uses a two-step plan: select an adjacent resource, construction or creature target, turn or wait, then interact if the target and enough original participants are still present. It allows at most eight interaction attempts per agent per world, avoids active handovers, and temporarily avoids a target whose visible kind remains unchanged after an attempt. |
| Call 4 | Restores matching communication symbols for nearby hard joint interactions, with stricter health and nearby-danger checks, at most five starts and four completed interaction attempts per agent. It also attempts to revive an adjacent dead teammate using `5`, and replaces a proposed `5` facing a living teammate with the highest-scoring other legal action from the frozen policy. |
| Call 5 | Narrows intervention to hard resource interactions with healthy agents already in place and no detected nearby hostile, with no added messages, construction handling or revival rule. It starts only on even-numbered steps, issues a directional action, and attempts `5` on the next step if the group and target still qualify, with at most eight starts and a target cooldown. |
| Call 6 | Rotates the eligible group through the three agent pairs and the full team on a fixed two-step schedule, attempting nearby resource, creature or construction interactions without added messages. Separately, it tries to initiate or finish construction handovers using inventory checks, a nearby helper and actions `52`, `51` or `53`, with danger checks and cooldowns. |

The main code-level differences are how each version times joint actions,
whether it adds communication turns, which targets it considers, and when it
leaves the frozen proposal unchanged. All seven include exception handling that
attempts to fall back to that proposal; reading the code does not establish how
often any branch ran, whether agents agreed on a target, or why a score changed.

## Action numbers used above

These are the action IDs in the frozen 60-action configuration, using the
official constants supplied in the researcher packet and the contract's final
four communication actions. A directional action can change facing and may
move the agent when the destination permits it; `5` is the context-dependent
`DO` action, not a dedicated synchronization or revival command.

| ID | Native action |
| --- | --- |
| `0` | Do nothing (`NOOP`) |
| `1`, `2`, `3`, `4` | Left, right, up, down |
| `5` | `DO`: interact with the faced target |
| `6`, `17` | Sleep, rest |
| `18`, `19` | Descend, ascend |
| `51`, `52`, `53` | Build shelter, forge, beacon |
| `56`–`59` | Four native communication symbols; each consumes the agent's turn |

## Source identities

Call numbers refer to the six new generations in the
[extension protocol](EXTENSION-PROTOCOL.md). These SHA-256 values identify the
exact source bytes reviewed; they do not identify an executed branch or an
experimental effect.

| Controller | SHA-256 |
| --- | --- |
| [Original Sol](../results/sol-001/generation-03/controller.py) | `3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89` |
| Call 1 | `adde1ca397bddcbaba36e63ecd6ded40133687563fcfdd596456948d83085192` |
| Call 2 | `250d47a0697ca52d45543c9c8e30246e7427a8786319ca4e18ce02d80b23e2f5` |
| Call 3 | `e65deb3bb2e51f304b5438d06d6be826de77fa5c70e4649fec48b27d81751db1` |
| Call 4 | `3bdd0f68c497bef4a7ab3e0d5d476b2fa6e145ff66a4f8815f4345981e350eec` |
| Call 5 | `50105844bd662113bc9db085a2a3d5990b09fa783319c8c1bfc7365c1d575dd4` |
| Call 6 | `1100a5af8f19ff678a3277ce40f7367ba6bc12e6b0f9404e98736a674e94674d` |
