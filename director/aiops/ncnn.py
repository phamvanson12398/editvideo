"""GPU helpers via standalone ncnn-Vulkan binaries (work on GTX 10xx without any CUDA/PyTorch setup):

- realesrgan-ncnn-vulkan  (model realesr-animevideov3: fast, keeps line art crisp)  -> upscale
- rife-ncnn-vulkan        (frame interpolation)                                     -> smooth slow motion

Download the release zips (Windows/Linux/macOS) and either put the executables on PATH, in assets/bin/,
or point REALESRGAN_BIN / RIFE_BIN at them."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..utils.ffmpeg import run, video_codec_args
from ..utils.log import log, warn

ROOT = Path(__file__).resolve().parents[2]


def find_bin(name: str, env: str) -> str | None:
    if os.environ.get(env):
        return os.environ[env]
    for cand in (name, name + ".exe"):
        p = shutil.which(cand)
        if p:
            return p
        local = ROOT / "assets" / "bin" / cand
        if local.exists():
            return str(local)
        hits = list((ROOT / "assets" / "bin").glob(f"**/{cand}")) if (ROOT / "assets" / "bin").exists() else []
        if hits:
            return str(hits[0])
    return None


def realesrgan_bin() -> str | None:
    return find_bin("realesrgan-ncnn-vulkan", "REALESRGAN_BIN")


def rife_bin() -> str | None:
    return find_bin("rife-ncnn-vulkan", "RIFE_BIN")


def _frames(src: Path, d: Path, fps: float | None = None) -> int:
    d.mkdir(parents=True, exist_ok=True)
    vf = [f"fps={fps}"] if fps else []
    args = ["-i", str(src)] + (["-vf", ",".join(vf)] if vf else []) + ["-q:v", "2", str(d / "%08d.png")]
    run(args)
    return len(list(d.glob("*.png")))


def _encode(d: Path, fps: float, dst: Path) -> None:
    run(["-framerate", f"{fps}", "-i", str(d / "%08d.png")] + video_codec_args("intermediate") + ["-g", "15", str(dst)])


def upscale(src: Path, dst: Path, scale: int = 2, fps: float = 30.0) -> bool:
    exe = realesrgan_bin()
    if not exe:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        n = _frames(src, t / "in")
        log(f"Nâng nét {n} khung bằng Real-ESRGAN (GPU)...")
        proc = subprocess.run([exe, "-i", str(t / "in"), "-o", str(t / "out"), "-n", "realesr-animevideov3", "-s", str(scale), "-f", "png"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            warn(f"Real-ESRGAN lỗi: {proc.stderr[-400:]}")
            return False
        _encode(t / "out", fps, dst)
    return True


def interpolate(src: Path, dst: Path, factor: float, fps: float) -> bool:
    """Make `src` (normal speed) `1/factor` times longer with generated in-between frames."""
    exe = rife_bin()
    if not exe or factor >= 1:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        n = _frames(src, t / "in", fps)
        target = max(n + 1, int(round(n / factor)))
        log(f"Slow motion RIFE: {n} -> {target} khung (GPU)...")
        (t / "out").mkdir()
        proc = subprocess.run([exe, "-i", str(t / "in"), "-o", str(t / "out"), "-n", str(target), "-f", "%08d.png"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            warn(f"RIFE lỗi: {proc.stderr[-400:]}")
            return False
        _encode(t / "out", fps, dst)
    return True
