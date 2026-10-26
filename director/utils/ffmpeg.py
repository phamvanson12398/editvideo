"""Thin wrappers around ffmpeg / ffprobe."""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
from pathlib import Path

from .log import log


class FFmpegError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegError("Không tìm thấy ffmpeg. Hãy cài ffmpeg và thêm vào PATH.")
    return path


def ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FFmpegError("Không tìm thấy ffprobe. Hãy cài ffmpeg (kèm ffprobe) và thêm vào PATH.")
    return path


def run(args: list[str], *, quiet: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_bin(), "-hide_banner", "-y"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-3000:]
        raise FFmpegError(f"ffmpeg lỗi (mã {proc.returncode}):\n{' '.join(cmd)}\n{tail}")
    return proc


def run_stderr(args: list[str]) -> str:
    """Run ffmpeg with info-level logging and return stderr (for filters like silencedetect)."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostats", "-y"] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg lỗi:\n{' '.join(cmd)}\n{proc.stderr[-3000:]}")
    return proc.stderr


def probe(path: str | Path) -> dict:
    cmd = [
        ffprobe_bin(), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe không đọc được {path}: {proc.stderr}")
    return json.loads(proc.stdout)


@functools.lru_cache(maxsize=1)
def encoders() -> set[str]:
    try:
        out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6:
            names.add(parts[1])
    return names


@functools.lru_cache(maxsize=1)
def nvenc_ok() -> bool:
    """True when h264_nvenc exists AND actually works (driver present)."""
    if "h264_nvenc" not in encoders():
        return False
    try:
        run(["-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"])
        log("Phát hiện GPU NVIDIA: dùng NVENC để encode.")
        return True
    except FFmpegError:
        return False


def video_codec_args(quality: str = "final") -> list[str]:
    """Encoder args. quality: 'final' | 'draft' | 'intermediate'."""
    if nvenc_ok():
        cq = {"final": "19", "draft": "30", "intermediate": "18"}[quality]
        preset = {"final": "p5", "draft": "p1", "intermediate": "p4"}[quality]
        return ["-c:v", "h264_nvenc", "-preset", preset, "-rc", "vbr", "-cq", cq, "-b:v", "0", "-pix_fmt", "yuv420p"]
    crf = {"final": "18", "draft": "30", "intermediate": "17"}[quality]
    preset = {"final": "medium", "draft": "ultrafast", "intermediate": "veryfast"}[quality]
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p"]
