#!/usr/bin/env python3
"""Versioned, user-owned rea-video installation. No agent settings are edited."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SCHEMA = 1
OWNER = "rea-video-managed-installer"


@contextmanager
def installer_lock(base: Path):
    """Nonblocking Unix advisory lock; the persistent inode is safe to reuse."""
    if exists(base) and (base.is_symlink() or not base.is_dir()):
        raise RuntimeError(f"Unowned installation root: {base}")
    base.mkdir(parents=True, exist_ok=True)
    path = base / ".installer.lock"
    if path.is_symlink() or (exists(path) and not path.is_file()):
        raise RuntimeError(f"Unowned installer lock path: {path}")
    with path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Another rea-video installer is running (lock: {path})") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def identity(source: Path) -> str:
    version = re.search(r'^version\s*=\s*"([^"]+)"', (source / "pyproject.toml").read_text(), re.MULTILINE).group(1)
    try:
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "--short=12", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "source"
    digest = hashlib.sha256()
    for path in snapshot_files(source):
        digest.update(str(path.relative_to(source)).encode())
        digest.update(path.read_bytes())
    return f"{version}-{commit}-{digest.hexdigest()[:12]}"


def snapshot_files(source: Path) -> list[Path]:
    files = [source / "pyproject.toml", source / "README.md"]
    for folder in ("rea_video", "skills/rea-video"):
        for path in (source / folder).rglob("*"):
            relative = path.relative_to(source)
            if any(part.startswith('.') or part in ('__pycache__', 'build', 'dist', 'out', 'outputs') for part in relative.parts):
                continue
            if path.is_symlink():
                raise RuntimeError(f"Source snapshot refuses symlink: {path}")
            if path.is_file() and path.suffix in ('.py', '.md', '.yaml', '.yml', '.json'):
                files.append(path)
    return sorted(files)


def exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def atomic_link(target: str, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.symlink_to(target)
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


def save(path: Path, data: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_manifest(path: Path, base: Path) -> dict | None:
    if not exists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Unowned manifest path: {path}")
    data = json.loads(path.read_text())
    if data.get("owner") != OWNER or data.get("schema") != SCHEMA or data.get("installation_dir") != str(base):
        raise RuntimeError(f"Invalid ownership manifest: {path}")
    for key in ("active_version", "launcher_path", "skill_links"):
        if key not in data:
            raise RuntimeError(f"Incomplete ownership manifest: {path}")
    if (not isinstance(data["active_version"], str) or Path(data["active_version"]).name != data["active_version"]
            or data["launcher_path"] != str(base.parent.parent / "bin/rea-video")
            or not isinstance(data["skill_links"], list)):
        raise RuntimeError(f"Invalid ownership manifest: {path}")
    return data


def owned_version(path: Path, base: Path) -> bool:
    if path.parent != base / "versions" or path.name in (".", ".."):
        return False
    marker = path / ".rea-video-owner.json"
    if path.is_symlink() or not path.is_dir() or not marker.is_file() or marker.is_symlink():
        return False
    try:
        data = json.loads(marker.read_text())
    except (ValueError, OSError):
        return False
    return data == {"owner": OWNER, "path": str(path), "schema": SCHEMA}


def recover(base: Path, manifest: dict | None, dry_run: bool) -> dict | None:
    current = base / "current"
    if manifest is None:
        if exists(current):
            raise RuntimeError("Recovery refused: current exists without an ownership manifest")
        return None
    expected = manifest["active_version"]
    target = os.readlink(current) if current.is_symlink() else None
    if exists(current) and (target is None or not target.startswith("versions/") or Path(target).parts != ("versions", Path(target).name)):
        raise RuntimeError("Recovery refused: current is not a managed version pointer")
    selected = Path(target).name if target else expected
    if not owned_version(base / "versions" / selected, base):
        raise RuntimeError(f"Recovery refused: ownership cannot be proven for {selected}")
    if target == f"versions/{expected}":
        return manifest
    verify(base / "versions" / selected, selected.rsplit("-", 1)[0])
    if dry_run:
        raise RuntimeError("Recovery required; rerun without --dry-run to reconcile owned state")
    if target is None:
        atomic_link(f"versions/{expected}", current)
    else:
        manifest = {**manifest, "active_version": selected, "installed_version": selected.rsplit("-", 1)[0],
                    "prior_active_version": expected}
        save(base / "manifest.json", manifest)
    return manifest


def check_link(path: Path, target: str, recorded: list[str]) -> None:
    if exists(path) and (str(path) not in recorded or not path.is_symlink() or os.readlink(path) != target):
        raise RuntimeError(f"Unowned or changed path; refusing to overwrite: {path}")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def verify(version_dir: Path, version: str) -> None:
    executable = version_dir / "venv/bin/rea-video"
    run([str(executable), "--help"])
    result = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True)
    if version not in result.stdout:
        raise RuntimeError(f"CLI version mismatch: {result.stdout.strip()}")
    run([str(version_dir / "venv/bin/python"), "-c", "import rea_video, cv2, numpy, onnxruntime; assert rea_video.__file__"])
    if not (version_dir / "skill/SKILL.md").is_file():
        raise RuntimeError("Skill payload missing")


def make_directory(path: Path, created: list[Path]) -> None:
    if path.is_dir():
        return
    if exists(path):
        raise RuntimeError(f"Unowned path blocks installation: {path}")
    make_directory(path.parent, created)
    path.mkdir()
    created.append(path)


def restore_pointer(path: Path, prior_target: str | None) -> None:
    """Restore a pointer using a fresh temporary link, bypassing activation hooks."""
    if prior_target is None:
        path.unlink(missing_ok=True)
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.restore")
    try:
        temporary.symlink_to(prior_target)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def restore_manifest(path: Path, prior_bytes: bytes | None) -> None:
    if prior_bytes is None:
        path.unlink(missing_ok=True)
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.restore")
    try:
        temporary.write_bytes(prior_bytes)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def activate(current: Path, manifest_path: Path, launcher: Path, skill_paths: list[Path],
             manifest: dict | None, new_manifest: dict, key: str) -> None:
    """Undo every activation mutation if any step raises."""
    old_pointer = os.readlink(current) if current.is_symlink() else None
    old_manifest = manifest_path.read_bytes() if manifest else None
    created_links: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for path in skill_paths:
            make_directory(path.parent, created_dirs)
            if not exists(path):
                created_links.append(path)
                path.symlink_to(current / "skill")
        make_directory(launcher.parent, created_dirs)
        if not exists(launcher):
            created_links.append(launcher)
            launcher.symlink_to(current / "venv/bin/rea-video")
        atomic_link(f"versions/{key}", current)
        save(manifest_path, new_manifest)
    except BaseException as error:
        restore_errors = []
        for restore in (lambda: restore_pointer(current, old_pointer),
                        lambda: restore_manifest(manifest_path, old_manifest)):
            try:
                restore()
            except BaseException as exc:
                restore_errors.append(exc)
        for path in reversed(created_links):
            try:
                path.unlink(missing_ok=True)
            except BaseException as exc:
                restore_errors.append(exc)
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        if restore_errors:
            raise RuntimeError(f"Activation failed ({error}); restoration failed: {restore_errors}") from error
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["install", "update", "rollback", "uninstall"], default="install")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        return execute(args)
    home = args.home.resolve()
    with installer_lock(home / ".local/share/rea-video"):
        return execute(args)


def execute(args: argparse.Namespace) -> int:
    source = args.source.resolve()
    home = args.home.resolve()
    base = home / ".local/share/rea-video"
    versions = base / "versions"
    current = base / "current"
    manifest_path = base / "manifest.json"
    launcher = home / ".local/bin/rea-video"
    skill_paths = [home / f".{agent}/skills/rea-video" for agent in ("claude", "codex", "agents")]
    architecture = platform.machine().lower()
    if architecture not in ("x86_64", "arm64"):
        raise RuntimeError(f"Unsupported architecture: {architecture}")
    if sys.version_info < (3, 10):
        raise RuntimeError("Python >= 3.10 required")
    version = identity(source)
    key = f"{version}-{architecture}"
    destination = versions / key
    manifest = read_manifest(manifest_path, base)
    manifest = recover(base, manifest, args.dry_run)
    recorded = manifest.get("skill_links", []) if manifest else []
    print(f"OS: {platform.system()} | architecture: {architecture}")
    print(f"Python: {sys.executable} ({platform.python_version()})")
    print(f"ffmpeg: {shutil.which('ffmpeg') or 'MISSING'} | ffprobe: {shutil.which('ffprobe') or 'MISSING'}")
    print(f"Build: {version} | destination: {destination}")
    print(f"Current: {current} -> {os.readlink(current) if current.is_symlink() else 'absent or non-link'}")
    print(f"Launcher: {launcher} -> {os.readlink(launcher) if launcher.is_symlink() else 'absent or non-link'}")
    for path in skill_paths:
        print(f"Skill: {path} -> {os.readlink(path) if path.is_symlink() else 'absent or non-link'}")
    if exists(current) and (not manifest or not current.is_symlink() or os.readlink(current) != f"versions/{manifest.get('active_version')}"):
        raise RuntimeError(f"Unowned or changed active pointer: {current}")
    launcher_target = str(current / "venv/bin/rea-video")
    check_link(launcher, launcher_target, [manifest.get("launcher_path")] if manifest else [])
    for path in skill_paths:
        check_link(path, str(current / "skill"), recorded)
    if destination.exists() and not owned_version(destination, base):
        raise RuntimeError(f"Unowned version directory: {destination}")
    if args.action in ("install", "update"):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("ffmpeg and ffprobe are required")
        if not (source / "skills/rea-video/SKILL.md").is_file():
            raise RuntimeError("Source skill missing")
        if manifest and manifest["active_version"] == key:
            verify(destination, version)
            print("Already installed and active")
            return 0
        if args.action == "update" and not manifest:
            raise RuntimeError("Nothing installed to update")
        if args.action == "install" and manifest:
            raise RuntimeError("Already installed; use update")
        if args.dry_run:
            print("Dry run: no changes")
            return 0
        created_dirs: list[Path] = []
        make_directory(versions, created_dirs)
        candidate_created = False
        try:
            if not destination.exists():
                destination.mkdir()
                candidate_created = True
                (destination / ".rea-video-owner.json").write_text(json.dumps({"owner": OWNER, "path": str(destination), "schema": SCHEMA}))
                payload = destination / "source"
                payload.mkdir()
                for file in snapshot_files(source):
                    relative = file.relative_to(source)
                    output = (destination / "skill" / file.relative_to(source / "skills/rea-video")
                              if relative.parts[0] == "skills" else payload / relative)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, output)
                if identity(source) != version:
                    raise RuntimeError("Source changed during snapshot; retry with a stable checkout")
                (payload / "rea_video/_build.py").write_text(f"BUILD_ID = {version!r}\n")
                run([sys.executable, "-m", "venv", str(destination / "venv")])
                python = destination / "venv/bin/python"
                run([str(python), "-m", "pip", "install", f"{payload}[ocr]"])
                if subprocess.run([str(python), "-m", "pip", "show", "opencv-python"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    run([str(python), "-m", "pip", "uninstall", "-y", "opencv-python"])
                    run([str(python), "-m", "pip", "install", "--force-reinstall", "--no-deps", "opencv-python-headless>=4.8,<5"])
                shutil.rmtree(payload)
                verify(destination, version)
            else:
                verify(destination, version)
            new_links = list(recorded)
            new_links.extend(str(path) for path in skill_paths if not exists(path))
            old = manifest["active_version"] if manifest else None
            activate(current, manifest_path, launcher, skill_paths, manifest,
                     {"owner": OWNER, "schema": SCHEMA, "installed_version": version, "architecture": architecture,
                      "python_version": platform.python_version(), "installation_dir": str(base),
                      "active_version": key, "prior_active_version": old, "launcher_path": str(launcher), "skill_links": new_links}, key)
        except BaseException:
            if candidate_created and owned_version(destination, base):
                shutil.rmtree(destination)
            for path in reversed(created_dirs):
                try:
                    path.rmdir()
                except OSError:
                    pass
            raise
        print(f"Active: {key}")
    elif args.action == "rollback":
        if not manifest or not manifest.get("prior_active_version"):
            raise RuntimeError("No previous version to roll back to")
        target_key = manifest["prior_active_version"]
        target = versions / target_key
        if not owned_version(target, base):
            raise RuntimeError(f"Previous version is not installer-owned: {target}")
        verify(target, target_key.rsplit("-", 1)[0])
        if args.dry_run:
            print(f"Dry run: would restore {target_key}")
            return 0
        old = manifest["active_version"]
        updated = {**manifest, "active_version": target_key, "prior_active_version": old,
                   "installed_version": target_key.rsplit("-", 1)[0]}
        old_bytes = manifest_path.read_bytes()
        try:
            atomic_link(f"versions/{target_key}", current)
            save(manifest_path, updated)
        except BaseException:
            restore_pointer(current, f"versions/{old}")
            restore_manifest(manifest_path, old_bytes)
            raise
        print(f"Restored: {target_key}")
    else:
        if not manifest:
            print("Nothing installed")
            return 0
        if args.dry_run:
            print("Dry run: would remove installer-owned resources; user data preserved")
            return 0
        for path in skill_paths:
            if str(path) in recorded and path.is_symlink() and os.readlink(path) == str(current / "skill"):
                path.unlink()
        if launcher.is_symlink() and os.readlink(launcher) == launcher_target:
            launcher.unlink()
        current.unlink()
        for path in versions.iterdir():
            if owned_version(path, base):
                shutil.rmtree(path)
        manifest_path.unlink()
        print("Uninstalled; ~/.rea-video preserved")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"Installation error: {exc}", file=sys.stderr)
        raise SystemExit(1)
