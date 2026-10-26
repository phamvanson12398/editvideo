"""Minimal logging with optional progress callback (used by the Studio)."""

from __future__ import annotations

import sys
import time
from typing import Callable

_listeners: list[Callable[[str], None]] = []
_t0 = time.time()


def add_listener(fn: Callable[[str], None]) -> None:
    _listeners.append(fn)


def remove_listener(fn: Callable[[str], None]) -> None:
    if fn in _listeners:
        _listeners.remove(fn)


def reset_clock() -> None:
    """Start the [..s] counter from zero (one count per job, also inside the long-running Studio)."""
    global _t0
    _t0 = time.time()


def log(msg: str) -> None:
    line = f"[{time.time() - _t0:7.1f}s] {msg}"
    print(line, file=sys.stderr, flush=True)
    for fn in list(_listeners):
        try:
            fn(line)
        except Exception:
            pass


def warn(msg: str) -> None:
    log(f"CẢNH BÁO: {msg}")
