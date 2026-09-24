# Repository-disjoint proposed study selection

[`study-v1.json`](study-v1.json) freezes **24 development pairs from eight repositories and 12 evaluation pairs from four repositories**, selected from CooperBench's 652 pairs / 30 base tasks / 12 repositories at `63b9d44d9f39a02fccf5bf0052db48a917a011fd`. Its exact content digest is in [`study-v1.sha256`](study-v1.sha256). This is a source-audited proposed workload, not a claim of36 runtime-validated cases.

The existing three-pair pilot already uses `pallets_click_task` and `samuelcolvin_dirty_equals_task`. **Both entire repositories are assigned to development before applying any hash selection.** Their other features/base tasks cannot be represented as unseen evaluation data. These exposure constraints are part of the frozen rule, not an outcome-based exclusion.

| Split | Repositories | Pairs |
| --- | --- | --- |
| Development | huggingface_datasets, pallets_click, openai_tiktoken, pillow, samuelcolvin_dirty_equals, llama_index, typst, dspy | 3 per repository; 24 total |
| Evaluation | pallets_jinja, dottxt_ai_outlines, react_hook_form, go_chi | 3 per repository; 12 total |

Names above omit the common `_task` suffix for readability; the JSON contains exact upstream IDs. Source paths, Git-blob SHA1 identities, sizes, immutable links, feature numbers and selection hashes are included for every selected case.

## Fixed selection rule

1. Assign all previously used pilot repositories to development.
2. Sort all remaining repositories by SHA256 of `jointverify-v1:` followed by exact repository ID. Add earliest repositories to development until it contains eight; the other four are evaluation.
3. Within each repository, sort base tasks by SHA256 of `jointverify-v1:task:REPO:TASK`.
4. Within each base task, sort unique feature pairs by SHA256 of `jointverify-v1:pair:REPO:TASK:FEATURE_A:FEATURE_B`, with ascending feature IDs.
5. Round-robin across the ordered base tasks, taking one next pair from each until three pairs are selected. This spreads coverage over base tasks before reusing them when the repository has fewer than three.

The builder reads **no model scores, difficulty labels, policy outcomes or test results**. All 36 selected cases have the recorded Dockerfile, combined oracle patch, both feature descriptions and both feature-test patches in the complete pinned Git tree. Optional recorded runner/test-shell/individual implementation patches also exist for this selection. File presence and Git identities do not establish working container images, applicable patches, correct tests or model headroom. No new images were pulled and no selected study tests/model runs were executed during generation.

Only the separate three-pair pilot has its documented environment/oracle checks. The 36 study pairs do not include those exact pilot pairs, although development repositories/base tasks overlap intentionally. Every `image_digest` remains null in the study manifest until pinned by implementation. Do not fill it by copying a digest from a different base task.

No difficulty filtering or automatic replacement is permitted in v1. If infrastructure validation later finds a broken case, preserve the finding and create an explicitly versioned manifest with an outcome-independent exclusion/replacement rule **before policy comparisons**. Do not quietly drop failed model cases or change denominators.

## Reproduction

[`build_study_split.py`](build_study_split.py) accepts the pinned public `dataset/subsets/all.json`, a complete GitHub recursive tree JSON for that same commit, and [`pilot-v1.json`](pilot-v1.json). It checks source cardinality, duplicate pair IDs, source pins, repository separation and selected pair counts, then writes the manifest and SHA256 file.

```bash
python3 manifests/build_study_split.py \
  --all /path/to/pinned-all.json \
  --tree /path/to/pinned-complete-github-tree.json \
  --pilot manifests/pilot-v1.json \
  --output /tmp/study-v1-reproduced.json
```

Compare file bytes, not the sidecar filename: the JSON contains no generation time or machine path, so identical inputs yield identical content. Input source URL/revision/hash and the pilot input hash are recorded in the result. Preparation checks verified three selected pairs per repository, 36 unique raw IDs, eight/four disjoint repository sets, forced inclusion of both pilot repositories in development, all required source assets present, and order-independent regeneration.

## Evaluation meaning

An evaluation-repository score can test policy transfer beyond development repositories. With three pairs per repository it remains coarse and correlated; report repository/base-task group structure and avoid claiming precise gains from a one-pair change. Upstream tasks/reference patches are globally public. Runtime withholding is not a claim of global secrecy, contamination-free evaluation or a new benchmark. If the outer research loop receives repeated aggregate Judge scores on this set, call it repository-disjoint evaluation, not an untouched final holdout. No per-case hidden test outcomes or oracle contents should be returned to Work under the proposed contract.
