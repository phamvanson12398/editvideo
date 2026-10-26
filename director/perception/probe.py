from __future__ import annotations

from pathlib import Path

from ..utils.ffmpeg import probe
from .schema import SourceInfo


def _fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        val = stream.get(key) or "0/0"
        try:
            num, den = val.split("/")
            if float(den) > 0 and float(num) > 0:
                return float(num) / float(den)
        except ValueError:
            continue
    return 30.0


def probe_source(path: str | Path) -> SourceInfo:
    info = probe(path)
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if v is None:
        raise ValueError(f"{path} không có luồng video.")
    has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if "rotate" in (v.get("tags") or {}):
        rotation = int(v["tags"]["rotate"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rotation) % 180 == 90:
        w, h = h, w
    duration = float(info["format"].get("duration") or v.get("duration") or 0.0)
    return SourceInfo(
        path=str(Path(path).resolve()),
        duration=duration,
        fps=round(_fps(v), 3),
        width=w,
        height=h,
        has_audio=has_audio,
        rotation=rotation,
    )
