# REA-VIDEO Engineering Audit

**Date:** 2026-11-09  
**Scope:** read-only engineering/security review of branch `codex/full-audit`; this audit adds reports only. No application code, global agent settings, APIs, or external models were changed or called.

## Executive summary

The repository is a substantial local-first Python toolkit: it probes media, detects shots, extracts image/audio features, classifies shot content using deterministic heuristics and optional OpenAI-compatible VLM calls, builds packaging/audio/remake reports, and offers review/evaluation workflows. It is not a general video-understanding model and does not itself generate replacement video. Several outputs are measurements or heuristic inferences whose reliability is format- and content-dependent.

The strongest concern is benchmark interpretation. README headline scores (98–100%) describe duration-weighted label agreement on small, partly development-derived datasets. The evaluation helper supports acceptable label sets and scores each predicted shot at its midpoint, so these scores are not conventional independent frame-level or video-level accuracy. Evaluation files reference media outside this checkout, preventing independent reproduction here. `eval/RESULTS.md` itself documents cases around 46% on a difficult mixed dataset and agent/VLM corrections, contradicting broad unqualified accuracy impressions.

No confirmed critical security vulnerability was established in this static audit. External inputs are passed to subprocesses as argument arrays in reviewed paths; reports escape HTML; model downloads have SHA-256 checks. Material risks/gaps remain: a user-configured VLM can receive full video clips/frames and keys are sent to arbitrary configured endpoints; cache files contain returned model analyses; downloader integrity lacks signed provenance; output-path writes are broad and overwrite existing report artifacts; install script can replace an existing symlink and may install editable source into the selected Python environment.

### Confirmed major findings

- **P1 accuracy claims are not independently established.** See ACC-01: small, evolving datasets; some “holdout” material became non-independent for later tuning; labels can be ambiguous; missing media means scores cannot be reproduced from this checkout.
- **P1 high-resolution/long-video scalability has not been measured.** Analysis decodes/samples repeatedly and can keep per-shot arrays, thumbnails, audio, packaging frames, and concurrent still-generation jobs in memory. No resource budget or performance benchmark is present.
- **P1 unsupported or uncertain advertised capabilities are described as complete.** AI/live/3D attribution, detailed sound-source attribution, light/camera interpretation, and “all shot boundaries correct” are heuristic or agent-assisted and lack broad independent validation.
- **P2 VLM privacy and cost controls are limited.** Configurable arbitrary HTTP(S) OpenAI-compatible endpoints, per-call timeout/retry and call cap exist; no explicit spend/rate budget, endpoint allowlist, payload-size policy, or user-facing data-flow confirmation is implemented.
- **P2 install lifecycle is not transactional.** `scripts/install_skill.sh` installs editable code (pip/pipx/venv fallback), changes the selected Python environment, and links skills into global agent directories; rollback/version pinning is absent and existing symlinks may be replaced.
- **P2 audio stem model downloads are size-independent but hash-verified.** It is downloaded at first stem extraction; this can add network dependency and CPU time. No network/model download was performed for this audit.

### Issue counts

| Severity | Count | Notes |
|---|---:|---|
| P0 | 0 | No confirmed exploitable critical issue found in reviewed paths. |
| P1 | 4 | Benchmark validity, shot-boundary evidence, resource scalability, advertised capability calibration. |
| P2 | 8 | Privacy/cost, audio capability boundary, install lifecycle, destructive output behavior, portability, package reproducibility, observability. |
| P3 | 3 | Additional blind evaluation, clearer uncertainty UX, richer performance instrumentation. |

These counts cover the finding IDs in `GAP_MATRIX.md`; security classifications are summarized in `SECURITY_REVIEW.md`.

### Top five remediation priorities

1. Establish a truly blind, versioned benchmark with provenance, ambiguity policy, per-class metrics, confidence intervals, and immutable test labels.
2. Define and test resource ceilings for 4K/long footage; reduce retained arrays, stream audio, bound concurrent work, and report measured peak RSS/runtime.
3. Add a separate independent shot-boundary test set and publish precision/recall/F1/tolerance, not a blanket “all correct” statement.
4. Make VLM data transfer/cost explicit; enforce safer timeout, size, concurrency, endpoint and retry budgets, and document cache contents/retention.
5. Replace implicit editable/global installation with an explicit versioned shared CLI plus owned, reversible agent skill links that refuse to replace user content.

## Coverage and method

Inspected source modules in `rea_video/` and `rea_video/aspects/`, capability maps, all tests, all evaluation YAML/JSON and recorded results, scripts, packaging metadata, README/docs, AGENTS/CLAUDE instructions, skill and references, and integration scripts. Ran the existing pytest suite in `.venv`; ran capability validation without matrix generation. No paid service, web lookup, install, video evaluation or model download was performed. The referenced evaluation media are absent from this checkout.

## Detailed reviews

- [Feature inventory](FEATURE_INVENTORY.md)
- [Gap matrix](GAP_MATRIX.md)
- [Security review](SECURITY_REVIEW.md)
- [Accuracy review](ACCURACY_REVIEW.md)
- [Performance review](PERFORMANCE_REVIEW.md)
- [Agent integration plan](AGENT_INTEGRATION_PLAN.md)
- [Remediation roadmap](REMEDIATION_ROADMAP.md)

## Validation results

- Branch: `codex/full-audit` (verified).
- Existing suite: **178 passed, 3 skipped** (locally observed; see final run output in completion message).
- Capability validator: **43 primitives, 16 metrics, 76 model entries (75 available), 21 visual rules, 5 audio rules; passed**.
- Dataset reproduction: **not run**; required media are not present in `eval/` and default capsule-cinema paths are external to this repository.
- Working tree changes are the eight new Markdown audit documents only.

## Limitations and unresolved questions

Static inspection cannot establish runtime exploitability, exact 4K memory/time, platform behavior on a second host, VLM-provider privacy terms, or accuracy beyond available recorded evidence. The `eval/RESULTS.md` history and dataset paths need matching immutable media, labels, pipeline revision, model/configuration, and run artifacts for full reproduction. No network or external source validation was performed, so current external model/provider capability claims were not independently checked.
