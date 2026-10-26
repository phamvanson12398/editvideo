"""Coordination between jobs running in parallel (Studio tabs, several .bat windows).

- gpu_lock(): Whisper / Demucs / pyannote use the GPU one at a time (8 GB cards run out of memory otherwise).
  Works across threads AND processes (lock file in the Director home folder).
- render_share(): divides CPU cores between Remotion renders running at the same time in this process.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path

from .log import log

_thread_gpu = threading.Lock()
_render_lock = threading.Lock()
_active_renders = 0
STALE_SEC = 3 * 3600


def _home() -> Path:
    p = Path(os.environ.get("DIRECTOR_HOME") or Path.home() / ".director")
    p.mkdir(parents=True, exist_ok=True)
    return p


@contextlib.contextmanager
def gpu_lock(what: str = "GPU"):
    path = _home() / "gpu.lock"
    waited = False
    with _thread_gpu:
        while True:
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time()}".encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - path.stat().st_mtime > STALE_SEC:
                        path.unlink(missing_ok=True)  # left behind by a crashed run
                        continue
                except FileNotFoundError:
                    continue
                if not waited:
                    log(f"Đang chờ việc khác dùng xong GPU để chạy {what}...")
                    waited = True
                time.sleep(2)
        try:
            yield
        finally:
            path.unlink(missing_ok=True)


@contextlib.contextmanager
def render_share(total: int):
    """Yields how many Chrome tabs this render may use while others run alongside it."""
    global _active_renders
    with _render_lock:
        _active_renders += 1
        n = _active_renders
    try:
        yield max(1, total // n)
    finally:
        with _render_lock:
            _active_renders -= 1
