"""Scene cuts (ffmpeg scene score) and keyframe extraction."""

from __future__ import annotations

import re
from pathlib import Path

from ..utils.ffmpeg import run, run_stderr
from .schema import Scene


def detect_scenes(src: str | Path, duration: float, threshold: float = 0.3, min_len: float = 0.4) -> list[Scene]:
    vf = f"scale=320:-2,select='gt(scene,{threshold})',showinfo"
    err = run_stderr(["-i", str(src), "-an", "-vf", vf, "-f", "null", "-"])
    cuts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", err)]
    times = [0.0]
    for c in cuts:
        if c - times[-1] >= min_len and duration - c >= min_len:
            times.append(round(c, 3))
    times.append(round(duration, 3))
    return [Scene(t0=a, t1=b) for a, b in zip(times[:-1], times[1:])]


def extract_frames(src: str | Path, times: list[float], out_dir: str | Path, width: int = 512) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(times):
        p = out_dir / f"kf_{i:04d}_{t:08.2f}.jpg"
        if not p.exists():
            try:
                run(["-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(p)])
            except Exception:
                continue
        if p.exists():
            out.append({"t": round(t, 3), "path": str(p)})
    return out


def keyframe_times(scenes: list[Scene], duration: float, every: float = 6.0, limit: int = 60) -> list[float]:
    ts = {round((s.t0 + s.t1) / 2, 2) for s in scenes}
    t = every / 2
    while t < duration:
        ts.add(round(t, 2))
        t += every
    out = sorted(ts)
    if len(out) > limit:
        step = len(out) / limit
        out = [out[int(i * step)] for i in range(limit)]
    return out
