# Remediation Roadmap

## Phase 0 — Establish evidence and release gates

**Priorities:** ACC-01, VID-01, PERF-01, MODEL-01.  
Freeze current commit/dependency/model identifiers, recover or reconstruct media inputs, document label provenance, and register a blind evaluation protocol before changing heuristics. Add per-class and boundary metrics to a release gate. Keep all existing scores labeled as development-set results until this is complete.

**Exit:** an independent evaluator can run deterministic and VLM conditions from fresh outputs, explain every label and boundary, and produce a signed results manifest with hashes.

## Phase 1 — Reduce user-facing risk

**Priorities:** OUT-01, PRIV-01, COST-01, INST-01.  
Add output preflight/atomic writes and explicit force behavior. Require VLM opt-in with a clear endpoint/media-scope summary, secure transport defaults, request concurrency and total budgets. Replace installer behavior with a staged, versioned, ownership-aware update/rollback/uninstall flow.

**Exit:** collision, privacy, budget and install tests prove unrelated files/configurations are unchanged and caps cannot be exceeded.

## Phase 2 — Measure and bound runtime

**Priorities:** PERF-01, PERF-02, DEP-01, PORT-01.  
Add reproducible benchmark fixtures and stage metrics; test 1080p/4K and duration matrix on Intel and Apple Silicon. Then reduce duplicate decodes/full audio materialization/retained samples as measurements justify. Add dependency constraints and supported platform CI.

**Exit:** published median/range time and peak RSS for declared workloads, no uncontrolled memory growth, cross-architecture smoke tests.

## Phase 3 — Clarify capabilities and unsupported cases

**Priorities:** AUDIO-01, UX-01, OBS-01.  
Label heuristic audio-source claims as inferred, clearly state transcription is not implemented, surface uncertainty/required review, and persist sanitized stage status/version/timing records.

**Exit:** reports distinguish evidence, model opinion, and operator review; failures identify stage and recovery action without exposing secrets.

## Phase 4 — Maintain independent evaluation

**Priorities:** EVAL-01.  
Create safe blind-data staging and scoring tools, maintain a sealed final dataset, and publish score cards per release. Every rule tuning iteration consumes only development data.

**Exit:** blind-set custody and scoring are independent of code authors; no benchmark data or labels leak into skill prompts or tuning records.

## Priority ordering summary

1. Blind evaluation and headline claim correction.
2. Shot-boundary evaluation and uncertainty calibration.
3. Resource benchmark and bounds for 4K/long inputs.
4. VLM privacy, endpoint, and cost controls.
5. Safe installer and output overwrite protections.

## Audit boundary

No remediation was implemented. ChatGPT/user review is expected before code changes; the next engineering phase should select acceptance criteria from this roadmap and preserve the audit as a baseline.
