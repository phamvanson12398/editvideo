"""Generate a small cartoon-like drama sample video for tests (needs ffmpeg + espeak-ng).

usage: python tests/make_sample.py OUT.mp4 [--no-subs]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LINES = [
    (0.8, "Mẹ ơi, con về rồi đây."),
    (4.2, "Ừm... con đi đâu cả ngày vậy hả?"),
    (8.6, "Con đi làm thêm để trả nợ cho nhà mình."),
    (13.5, "Cái gì? Ai cho con đi làm!"),
    (17.8, "Con xin lỗi mẹ. Con xin lỗi mẹ."),
    (22.4, "Thật ra con không phải con ruột của mẹ!"),
    (27.0, "Không thể nào! Trời ơi!"),
]
SCENES = [  # (start, color, hair color of the "character")
    (0.0, "0x87CEEB", "0x3B2A1A"),
    (8.0, "0xF4D03F", "0xD35400"),
    (13.0, "0xE8DAEF", "0x3B2A1A"),
    (22.0, "0x2E4053", "0xD35400"),
    (27.0, "0xC0392B", "0x3B2A1A"),
]
DURATION = 31.0


def srt_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "sample.mp4").resolve()
    subs = "--no-subs" not in sys.argv
    if not shutil.which("espeak-ng"):
        sys.exit("cần espeak-ng để tạo giọng đọc mẫu")
    tmp = Path(tempfile.mkdtemp())
    # voice lines
    inputs, delays = [], []
    for i, (t, text) in enumerate(LINES):
        wav = tmp / f"l{i}.wav"
        subprocess.run(["espeak-ng", "-v", "vi", "-s", "150", "-a", "180", "-w", str(wav), text], check=True)
        inputs.append(wav)
        delays.append(t)
    # an impact sound at 13.4 and 22.3 (drama!)
    filt = []
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for wav in inputs:
        args += ["-i", str(wav)]
    args += ["-f", "lavfi", "-i", f"anoisesrc=d={DURATION}:c=pink:a=0.01"]
    args += ["-f", "lavfi", "-i", f"sine=f=110:d={DURATION},volume=0.05"]
    n = len(inputs)
    for i, d in enumerate(delays):
        filt.append(f"[{i}:a]aresample=44100,adelay={int(d * 1000)}|{int(d * 1000)}[v{i}]")
    mix_in = "".join(f"[v{i}]" for i in range(n)) + f"[{n}:a][{n + 1}:a]"
    filt.append(f"{mix_in}amix=inputs={n + 2}:normalize=0,atrim=0:{DURATION}[a]")
    audio = tmp / "audio.wav"
    subprocess.run(args + ["-filter_complex", ";".join(filt), "-map", "[a]", "-ac", "2", "-ar", "44100", str(audio)], check=True)

    # video: flat-color scenes with a simple drawn "face"
    vf_parts = []
    for k, (t0, bg, hair) in enumerate(SCENES):
        t1 = SCENES[k + 1][0] if k + 1 < len(SCENES) else DURATION
        en = f"between(t,{t0},{t1})"
        cx = 520 + 260 * (k % 2)
        vf_parts += [
            f"drawbox=x=0:y=0:w=iw:h=ih:color={bg}:t=fill:enable='{en}'",
            f"drawbox=x={cx - 150}:y=170:w=300:h=330:color=0xFFE0BD:t=fill:enable='{en}'",
            f"drawbox=x={cx - 165}:y=120:w=330:h=110:color={hair}:t=fill:enable='{en}'",
            f"drawbox=x={cx - 90}:y=290:w=50:h=60:color=0x1B2631:t=fill:enable='{en}'",
            f"drawbox=x={cx + 40}:y=290:w=50:h=60:color=0x1B2631:t=fill:enable='{en}'",
            f"drawbox=x={cx - 50}:y=420:w=100:h=20:color=0xC0392B:t=fill:enable='{en}'",
        ]
    vf = ",".join(vf_parts)
    if subs:
        srt = tmp / "subs.srt"
        lines = []
        for i, (t, text) in enumerate(LINES):
            t1 = LINES[i + 1][0] - 0.3 if i + 1 < len(LINES) else DURATION - 0.5
            lines.append(f"{i + 1}\n{srt_time(t)} --> {srt_time(t1)}\n{text}\n")
        srt.write_text("\n".join(lines), encoding="utf-8")
        vf += f",subtitles={srt.as_posix()}:force_style='FontName=DejaVu Sans,FontSize=22,Outline=2'"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s=1280x720:r=24:d={DURATION}",
        "-i", str(audio), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(out)


if __name__ == "__main__":
    main()
