"""Export the cut list so the edit can be finished in DaVinci Resolve / Premiere / Final Cut.

- CMX3600 EDL: universally supported, cuts + speed (M2 lines).
- OpenTimelineIO (.otio): if the `opentimelineio` package is installed; otherwise a minimal JSON in the same schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..plan.schema import EditPlan


def _tc(sec: float, fps: float) -> str:
    fr = int(round(sec * fps))
    f = int(round(fps))
    h, rem = divmod(fr, 3600 * f)
    m, rem = divmod(rem, 60 * f)
    s, fr = divmod(rem, f)
    return f"{h:02d}:{m:02d}:{s:02d}:{fr:02d}"


def export_edl(plan: EditPlan, path: Path) -> Path:
    fps = plan.outputs[0].fps if plan.outputs else plan.source_fps
    reel = "AX"
    src_name = Path(plan.source).name
    lines = [f"TITLE: {Path(path).stem}", "FCM: NON-DROP FRAME", ""]
    for i, c in enumerate(plan.clips, start=1):
        if c.freeze is not None:
            s_in = s_out = c.freeze
            s_out = c.freeze + 1 / fps
        else:
            s_in, s_out = c.src_in, c.src_out
        rec_in, rec_out = c.start, c.start + c.duration
        lines.append(f"{i:03d}  {reel:<8} V     C        {_tc(s_in, fps)} {_tc(s_out, fps)} {_tc(rec_in, fps)} {_tc(rec_out, fps)}")
        lines.append(f"* FROM CLIP NAME: {src_name}")
        if abs(c.speed - 1) > 1e-3 or c.reverse or c.freeze is not None:
            speed = 0.0 if c.freeze is not None else c.speed * fps * (-1 if c.reverse else 1)
            lines.append(f"M2   {reel:<8}       {speed:05.1f}                {_tc(s_in, fps)}")
        lines.append(f"* DIRECTOR ROLE: {c.role}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_otio(plan: EditPlan, path: Path) -> Path:
    fps = plan.outputs[0].fps if plan.outputs else plan.source_fps
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import opentimelineio as otio  # type: ignore

        tl = otio.schema.Timeline(name=path.stem)
        track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
        tl.tracks.append(track)
        ref = otio.schema.ExternalReference(target_url=Path(plan.source).resolve().as_uri())
        for c in plan.clips:
            start = c.freeze if c.freeze is not None else c.src_in
            dur = c.duration if c.freeze is not None else c.src_out - c.src_in
            clip = otio.schema.Clip(
                name=f"{c.id} ({c.role})",
                media_reference=ref,
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(start * fps, fps), otio.opentime.RationalTime(max(1, dur * fps), fps)),
            )
            if c.freeze is not None:
                clip.effects.append(otio.schema.FreezeFrame())
            elif abs(c.speed - 1) > 1e-3 or c.reverse:
                clip.effects.append(otio.schema.LinearTimeWarp(time_scalar=c.speed * (-1 if c.reverse else 1)))
            clip.metadata["director"] = {"role": c.role}
            track.append(clip)
        markers = otio.schema.Track(name="Effects", kind=otio.schema.TrackKind.Video)
        for e in plan.effects:
            tl.tracks[0].markers.append(otio.schema.Marker(
                name=e.id, marked_range=otio.opentime.TimeRange(otio.opentime.RationalTime(e.start * fps, fps),
                                                                otio.opentime.RationalTime(max(1, (e.end - e.start) * fps), fps)),
                metadata={"category": e.category, "params": e.params}))
        del markers
        otio.adapters.write_to_file(tl, str(path))
    except ImportError:
        data = {
            "OTIO_SCHEMA": "Timeline.1", "name": path.stem,
            "tracks": {"OTIO_SCHEMA": "Stack.1", "children": [{
                "OTIO_SCHEMA": "Track.1", "name": "V1", "kind": "Video",
                "children": [{
                    "OTIO_SCHEMA": "Clip.1", "name": c.id,
                    "source_range": {"OTIO_SCHEMA": "TimeRange.1",
                                     "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": (c.freeze or c.src_in) * fps},
                                     "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": c.duration * fps}},
                    "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": Path(plan.source).resolve().as_uri()},
                } for c in plan.clips],
            }]},
        }
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path
