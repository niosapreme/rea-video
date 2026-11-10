# Feature Inventory

## Implemented capabilities (verified in source)

| Area | Implementation | Boundaries / evidence |
|---|---|---|
| CLI and workflow | `rea_video/cli.py`, `__main__.py`; decompose, summary, review/apply-review, correction/memory, evaluation, tiles, report export, remake planning/assembly | Main entry point declared in `pyproject.toml`; workflow documented in `skills/rea-video/SKILL.md`. |
| Media metadata | `media.py`, `probe.py` | `ffprobe` metadata, dimensions/rate/aspect/duration, provenance tags and generator markers. Metadata is not proof when absent. |
| Shot detection | `shots.py` | Frame histogram/pixel differences, cuts, fades/wipes and motion-aware logic; eval helper has boundary-F1 utility, but available main datasets do not establish broad boundary performance. |
| Visual classification | `features.py`, `classify.py`, `pipeline.py` | Sampled spatial/noise/cadence/motion/overlay facts, deterministic scores and fusion across 11 labels. It is heuristic; mixed-media cases and transcoding are known weaknesses. |
| Optional vision model | `vlm.py`, `pipeline.py` | OpenAI-compatible chat completions; configurable base URL/key/model list; frame/clip payloads; concurrent shot requests; response parsing/normalization, fallback models, local JSON cache. Not a built-in provider integration. |
| OCR and overlays | `overlay.py`, `packaging.py` | Optional RapidOCR, subtitle/text timing and appearance, sticker/motion heuristics, SRT/ASS exports. OCR extra is optional; accuracy depends on language and visual quality. |
| Audio | `audio.py`, `sound_source.py`, `stems.py` | Signal-level voice/music/beat/BPM/key and transient/event heuristics; optional UVR ONNX instrumental extraction; rule-based source guesses with optional VLM. No audio speech transcription implementation observed. |
| Camera/aspects | `aspects/` | Derived framing, movement, lighting/grade/editing/subject summaries and VLM/review fields. Many scene interpretation details are inference, not direct physical measurement. |
| Real assets | `assets.py` | Detects embedded footage/images/screenshots and distinguishes reference material. Documented misses include dark/translucent images. |
| Reports | `report.py`, `visual.py` | Markdown/HTML, storyboard, shot contact sheets, audio timeline, stems, subtitle exports. HTML escapes content and restricts links in tested helpers. |
| Remake integration | `production.py`, `remake.py`, `integrations/` | Plans generation units from capability YAML and invokes local capsule-cinema helper; does not implement video generation itself. Dry-run is available; real generation may be paid and external. |
| Evaluation | `evaluate.py`, `eval/*.yaml`, `tests/` | Duration-weighted shot-class agreement, per-video mean, real-material, optional audio/aspect/packaging checks and cuts F1. Evaluation is not an independent benchmark by itself. |
| Agent skill | `skills/rea-video/` | Workflow instructions, taxonomy/review/audio/material/remake/setup references. Global linking behavior is in install script. |

## Advertised claims and verification status

- **“98%–100% accuracy”**: recorded score claim, not independently verified. Metric and data limitations are detailed in `ACCURACY_REVIEW.md`.
- **“all shot boundaries correct”**: a README claim without a matching broad boundary benchmark shown there; specific cut F1 exists only on configured entries. Not established for arbitrary inputs.
- **“real-asset detection 97–99%”**: code and some recorded evaluation support a dataset-specific metric; truth coverage and generalization are limited.
- **AI music / music source and SFX detection**: signal and rule heuristics exist; source labels are inference and weak sound effects are expressly noted as low-confidence. Not transcription-grade audio understanding.
- **11 production methods**: classifier labels and optional VLM prompt support these categories. Film, 2D animation, stop motion and nuanced AI edits are not uniformly measured; many require manual visual review.
- **Shot-by-shot prompts and model recommendations**: VLM can emit descriptions/prompts; capability YAML routes planning. Endpoint quality and the changing external capability catalog are unverified; no model inference occurs for generation in this repository.
- **Cross-platform support**: Python/platform-neutral intent, but installer uses shell/Bash and macOS/Linux examples. No Windows installer/CI evidence was found.
- **Offline mode**: deterministic analysis is local, but ONNX stem extraction can trigger a first-run GitHub download; OCR model availability and optional VLM are separate. Not every run is necessarily network-free.

## Dependencies and services

- Required Python dependencies: NumPy, headless OpenCV, Pillow, PyYAML, ONNX Runtime; Python >=3.10. OCR extra adds `rapidocr-onnxruntime`; dev extra adds pytest/jsonschema.
- Required system tools: `ffmpeg` and `ffprobe`.
- Optional external services: any configured OpenAI-compatible VLM endpoint; capsule-cinema and its configured generation/model services for remake execution.
- Downloaded model: UVR MDX-Net ONNX (~67 MB) from a GitHub release; checked against a hard-coded SHA-256 before use.
- Model catalog: YAML capability metadata for 76 models, not SDK integrations. It may become stale.

## Filesystem and network behavior

- Reads input media and optional JSON/YAML labels, config, and review files; writes analysis artifacts under user-selected output path (breakdown, reports, frames, audio stems, packaging output, caches).
- Writes user memory/prefs under `~/.rea-video`; model cache under `~/.cache/rea-video/models` or `REA_VIDEO_MODELS`; VLM response cache under analysis output/cache path.
- Calls `ffmpeg`/`ffprobe` with argv arrays; downloads ONNX model using `urllib`; sends frames/video and prompts to configured VLM using `urllib`; remake integration starts a configured Python interpreter and local scripts.
- Detailed risks and controls appear in `SECURITY_REVIEW.md`.

## Tests and evaluation

Tests cover classifier, fusion, shots, transcode, OCR, motion, audio, stems, report/escaping, VLM mock/cache, packaging, security, robustness and production planning. They are mostly unit/regression tests with mocks and local fixtures, not broad real-world quality or scale tests. Evaluation docs recommend a blind copy and independent agent assessment, but the included protocol is manual and currently lacks an immutable blind dataset bundled in this checkout.
