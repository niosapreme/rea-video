"""Output collision checks and atomic text replacement."""
from pathlib import Path
import os
import tempfile


def preflight(paths, *, force=False):
    existing = [Path(p) for p in paths if Path(p).exists() or Path(p).is_symlink()]
    if existing and not force:
        raise FileExistsError('output already exists (pass --force to replace): ' + ', '.join(map(str, existing[:8])))
    for path in existing:
        if path.is_dir():
            raise IsADirectoryError(str(path))


def preflight_tree(path, *, force=False, marker=None):
    path = Path(path).expanduser()
    resolved = path.resolve()
    protected = {Path.home().resolve(), Path.cwd().resolve(), Path(resolved.anchor)}
    if resolved in protected or (Path.cwd().resolve() in resolved.parents and resolved == Path.cwd().resolve()):
        raise ValueError(f'unsafe output directory: {path}')
    if path.is_symlink():
        raise ValueError(f'output directory is a symlink: {path}')
    if path.exists():
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        if any(path.iterdir()):
            if not force:
                raise FileExistsError(f'output directory is not empty (pass --force to replace): {path}')
            if marker and not (path / marker).is_file():
                raise ValueError(f'output directory is not a previous {marker} output: {path}')


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp', delete=False) as stream:
            name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)

from contextlib import contextmanager


@contextmanager
def staged_media(destination):
    """Render beside destination; publish only a successful nonempty artifact."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{destination.stem}.', suffix=destination.suffix, dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise OSError(f'media output is empty: {temporary}')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
