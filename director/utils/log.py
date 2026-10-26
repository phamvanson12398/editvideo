"""Minimal logging with per-job progress sinks (used by the Studio, where several jobs run in parallel).

Each job binds its own sink and clock through context variables, so log lines from one job never show up
in another job's progress view. Use `pool_map` instead of a bare ThreadPoolExecutor so worker threads
keep the job's context."""

from __future__ import annotations

import contextvars
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable

_sinks: contextvars.ContextVar[tuple[Callable[[str], None], ...]] = contextvars.ContextVar("director_log_sinks", default=())
_t0: contextvars.ContextVar[float] = contextvars.ContextVar("director_log_t0", default=time.time())
_tag: contextvars.ContextVar[str] = contextvars.ContextVar("director_log_tag", default="")


def add_listener(fn: Callable[[str], None]) -> None:
    """Send this context's log lines (the current job, incl. its worker threads) to fn."""
    _sinks.set(_sinks.get() + (fn,))


def remove_listener(fn: Callable[[str], None]) -> None:
    _sinks.set(tuple(f for f in _sinks.get() if f is not fn))


def set_tag(tag: str) -> None:
    """Short prefix for console lines (job id) when several jobs share one terminal."""
    _tag.set(tag)


def reset_clock() -> None:
    """Start the [..s] counter from zero for the current job."""
    _t0.set(time.time())


def log(msg: str) -> None:
    tag = _tag.get()
    line = f"[{time.time() - _t0.get():7.1f}s] {msg}"
    print(f"{tag} {line}" if tag else line, file=sys.stderr, flush=True)
    for fn in _sinks.get():
        try:
            fn(line)
        except Exception:
            pass


def warn(msg: str) -> None:
    log(f"CẢNH BÁO: {msg}")


def pool_map(fn: Callable, items: Iterable, workers: int) -> list:
    """ThreadPoolExecutor.map that keeps the caller's logging context in the worker threads."""
    ctx = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return list(ex.map(lambda it: ctx.copy().run(fn, it), items))
