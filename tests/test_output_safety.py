import pytest
from pathlib import Path
from rea_video.output_safety import atomic_text, preflight, preflight_tree


def test_existing_output_is_protected(tmp_path):
    out = tmp_path / 'out'
    out.mkdir()
    previous = out / 'report.md'
    previous.write_text('valid')
    with pytest.raises(FileExistsError):
        preflight_tree(out)
    assert previous.read_text() == 'valid'
    preflight_tree(out, force=True)


def test_output_collision(tmp_path):
    path = tmp_path / 'result.json'
    path.write_text('valid')
    with pytest.raises(FileExistsError):
        preflight([path])
    assert path.read_text() == 'valid'


def test_interrupted_write_preserves_report(tmp_path, monkeypatch):
    import rea_video.output_safety as safety
    path = tmp_path / 'report.md'
    path.write_text('valid')
    def fail(*args):
        raise OSError('interrupted')
    monkeypatch.setattr(safety.os, 'replace', fail)
    with pytest.raises(OSError):
        atomic_text(path, 'new')
    assert path.read_text() == 'valid'
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_success(tmp_path):
    path = tmp_path / 'report.md'
    atomic_text(path, 'new')
    assert path.read_text() == 'new'


def test_force_requires_owned_directory(tmp_path):
    out = tmp_path / 'unrelated'
    out.mkdir()
    (out / 'notes.txt').write_text('keep')
    with pytest.raises(ValueError):
        preflight_tree(out, force=True, marker='breakdown.json')
    assert (out / 'notes.txt').read_text() == 'keep'
    (out / 'breakdown.json').write_text('{}')
    preflight_tree(out, force=True, marker='breakdown.json')


def test_reject_dangerous_destinations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for path in (tmp_path, tmp_path.home(), Path('/')):
        with pytest.raises(ValueError):
            preflight_tree(path, force=True)
    child = tmp_path / 'child'
    child.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(child)
    with pytest.raises(ValueError):
        preflight_tree(link, force=True)


def test_safe_regeneration(tmp_path):
    path = tmp_path / 'report.md'
    atomic_text(path, 'old')
    atomic_text(path, 'new')
    assert path.read_text() == 'new'


def test_failed_media_replacement_preserves_destination(tmp_path):
    from rea_video.output_safety import staged_media
    path = tmp_path / 'movie.mp4'
    path.write_bytes(b'valid movie')
    with pytest.raises(RuntimeError):
        with staged_media(path) as temporary:
            temporary.write_bytes(b'partial movie')
            raise RuntimeError('encoder failed')
    assert path.read_bytes() == b'valid movie'
    assert list(tmp_path.iterdir()) == [path]


def test_successful_media_replacement(tmp_path):
    from rea_video.output_safety import staged_media
    path = tmp_path / 'movie.mp4'
    path.write_bytes(b'valid movie')
    with staged_media(path) as temporary:
        temporary.write_bytes(b'new movie')
    assert path.read_bytes() == b'new movie'
    assert list(tmp_path.iterdir()) == [path]


def test_empty_media_replacement_preserves_destination(tmp_path):
    from rea_video.output_safety import staged_media
    path = tmp_path / 'movie.mp4'
    path.write_bytes(b'valid movie')
    with pytest.raises(OSError):
        with staged_media(path):
            pass
    assert path.read_bytes() == b'valid movie'
    assert list(tmp_path.iterdir()) == [path]


def test_cut_clip_failed_ffmpeg_keeps_valid_file(tmp_path, monkeypatch):
    import subprocess
    from rea_video.media import cut_clip
    path = tmp_path / 'clip.mp4'
    path.write_bytes(b'valid clip')
    def failed(command, **kwargs):
        Path(command[-1]).write_bytes(b'partial clip')
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(subprocess, 'run', failed)
    with pytest.raises(subprocess.CalledProcessError):
        cut_clip('input.mp4', 0, 1, path)
    assert path.read_bytes() == b'valid clip'
    assert list(tmp_path.iterdir()) == [path]


def test_cut_clip_success_replaces_valid_file(tmp_path, monkeypatch):
    from rea_video.media import cut_clip
    import subprocess
    path = tmp_path / 'clip.mp4'
    path.write_bytes(b'valid clip')
    def succeeded(command, **kwargs):
        Path(command[-1]).write_bytes(b'new clip')
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(subprocess, 'run', succeeded)
    cut_clip('input.mp4', 0, 1, path)
    assert path.read_bytes() == b'new clip'
    assert list(tmp_path.iterdir()) == [path]
