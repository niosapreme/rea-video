"""Managed installer contract; all paths stay under tmp_path."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("managed", Path(__file__).resolve().parents[1] / "scripts/manage_install.py")
managed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(managed)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    source = tmp_path / "source"
    (source / "skills/rea-video").mkdir(parents=True)
    (source / "skills/rea-video/SKILL.md").write_text("skill")
    (source / "rea_video").mkdir()
    (source / "rea_video/__init__.py").write_text("__version__ = '0.1.0'")
    (source / "pyproject.toml").write_text('[project]\nname="rea-video"\nversion="0.1.0"\n')
    (source / "README.md").write_text("readme")
    monkeypatch.setattr(managed, "identity", lambda _: "0.1.0-abc")
    monkeypatch.setattr(managed.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(managed.shutil, "which", lambda name: f"/usr/bin/{name}")
    def fake_run(command):
        if command[1:3] == ["-m", "venv"]:
            path = Path(command[3]) / "bin"
            path.mkdir(parents=True)
            (path / "python").write_text("")
            (path / "rea-video").write_text("")
    monkeypatch.setattr(managed, "run", fake_run)
    monkeypatch.setattr(managed, "verify", lambda path, version: None)
    monkeypatch.setattr(managed.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1})())
    return home, source


def call(fixture, *args):
    home, source = fixture
    return managed.main(["--home", str(home), "--source", str(source), *args])


def paths(fixture):
    home, _ = fixture
    base = home / ".local/share/rea-video"
    return base, home / ".local/bin/rea-video"


def test_dry_run_no_mutation(fixture):
    call(fixture, "--dry-run")
    assert list(fixture[0].iterdir()) == []


def test_install_layout_and_idempotence(fixture):
    call(fixture)
    base, launcher = paths(fixture)
    manifest = json.loads((base / "manifest.json").read_text())
    assert manifest["owner"] == managed.OWNER
    assert launcher.is_symlink()
    assert (base / "current/skill/SKILL.md").read_text() == "skill"
    assert len(list((base / "versions").iterdir())) == 1
    for agent in ("claude", "codex", "agents"):
        assert (fixture[0] / f".{agent}/skills/rea-video").is_symlink()
    call(fixture)
    assert len(list((base / "versions").iterdir())) == 1


@pytest.mark.parametrize("conflict", ["launcher", "directory", "symlink"])
def test_unowned_conflicts(fixture, conflict):
    home, _ = fixture
    if conflict == "launcher":
        target = home / ".local/bin/rea-video"
    else:
        target = home / ".claude/skills/rea-video"
    target.parent.mkdir(parents=True)
    if conflict == "directory":
        target.mkdir()
    elif conflict == "symlink":
        target.symlink_to("/somewhere/else")
    else:
        target.write_text("mine")
    with pytest.raises(RuntimeError, match="Unowned"):
        call(fixture)
    assert target.exists() or target.is_symlink()


def test_update_rollback_and_uninstall(fixture, monkeypatch):
    call(fixture)
    base, launcher = paths(fixture)
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    call(fixture, "update")
    assert os.readlink(base / "current") == "versions/0.2.0-def-x86_64"
    call(fixture, "rollback")
    assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    user_data = fixture[0] / ".rea-video/preferences.json"
    user_data.parent.mkdir()
    user_data.write_text("saved")
    unrelated = fixture[0] / ".codex/skills/other"
    unrelated.write_text("keep")
    call(fixture, "uninstall")
    assert not launcher.exists()
    assert not (base / "manifest.json").exists()
    assert unrelated.read_text() == "keep"
    assert user_data.read_text() == "saved"


def test_failed_staging_keeps_active(fixture, monkeypatch):
    call(fixture)
    base, launcher = paths(fixture)
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    monkeypatch.setattr(managed, "verify", lambda *args: (_ for _ in ()).throw(RuntimeError("bad build")))
    with pytest.raises(RuntimeError, match="bad build"):
        call(fixture, "update")
    assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    assert launcher.resolve().exists()


def test_manifest_validation(fixture):
    base, _ = paths(fixture)
    base.mkdir(parents=True)
    (base / "manifest.json").write_text('{"owner":"someone else"}')
    with pytest.raises(RuntimeError, match="Invalid ownership"):
        call(fixture)


@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
def test_architecture_layout(fixture, monkeypatch, arch):
    monkeypatch.setattr(managed.platform, "machine", lambda: arch)
    call(fixture)
    base, _ = paths(fixture)
    assert (base / "versions" / f"0.1.0-abc-{arch}").is_dir()


def test_candidate_venv_uses_final_path(fixture, monkeypatch):
    seen = []
    original = managed.run
    def record(command):
        if command[1:3] == ["-m", "venv"]:
            seen.append(Path(command[3]))
        original(command)
    monkeypatch.setattr(managed, "run", record)
    call(fixture)
    base, _ = paths(fixture)
    assert seen == [base / "versions/0.1.0-abc-x86_64/venv"]


def test_version_check_rejects_mismatched_cli(tmp_path, monkeypatch):
    directory = tmp_path / "version"
    (directory / "venv/bin").mkdir(parents=True)
    (directory / "skill").mkdir()
    (directory / "skill/SKILL.md").write_text("skill")
    (directory / "venv/bin/rea-video").write_text("")
    (directory / "venv/bin/python").write_text("")
    monkeypatch.setattr(managed, "run", lambda _: None)
    monkeypatch.setattr(managed.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "rea-video 0.1.0 (other)"})())
    with pytest.raises(RuntimeError, match="version mismatch"):
        managed.verify(directory, "0.1.0-expected")


def assert_no_install_artifacts(fixture):
    home, _ = fixture
    base, launcher = paths(fixture)
    assert not launcher.is_symlink()
    assert not (base / "current").is_symlink()
    assert not (base / "manifest.json").exists()
    assert not any((base / "versions").iterdir()) if (base / "versions").exists() else True
    for agent in ("claude", "codex", "agents"):
        assert not (home / f".{agent}/skills/rea-video").is_symlink()


def assert_old_install_usable(fixture, old_manifest):
    home, _ = fixture
    base, launcher = paths(fixture)
    assert (base / "manifest.json").read_bytes() == old_manifest
    assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    assert launcher.resolve().exists()
    for agent in ("claude", "codex", "agents"):
        assert (home / f".{agent}/skills/rea-video/SKILL.md").read_text() == "skill"


@pytest.mark.parametrize("mode", ["fresh", "update"])
@pytest.mark.parametrize("failure", ["candidate_install", "candidate_verify", "launcher", "skill", "current", "manifest"])
def test_injected_failures_restore_state(fixture, monkeypatch, mode, failure):
    home, _ = fixture
    base, launcher = paths(fixture)
    old_manifest = None
    if mode == "update":
        call(fixture)
        old_manifest = (base / "manifest.json").read_bytes()
        monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    if failure == "candidate_install":
        original = managed.run
        def fail_install(command):
            if "install" in command:
                raise RuntimeError("injected install failure")
            original(command)
        monkeypatch.setattr(managed, "run", fail_install)
    elif failure == "candidate_verify":
        monkeypatch.setattr(managed, "verify", lambda *args: (_ for _ in ()).throw(RuntimeError("injected verify failure")))
    elif failure in ("launcher", "skill"):
        original = Path.symlink_to
        def fail_link(self, target, *args, **kwargs):
            if (failure == "launcher" and self == launcher) or (failure == "skill" and self == home / ".codex/skills/rea-video"):
                raise RuntimeError("injected link failure")
            return original(self, target, *args, **kwargs)
        monkeypatch.setattr(Path, "symlink_to", fail_link)
        if mode == "update":
            # Updates ordinarily reuse existing links. Remove one owned link to exercise repair.
            target = launcher if failure == "launcher" else home / ".codex/skills/rea-video"
            target.unlink()
            old_manifest = (base / "manifest.json").read_bytes()
    elif failure == "current":
        monkeypatch.setattr(managed, "atomic_link", lambda *args: (_ for _ in ()).throw(RuntimeError("injected current failure")))
    else:
        original = managed.save
        def fail_save(path, data):
            original(path, data)
            raise RuntimeError("injected manifest failure after write")
        monkeypatch.setattr(managed, "save", fail_save)
    with pytest.raises(RuntimeError, match="injected"):
        call(fixture, "update" if mode == "update" else "install")
    if mode == "fresh":
        assert_no_install_artifacts(fixture)
    elif failure not in ("launcher", "skill"):
        assert_old_install_usable(fixture, old_manifest)
    else:
        # Pre-existing links removed by the test remain absent; all other state is restored.
        assert (base / "manifest.json").read_bytes() == old_manifest
        assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    candidate = base / "versions" / ("0.2.0-def-x86_64" if mode == "update" else "0.1.0-abc-x86_64")
    if mode == "update":
        assert not candidate.exists()


def test_update_validates_before_switch(fixture, monkeypatch):
    call(fixture)
    base, _ = paths(fixture)
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    def check_candidate(path, version):
        assert path == base / "versions/0.2.0-def-x86_64"
        assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    monkeypatch.setattr(managed, "verify", check_candidate)
    call(fixture, "update")
    assert os.readlink(base / "current") == "versions/0.2.0-def-x86_64"


def test_wrapper_finds_newer_python_when_python3_is_old(tmp_path):
    import subprocess
    import sys
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").write_text("#!/bin/sh\nexit 1\n")
    newer = bin_dir / "python3.12"
    newer.write_text(f"#!/bin/sh\nexec '{sys.executable}' \"$@\"\n")
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    wrapper = Path(__file__).resolve().parents[1] / "scripts/install_skill.sh"
    result = subprocess.run(["bash", str(wrapper), "--help"], capture_output=True, text=True,
                            env={"PATH": f"{bin_dir}:/usr/bin:/bin"}, check=True)
    assert "--dry-run" in result.stdout


def test_rollback_manifest_failure_restores_previous_state(fixture, monkeypatch):
    call(fixture)
    base, _ = paths(fixture)
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    call(fixture, "update")
    before = (base / "manifest.json").read_bytes()
    original = managed.save
    def fail_save(path, data):
        original(path, data)
        raise RuntimeError("injected rollback save failure")
    monkeypatch.setattr(managed, "save", fail_save)
    with pytest.raises(RuntimeError, match="injected"):
        call(fixture, "rollback")
    assert os.readlink(base / "current") == "versions/0.2.0-def-x86_64"
    assert (base / "manifest.json").read_bytes() == before


def test_second_installer_rejected_while_lock_held(fixture):
    base, _ = paths(fixture)
    with managed.installer_lock(base):
        with pytest.raises(RuntimeError, match="Another rea-video installer"):
            call(fixture)


def test_stale_lock_inode_does_not_block(fixture):
    base, _ = paths(fixture)
    base.mkdir(parents=True)
    (base / ".installer.lock").write_text("old lock file")
    call(fixture)
    assert (base / "current").is_symlink()


def test_lock_released_after_completion_and_exception(fixture, monkeypatch):
    base, _ = paths(fixture)
    with managed.installer_lock(base):
        pass
    with managed.installer_lock(base):
        pass
    original = managed.run
    def fail_install(command):
        if "install" in command:
            raise RuntimeError("injected")
        original(command)
    monkeypatch.setattr(managed, "run", fail_install)
    with pytest.raises(RuntimeError, match="injected"):
        call(fixture)
    with managed.installer_lock(base):
        pass


def test_failed_manifest_replace_preserves_old_file(fixture, monkeypatch):
    call(fixture)
    base, _ = paths(fixture)
    prior = (base / "manifest.json").read_bytes()
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    real_replace = os.replace
    def fail_manifest_replace(source, target):
        if Path(target) == base / "manifest.json" and str(source).endswith(".tmp"):
            raise RuntimeError("injected manifest replace failure")
        return real_replace(source, target)
    monkeypatch.setattr(managed.os, "replace", fail_manifest_replace)
    with pytest.raises(RuntimeError, match="injected"):
        call(fixture, "update")
    assert (base / "manifest.json").read_bytes() == prior
    assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
    assert not list(base.glob(".manifest.json.*.tmp"))


def test_current_switch_replaces_without_unlink_and_links_stay_live(fixture, monkeypatch):
    call(fixture)
    home, _ = fixture
    base, launcher = paths(fixture)
    monkeypatch.setattr(managed, "identity", lambda _: "0.2.0-def")
    original_replace = os.replace
    original_unlink = Path.unlink
    seen = []
    def observe_replace(source, target):
        if Path(target) == base / "current":
            assert os.readlink(base / "current") == "versions/0.1.0-abc-x86_64"
            assert launcher.resolve().exists()
            for agent in ("claude", "codex", "agents"):
                assert (home / f".{agent}/skills/rea-video/SKILL.md").read_text() == "skill"
            seen.append((Path(source), Path(target)))
        return original_replace(source, target)
    def forbid_current_unlink(self, *args, **kwargs):
        if self == base / "current":
            raise AssertionError("current was unlinked")
        return original_unlink(self, *args, **kwargs)
    monkeypatch.setattr(managed.os, "replace", observe_replace)
    monkeypatch.setattr(Path, "unlink", forbid_current_unlink)
    call(fixture, "update")
    assert len(seen) == 1
    assert seen[0][0].parent == base
    assert launcher.resolve().exists()
    assert os.readlink(base / "current") == "versions/0.2.0-def-x86_64"
    for agent in ("claude", "codex", "agents"):
        assert (home / f".{agent}/skills/rea-video/SKILL.md").read_text() == "skill"


def test_other_process_holding_lock_rejects_action(fixture):
    import subprocess
    import sys
    base, _ = paths(fixture)
    base.mkdir(parents=True)
    lock = base / ".installer.lock"
    script = (
        "import fcntl, sys; "
        "f=open(sys.argv[1], 'a+b'); "
        "fcntl.flock(f, fcntl.LOCK_EX); "
        "print('locked', flush=True); "
        "sys.stdin.readline()"
    )
    child = subprocess.Popen([sys.executable, "-c", script, str(lock)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(RuntimeError, match="Another rea-video installer"):
            call(fixture)
    finally:
        child.communicate(input="\n", timeout=5)
    call(fixture)


def test_recover_missing_current(fixture):
    call(fixture)
    base, _ = paths(fixture)
    (base / 'current').unlink()
    call(fixture)
    assert (base / 'current').is_symlink()


def test_recover_stale_manifest(fixture, monkeypatch):
    call(fixture)
    base, _ = paths(fixture)
    old = (base / 'manifest.json').read_bytes()
    monkeypatch.setattr(managed, 'identity', lambda _: '0.2.0-def')
    call(fixture, 'update')
    (base / 'manifest.json').write_bytes(old)
    call(fixture)
    assert json.loads((base / 'manifest.json').read_text())['active_version'] == '0.2.0-def-x86_64'


def test_uninstall_refuses_tampered_active_marker(fixture):
    call(fixture)
    base, launcher = paths(fixture)
    (base / 'current/.rea-video-owner.json').write_text('{}')
    with pytest.raises(RuntimeError, match='ownership'):
        call(fixture, 'uninstall')
    assert launcher.is_symlink()


def test_fake_home_lifecycle(fixture, monkeypatch):
    """Exercise all actions in a fake home with subprocess-executed fake CLI."""
    import subprocess
    real_run = subprocess.run
    # fixture mocks subprocess.run for pip; use Popen for independent CLI execution.
    original = managed.run
    def build(command):
        original(command)
        if command[1:3] == ['-m', 'venv']:
            cli = Path(command[3]) / 'bin/rea-video'
            version = managed.identity(fixture[1])
            cli.write_text(f'#!/bin/sh\nprintf "%s\\n" "rea-video {version}"\n')
            cli.chmod(0o755)
    monkeypatch.setattr(managed, 'run', build)
    home, _ = fixture
    data = home / '.rea-video/preferences.json'
    data.parent.mkdir()
    data.write_text('preserve')
    call(fixture, '--dry-run')
    call(fixture)
    base, launcher = paths(fixture)
    links = [launcher, *(home / f'.{agent}/skills/rea-video' for agent in ('claude', 'codex', 'agents'))]
    before = [(os.readlink(p), p.lstat().st_ino) for p in links]
    def check_cli():
        manifest = json.loads((base / 'manifest.json').read_text())
        for cli in (launcher, base / 'current/venv/bin/rea-video'):
            process = subprocess.Popen([str(cli), '--version'], stdout=subprocess.PIPE, text=True)
            output, _ = process.communicate(timeout=5)
            assert process.returncode == 0
            assert manifest['installed_version'] in output
        for link in links[1:]:
            assert link.resolve() == (base / 'current/skill').resolve()
    check_cli()
    monkeypatch.setattr(managed, 'identity', lambda _: '0.2.0-def')
    call(fixture, 'update')
    check_cli()
    assert before == [(os.readlink(p), p.lstat().st_ino) for p in links]
    call(fixture, 'rollback')
    check_cli()
    call(fixture, 'uninstall')
    assert all(not p.is_symlink() for p in links)
    assert not (base / 'manifest.json').exists()
    assert data.read_text() == 'preserve'


def test_snapshot_excludes_artifacts(fixture):
    _, source = fixture
    for name in ('.git/config', '.venv/local.py', 'out/output.json', 'rea_video/__pycache__/cache.py', 'rea_video/build/temp.py'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('excluded')
    selected = [str(p.relative_to(source)) for p in managed.snapshot_files(source)]
    assert selected == ['README.md', 'pyproject.toml', 'rea_video/__init__.py', 'skills/rea-video/SKILL.md']


def test_local_source_snapshot_cli_subprocess(tmp_path):
    """Offline smoke test of real CLI code from the selected local source snapshot."""
    import shutil
    import subprocess
    import sys
    source = Path(__file__).resolve().parents[1]
    snapshot = tmp_path / 'snapshot'
    for file in managed.snapshot_files(source):
        destination = snapshot / file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
    build = managed.identity(source)
    (snapshot / 'rea_video/_build.py').write_text(f'BUILD_ID = {build!r}\n')
    environment = dict(os.environ, PYTHONPATH=str(snapshot))
    command = [sys.executable, '-c',
               'import rea_video; from rea_video.cli import main; print(rea_video.__file__); main()', '--version']
    process = subprocess.Popen(command, cwd=tmp_path, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 0, stderr
    assert str(snapshot / 'rea_video/__init__.py') in stdout
    assert build in stdout
