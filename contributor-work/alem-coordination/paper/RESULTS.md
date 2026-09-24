# Complete result table

Scores are mean coordination reward percentages, not pass rates. All programs were fixed before final testing.
The unchanged reference was selected using only four development worlds. The other final scores are descriptive;
they do not select a new winner. The six new programs belong to one dependent research attempt.

| Program | Development (4) | Original worlds (20) | Fresh worlds (20) |
| --- | ---: | ---: | ---: |
| Unchanged reference — selected | 22.4843% | 18.5220% | 19.4654% |
| Original Sol | 19.8113% | 19.4654% | 20.4403% |
| New call 1 | 19.8113% | 18.9623% | 19.0566% |
| New call 2 | 21.3836% | 18.6478% | 18.7107% |
| New call 3 | 20.7547% | 18.3019% | 19.4654% |
| New call 4 | 19.1824% | 19.8113% | 19.2767% |
| New call 5 | 22.3270% | 18.1132% | 19.3711% |
| New call 6 | 20.4403% | 18.7107% | 19.2453% |

## Paired changes on fresh worlds

Each comparison uses the same twenty world IDs. Positive means the named program scored more.
Counts use exact equality of recorded scores; tiny floating-point differences can count as changes.

| Program | Gain over reference (percentage points) | Better / tied / worse | Gain over original Sol (percentage points) |
| --- | ---: | ---: | ---: |
| Unchanged reference — selected | +0.0000 | 0 / 20 / 0 | -0.9748 |
| Original Sol | +0.9748 | 11 / 4 / 5 | +0.0000 |
| New call 1 | -0.4088 | 5 / 10 / 5 | -1.3836 |
| New call 2 | -0.7547 | 7 / 5 / 8 | -1.7296 |
| New call 3 | +0.0000 | 5 / 12 / 3 | -0.9748 |
| New call 4 | -0.1887 | 10 / 3 / 7 | -1.1635 |
| New call 5 | -0.0943 | 7 / 8 / 5 | -1.0692 |
| New call 6 | -0.2201 | 5 / 10 / 5 | -1.1950 |

## Actions and reward components on fresh worlds

Action changes and message counts describe whole trajectories. Changing one action can change later states,
survival and opportunities, so these counts do not identify the cause of a reward difference.
Reward components use their own native denominators; their percentages must not be added together.

| Program | Changed actions / all actions | Native messages | Ordinary reward | Soft coordination | Hard synchronous coordination | Handover | Construction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unchanged reference — selected | 0 / 22857 | 325 | 14.1935% | 23.0000% | 15.6250% | 80.0000% | 0.0000% |
| Original Sol | 1095 / 28299 | 924 | 13.9862% | 26.1250% | 15.9659% | 80.0000% | 0.0000% |
| New call 1 | 69 / 26262 | 378 | 15.7834% | 22.2500% | 16.3636% | 70.0000% | 0.0000% |
| New call 2 | 351 / 25581 | 451 | 15.3456% | 25.1250% | 15.0000% | 65.0000% | 0.0000% |
| New call 3 | 80 / 28389 | 418 | 15.5300% | 22.6250% | 16.3636% | 75.0000% | 0.0000% |
| New call 4 | 278 / 29322 | 619 | 14.8618% | 25.6250% | 15.7955% | 65.0000% | 0.0000% |
| New call 5 | 75 / 29241 | 570 | 15.2074% | 23.0000% | 16.5909% | 70.0000% | 0.0000% |
| New call 6 | 47 / 25086 | 344 | 14.4931% | 23.3750% | 15.6250% | 75.0000% | 0.0000% |

The [machine-readable analysis](study-analysis.json) contains all paired differences on all three sets,
including every regression, reward components and action counts. The source exports retain per-world metrics,
runtime costs, exact code and provenance. [analyze_results.py](analyze_results.py) verifies export file hashes
and recomputes the scores and comparisons without importing or executing any controller.

These are fixed-set descriptions. We report no confidence intervals or population-level model ranking.
