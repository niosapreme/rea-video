# Performance Review

## Evidence available

No controlled runtime or peak-memory benchmark was run: the repository contains no standardized benchmark command/corpus, and evaluation media referenced by YAML are absent. Therefore no throughput numbers are claimed. Existing unit tests establish behavior on their fixtures, not 4K or multi-minute scale.

## Likely cost centers from implementation

- **Decode and shot tracking:** `shots.build_track()` traverses decoded frames to create histograms/differences and retains per-frame thumbnail data; VFR timestamp handling may invoke `ffprobe` packet enumeration. CPU scales with decoded frame count.
- **Per-shot feature sampling:** `pipeline.decompose()` collects sampled frames/features for every shot and retains `samples_by_shot`; it also accumulates template frames. Memory scales with shot count and sampled resolution.
- **Packaging/OCR:** `packaging.analyze()` performs OCR and dense frame passes for text timing/stickers. RapidOCR adds inference and native package overhead. Fine sampling is likely expensive on long videos.
- **Audio:** signal analysis decodes audio into arrays; `stems.load_stereo()` captures all decoded stereo float samples in subprocess stdout and copies to NumPy; ONNX model inference runs CPU chunks. Five minutes at 44.1kHz stereo float32 is about 106 MB per full raw array, excluding copies/STFT/model buffers. 90 seconds is about 19 MB raw. These are arithmetic estimates, not measured peak RSS.
- **VLM:** clips and multiple frame images are base64 encoded into request JSON; request memory can multiply media size. Calls run in a thread pool and timeout may be 180s; model fallback retries can extend latency.
- **Artifacts:** shot thumbnails, contact sheets, extracted clips/stems and reports consume disk roughly with shot count and configured outputs. Existing output cleanup/retention policy is not a comprehensive quota.
- **Concurrency:** VLM uses configurable worker count (default 3) and still generation uses four workers. CPU-bound NumPy/OpenCV/ONNX threading can oversubscribe these pools depending on native library defaults.

## Workload suitability (qualitative)

| Input | Current confidence | Main concern |
|---|---|---|
| 15s social video, 1080p | Likely practical on a modern Intel Mac; not measured | OCR/stem model startup may dominate; model download on first stem run. |
| 30–90s promotional video | Likely practical but runtime unknown | repeated decode passes (shots, samples, packaging, audio, VLM) and per-shot artifacts. |
| 3–5m video | Unverified | audio/stem arrays, high shot counts, dense packaging scans, larger reports and VLM request count. |
| 4K source | Unverified | decode cost and full-size extraction; most image measurements are sampled/scaled, but not every stage is proven bounded. |
| Mixed live/AI/MG | Supported at shot/segment architecture level | classification/fusion and boundary errors propagate; benchmark evidence is weak for generalization. |

## Recommended benchmark matrix

Use fixed local clips and record hardware (Intel model/core count/RAM), OS, Python, FFmpeg build, dependency versions, model hashes, VLM setting, cache state, and thread counts. Measure wall time per stage, CPU time, peak RSS, max request bytes, temporary/output disk, shot count and failure/retry count. Test 15s, 60s, 90s and 5m at 1080p and 4K; 24/30/60fps plus VFR; audio absent/present; subtitles dense/sparse; offline and VLM modes. Run each case three times cold and warm, report median and range.

## Candidate improvements

1. Set explicit maximum dimensions/sample counts and expose them in run manifest.
2. Stream audio through FFmpeg pipes/chunks and avoid retaining decoded PCM plus derived arrays simultaneously.
3. Bound packaging frame density by duration and early stop or report skipped work.
4. Release per-shot samples after use; store compact uint8/scaled representations only where needed.
5. Bound native thread count alongside Python pools and benchmark worker tuning.
6. Cap VLM media payload size, request count, retry time and total elapsed time.
7. Add disk quota/retention controls and report artifact sizes.

All should be validated with measured quality/performance tradeoffs; no benchmark result is fabricated in this report.
