# Security Review

## Summary

No confirmed critical exploit was found during static inspection. The security posture benefits from argv-based subprocess calls, escaping in HTML rendering, explicit exclusions for current-directory `.env`, containment checks in remake integration, and SHA-256 checks for downloaded model files. Residual risks below are confirmed design properties or verification gaps, not claims of known exploitation.

## Reviewed attack surfaces

| Surface | Evidence / existing controls | Assessment |
|---|---|---|
| Subprocess | `media.py`, `stems.py`, integrations and CLI pass argument lists to `subprocess`; no `shell=True` found in reviewed app code. | Shell injection not confirmed. Input/output paths still influence file operations and ffmpeg parsing. Keep argv use and consider `--`/protocol restrictions where supported. |
| Arbitrary paths / overwrite | User supplies media/output paths; report and image/audio artifacts are written under output; FFmpeg uses `-y`; evaluation reads YAML-specified paths; memory/prefs write under home. | No confirmed traversal from a crafted media name into another location, but output collision/overwrite is real (OUT-01). Treat paths as user-authorized, preflight outputs and avoid destructive implicit overwrite. |
| HTML/script injection | `report.py` escapes values and allows controlled raw tags; `tests/test_security.py` covers bad URL schemes, event attributes and raw HTML. | Existing tests are positive controls. Continue context-specific escaping and test generated reports with hostile VLM/user data, not only markdown helpers. |
| VLM credentials and payload | `vlm.py` sends Bearer key over configured URL, warns on non-local HTTP, and can send clips/frames. Cache identity intentionally excludes key. | Endpoint is operator-selected, but plaintext HTTP can expose credentials; arbitrary endpoint can receive private video. Add HTTPS-by-default/explicit local exception and explicit privacy/host review. Avoid embedding credentials in URL; `describe()` attempts to redact userinfo. |
| VLM cache | JSON answers written to cache directory; cache entries contain model response and may include descriptions/prompts, not API key. | Sensitive derived content persists with no documented retention/permission policy. Restrict permissions, support purge/disable, avoid following symlinks, document contents. |
| Downloaded ONNX models | `stems.py` and `faces.py` download from GitHub and validate fixed SHA-256; use temporary names and atomic replacement in stems path. | Integrity against accidental/malicious content substitution is improved; digest source is in same repository and no signed release provenance is checked. No download occurred in this audit. Add provenance/update process and content-size/timeout handling. |
| Network / SSRF | VLM base URL is environment-configurable and requests are sent to it; model download URL fixed. | For a local CLI, configured endpoint is trusted operator input. If called from a hosted service with untrusted config, private-network/metadata-service SSRF is possible; no service deployment is evidenced. Validate scheme/host if embedding. |
| Configuration / secrets | `.env` loader only reads selected explicit/prefs/repo config; does not read cwd `.env` (security regression test). Existing env takes precedence. | Good cwd defense. Repo-local `.env` is intentionally read when present; secret scanning and restrictive permissions are needed. Audit did not open any secret files. |
| Skill instructions | `SKILL.md` directs shell commands and optionally calls paid remake only after user confirmation; install instructions suggest repo install. | Agent instructions are operational guidance, not a sandbox. Avoid prompt-injection via media-derived text; VLM/OCR content must remain untrusted data. Confirm before paid generation. |
| Dependencies / supply chain | Core packages use version ranges, optional OCR brings native OpenCV conflict (script removes duplicate), no lock file observed. | Reproducibility/supply-chain gap DEP-01; no specific vulnerable dependency established. Run an authenticated dependency audit in a separate authorized phase. |
| Installer | `scripts/install_skill.sh` installs editable local project and creates global links; skips a real directory but replaces existing symlink with `ln -sfn`. | No silent deletion of real directories observed; symlink replacement and non-transactional installs are confirmed lifecycle risks (INST-01). |

## P0/P1 security disposition

- P0 confirmed vulnerabilities: **0**.
- P1 confirmed security findings: **0**.
- P2: privacy/cost controls (PRIV-01/COST-01), global installer ownership and output overwrite behavior (INST-01/OUT-01), dependency provenance (DEP-01).

## Security acceptance priorities

1. Make the VLM endpoint/payload scope explicit; reject plaintext remote HTTP by default; keep local HTTP opt-in.
2. Add robust output collision handling before any media processing; ensure report/artifact generation does not overwrite unrelated files.
3. Make cache permissions and retention explicit; provide cache clearing and disabling.
4. Preserve digest verification and document the trusted hash update/review process; use download timeouts, size bounds and atomic installation for all model assets.
5. Test hostile OCR/VLM strings through the complete HTML report path and malicious paths through CLI/integration flows.

## Limits

This was code inspection and existing tests only. No fuzzing, dynamic taint analysis, dependency advisory scan, network interception, malicious media, or model download was performed. No report should be read as proof of absence of vulnerabilities.
