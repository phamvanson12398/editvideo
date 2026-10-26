"""Parallel jobs: each job sees only its own log lines; GPU steps take turns."""

from __future__ import annotations

import threading
import time

from director.utils import log as L
from director.utils.locks import gpu_lock, render_share


def test_logs_stay_in_their_job():
    seen: dict[str, list[str]] = {"a": [], "b": []}
    barrier = threading.Barrier(2)

    def job(name: str) -> None:
        L.add_listener(seen[name].append)
        barrier.wait()
        L.log(f"from {name}")
        L.pool_map(lambda i: L.log(f"{name} worker {i}"), range(3), 3)

    ts = [threading.Thread(target=job, args=(n,)) for n in "ab"]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    for name, other in (("a", "b"), ("b", "a")):
        assert len(seen[name]) == 4
        assert not any(other in line for line in seen[name])


def test_gpu_lock_serializes(monkeypatch, tmp_path):
    monkeypatch.setenv("DIRECTOR_HOME", str(tmp_path))
    inside = []
    overlap = []

    def work() -> None:
        with gpu_lock("test"):
            inside.append(1)
            if len(inside) > 1:
                overlap.append(1)
            time.sleep(0.05)
            inside.pop()

    ts = [threading.Thread(target=work) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not overlap
    assert not (tmp_path / "gpu.lock").exists()


def test_render_share_splits_tabs():
    with render_share(8) as a:
        assert a == 8
        with render_share(8) as b:
            assert b == 4
