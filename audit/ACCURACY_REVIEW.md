# Accuracy and Benchmark Review

## What the headline metric measures

`rea_video/evaluate.py` computes `duration_weighted_accuracy` by iterating each predicted shot, taking its midpoint, finding an applicable ground-truth label/segment, and adding the shot duration to correct duration when `shot.base.label` belongs to the accepted label set. It also emits a mean of per-video accuracies. This is duration-weighted shot-label agreement on annotated timeline portions, not frame-level accuracy, calibration, or performance over a representative population.

The evaluator supports multiple accepted labels (e.g. `[ai_video, cg_3d]`), which is defensible for ambiguous production methods but makes the metric more permissive. A long easy shot can dominate brief difficult shots. Segment midpoint scoring can miss boundary errors; shot boundaries are a separate metric only for entries with `cuts`. Real material, audio, packaging and aspects are separate partial checks and must not be conflated with class accuracy.

## Dataset and labeling review

- `eval/labels.yaml` lists 15 development/tuning videos, many from capsule-cinema production records; some labels are source-record-based, others manual judgments. Mixed videos carry segments and acceptable label sets.
- `eval/holdout.yaml` lists nine videos and was described as not used during tuning initially. `eval/RESULTS.md` later states that all three known sets had been used to select rules; this makes holdout results in subsequent iterations non-independent.
- `eval/holdout2.yaml` lists seven entries and is documented as first run after all rule changes, but only the recorded run proves the claim; it is a small sample and not a permanent blind set. Later additions/tuning history should be tracked.
- `eval/articles.yaml` references 10 video files not present in this checkout (the associated set is platform-compressed; the docs note original platform tags are stripped from samples). Its labels are manually/externally described and some entries are excluded/uncertain.
- `eval/koubo.yaml`, `daihuo.yaml`, `film.yaml`, `audio_mv.yaml` add focused cases. `RESULTS.md` records difficult scores and correction examples, but these evolving sets are diagnostic, not independent validation.
- Overlay truth JSON is partly exported from the same maker's overlay code, and holdout comments explicitly flag packaging truth as not independent. Audio source annotations sometimes rely on generation records. Ground-truth provenance is therefore mixed.
- Some labeled content is ambiguous by nature: stable 3D-style AI vs true CG, screenshots embedded in code-render scenes, platform transcoding, subtle AI edits, and source attribution. The taxonomy/skill appropriately calls for review, but score claims need uncertainty categories and adjudication.

## Recorded numbers and interpretation

README reports 98.3% tuning accuracy, 99.6% / 98.9% holdout scores, 88.6% on re-encoded WeChat videos for tools-only, and 99.6–100% after VLM/agent review. `eval/RESULTS.md` contains historical changes, known errors, and more recent partial-subset reruns (for example labels with seven locally available items). It also records difficult `daihuo` results and known failure modes. These are self-reported development outputs; they were not independently reproduced in this audit.

The README's “shot boundaries are all correct” and broad real-asset range lack enough context in the headline to establish population-level generalization. Accuracy should be labeled with dataset name, n videos/shots/seconds, metric, tool version, whether media were re-decoded or cached, and whether VLM/agent review occurred.

## Reproducibility status

`eval/*.yaml` paths largely point to `${CAPSULE}` outputs or ignored local `eval/media/`. This checkout has no `eval/media` directory and no capsule-cinema checkout was supplied. Therefore no fresh `rea-video eval` score could be produced without unavailable local media. `RESULTS.md` records manual commands/results, but not a complete immutable set of media hashes, labels/adjudication, exact dependencies/model hashes, VLM provider/model snapshots, and run artifacts for each headline row. The reported numbers are **not independently reproducible from this checkout**.

Evaluation code's reuse mode reads cached `breakdown.json` and reuses prior features/results; this is convenient for regression, but results should state fresh decode versus reuse. `--fresh`/`--only` options exist; blind comparison should force fresh decoding and isolate output/cache.

## Blind evaluation proposal

1. Recruit an independent curator to select a stratified, consented set of at least 100 videos and enough shot-level cases per class, including short/long, 1080p/4K, VFR, platform-reencoded, mixed-media, and low-quality footage. Keep a second larger sealed set for final release claims.
2. Remove filenames, metadata and contextual clues from annotators and system operators; preserve original metadata only as a separately scored signal condition. Keep all source URLs and production records sealed from the model operator.
3. Have two annotators label shot boundaries and production class independently, with timestamp evidence; adjudicate disagreements and mark irreducible ambiguity as an accepted set or `unknown`. Separate ground truth for AI edits, embedded assets, audio source and overlays.
4. Freeze labels, media SHA-256, code commit, dependencies, model/checkpoint hash, VLM endpoint/model, prompt, cache state and run configuration before scoring. Run offline deterministic and VLM conditions separately, fresh, without prior outputs or cache.
5. Report per-class precision/recall/F1 and confusion matrix; macro/micro and duration-weighted scores; per-video distribution; boundary precision/recall/F1 at ±50/100/250ms; calibration (Brier/ECE); confidence intervals by resampling videos, not shots; failures/abstentions and compute/cost.
6. Hold final test labels with a custodian and allow one registered evaluation per release candidate. No rules may be tuned against sealed results; any resulting fix requires a new blind set.
7. Publish the protocol and reproducible evaluator; release hashes and aggregate results even if copyrighted media cannot be redistributed.

## Finding

**Confirmed:** headline values are claims over small development datasets and are not independently verified here; historical tuning undermines holdout independence for later iterations. This does not prove the algorithms are inaccurate. New blind evaluation is required before describing 98–100% as a production-wide accuracy rate.
