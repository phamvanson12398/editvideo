"""Prepare per-clip media with ffmpeg: trim, speed, reverse, freeze, LUT, interpolation, upscale."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..aiops.ncnn import interpolate, realesrgan_bin, rife_bin
from ..aiops.ncnn import upscale as ncnn_upscale
from ..plan.schema import Clip, EditPlan
from ..utils.ffmpeg import run, video_codec_args
from ..utils.log import log, pool_map
from .luts import lut_path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"


def ffmpeg_path(p: Path) -> str:
    """Path usable inside an ffmpeg filter argument (Windows drive colons must be escaped)."""
    return p.resolve().as_posix().replace(":", "\\:").replace("'", "\\'")


def _atempo_chain(speed: float) -> str:
    parts = []
    s = speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


def clip_filters(plan: EditPlan, clip: Clip, fps: float, lut: Path | None, extra: list[str], max_height: int | None,
                 interp: bool, upscale: bool) -> tuple[list[str], float, float]:
    """Return (filters, seek_start, read_duration) for one clip."""
    src_dur = clip.src_out - clip.src_in
    filters: list[str] = []
    if clip.freeze is not None:
        start = max(0.0, clip.freeze)
        read = 1.0 / max(plan.source_fps, 1)
        hold = clip.duration + clip.handle_pre + clip.handle_post
        filters.append(f"trim=end_frame=1,loop=loop=-1:size=1,setpts=N/{fps}/TB,trim=duration={hold:.3f}")
    else:
        pre_src = clip.handle_pre * clip.speed
        post_src = clip.handle_post * clip.speed
        if clip.reverse:
            pre_src, post_src = post_src, pre_src
        start = max(0.0, clip.src_in - pre_src)
        read = src_dur + (clip.src_in - start) + post_src
        if clip.reverse:
            filters.append("reverse")
        if abs(clip.speed - 1.0) > 1e-3:
            filters.append(f"setpts=PTS/{clip.speed:.5f}")
            if interp and clip.speed < 1.0:
                filters.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    filters.append(f"fps={fps}")
    if upscale:
        filters.append("scale=iw*2:ih*2:flags=lanczos")
    if max_height:
        filters.append(f"scale=-2:'min({max_height},ih)'")
    if plan.grade.get("auto_color") or plan.grade.get("match_color"):
        # gentle, temporally smoothed levels normalisation (also evens out exposure between shots)
        filters.append("normalize=smoothing=24:independence=0.3:strength=0.35")
    if lut is not None:
        filters.append(f"lut3d=file='{ffmpeg_path(lut)}'")
    if plan.grade.get("sharpen") or upscale:
        filters.append("unsharp=5:5:0.5:5:5:0.0")
    filters.extend(extra)
    filters.append("format=yuv420p")
    return filters, start, read


def prepare_clips(plan: EditPlan, public_dir: Path, *, draft: bool = False, workers: int = 3, upscale: bool = False) -> None:
    """Writes public_dir/clips/<id>.mp4 for every clip (cached by content hash)."""
    upscale = upscale or bool(plan.grade.get("upscale"))
    out_dir = public_dir / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = plan.outputs[0].fps if plan.outputs else 30.0
    lut = lut_path(plan.lut, ASSETS, ASSETS / "cache" / "luts", plan.lut_intensity) if plan.lut else None
    max_h = 540 if draft else None

    def work(clip: Clip) -> None:
        filters, start, read = clip_filters(plan, clip, fps, lut, clip.filters, max_h, clip.interp and not draft, False)
        use_rife = clip.interp and not draft and clip.speed < 1 and rife_bin() is not None
        if use_rife:
            filters = [f for f in filters if not f.startswith(("setpts=", "minterpolate="))]
        need_bg = any(r.mode == "fit-blur" for r in clip.reframe.values())
        key = hashlib.sha1(json.dumps([plan.source, start, read, filters, draft, use_rife, upscale, need_bg]).encode()).hexdigest()[:16]
        target = out_dir / f"{clip.id}.mp4"
        stamp = out_dir / f"{clip.id}.key"
        if target.exists() and stamp.exists() and stamp.read_text() == key:
            return
        args = ["-ss", f"{start:.3f}", "-t", f"{read:.3f}", "-i", plan.source, "-an", "-vf", ",".join(filters)]
        args += video_codec_args("draft" if draft else "intermediate") + ["-g", "15", "-movflags", "+faststart", str(target)]
        if need_bg:
            # pre-blurred, low-res background: far cheaper than a CSS blur on every frame in Chrome
            bg = out_dir / f"{clip.id}_bg.mp4"
            args += ["-an", "-vf", ",".join(filters[:-1] + ["scale=320:-2", "boxblur=12:2", "eq=brightness=-0.12:saturation=1.2", "format=yuv420p"]),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-g", "15", str(bg)]
        run(args)
        if use_rife:
            tmp = out_dir / f"{clip.id}_rife.mp4"
            if interpolate(target, tmp, clip.speed, fps):
                tmp.replace(target)
        if upscale and not draft and realesrgan_bin():
            tmp = out_dir / f"{clip.id}_up.mp4"
            if ncnn_upscale(target, tmp, 2, fps):
                tmp.replace(target)
        stamp.write_text(key)

    log(f"Chuẩn bị {len(plan.clips)} đoạn video{' (bản nháp)' if draft else ''}...")
    pool_map(work, plan.clips, workers)
