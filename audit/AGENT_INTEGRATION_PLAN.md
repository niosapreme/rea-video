# Codex and Claude Code Integration Plan

## Current state

- `AGENTS.md` delegates video workflows to `skills/rea-video/SKILL.md`; `CLAUDE.md` includes `@AGENTS.md`, so both project entrypoints share instructions.
- Skill content is project-local at `skills/rea-video/` and includes workflow plus references.
- `scripts/install_skill.sh` installs `pip install -e "$ROOT[ocr]"` into the selected Python, with pipx or repository `.venv` fallback, then symlinks the skill to existing `~/.claude/skills`, `~/.codex/skills`, and `~/.agents/skills` directories (or defaults to Claude location if none exist). The installed command may point into this checkout; this is one implementation but not a managed, immutable shared distribution.
- Script skips a real destination directory but uses `ln -sfn` for existing symlinks. It has no uninstall, version pin, ownership marker, rollback or post-install validation of the installed CLI. Repo docs direct users to run `rea-video --help` manually.
- Codex/Claude global configuration was not inspected or altered. No global settings were changed.

## Target architecture

Use one canonical implementation under a stable user-owned location, e.g. `~/.local/share/rea-video/versions/<version>` with a managed isolated environment and a stable `~/.local/bin/rea-video` launcher. Pin release/tag or commit and dependency constraints; update by staging a new version, smoke-checking it, atomically switching a managed `current` pointer, and retaining the previous version for rollback. The project checkout can remain the development source but should not be the only executable location for daily agent use.

Install exactly one skill payload from the same release into the agent skill discovery locations. Where both agents support a common `~/.agents/skills/rea-video` convention, prefer that shared target and verify each product's documented discovery behavior for the installed versions. Use separate per-agent symlinks only when required. Do not copy the skill into project instructions; project `AGENTS.md`/`CLAUDE.md` should say when to invoke the globally installed skill and preserve repository-specific rules.

## Safe install/update/rollback behavior

1. **Preflight:** identify Python/architecture/OS, FFmpeg/ffprobe, target paths and existing command; show target/version before mutation. Never read or alter agent settings files.
2. **Own only marked resources:** write a manifest containing installer version, release, canonical target and links it created. If a destination exists, leave it alone unless its symlink target and ownership manifest prove this installer created it. Refuse ambiguity.
3. **Stage:** create a new versioned environment in a temporary sibling directory; install pinned package and optional OCR; do not use `--break-system-packages`, editable installs, or global Python packages.
4. **Verify:** run CLI help and small local fixture smoke test, verify model downloads are not triggered unless selected, and verify imports against intended environment.
5. **Activate atomically:** switch only the managed launcher/link after checks pass; preserve prior version and logs. On failure, clean only the new staging directory and preserve old version.
6. **Uninstall:** remove only manifest-owned links/version directories; never recursively remove an unmarked path. Keep user cache/model files unless explicitly chosen.
7. **Architecture portability:** create a fresh environment on Apple Silicon; do not copy Intel virtualenvs or binary wheels. Maintain architecture-independent skill and source; resolve native wheels on target. Validate arm64 and x86_64 CI.

## Codex and Claude organization

- **Global skill:** shared reusable workflow under each agent's supported global skills directory; install once in a managed common directory and symlink only when the platform supports it.
- **Project-specific instructions:** keep repository policy in `AGENTS.md`; `CLAUDE.md` can include it. Do not duplicate full workflow there.
- **CLI:** one canonical managed environment; agent-specific skills call the same `rea-video` executable.
- **Future sessions/projects:** global skill discoverability is independent of the current project checkout; project instructions can opt in without installation duplication.
- **Future Apple Silicon:** repeat staged install from pinned source/dependencies on arm64 and revalidate native packages; keep user data caches separate from executable version directories.

## Acceptance criteria before implementation

- Existing non-owned file, directory, symlink, PATH entry, or agent settings remain byte-for-byte unchanged.
- Installer supports dry-run, install/update, rollback and uninstall with explicit output; second run is idempotent.
- `rea-video` resolves to exactly one canonical implementation and its version/build is queryable.
- Codex and Claude Code discover one skill version each, without duplicate copies or conflicting project instructions.
- Failed install leaves previous CLI operational; update on Intel and Apple Silicon independently passes smoke tests.

This is a proposed design only; no global settings or installation were changed during this audit.
