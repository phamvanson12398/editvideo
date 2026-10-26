"""Command line: `director edit video.mp4 -c "drama dọc 9:16, hook bằng cú twist"`."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def cmd_edit(a: argparse.Namespace) -> int:
    from .pipeline import JobOptions, run_job

    opt = JobOptions(
        command=a.command or "", frames=a.frame or None, preset=a.preset, out_dir=Path(a.out), draft=a.draft,
        use_llm=False if a.no_llm else (True if a.llm else None), critic_rounds=a.critic, variants=a.variants,
        genre=a.genre, whisper_model=a.whisper_model, language=a.lang, separate=not a.no_separate,
        force_analyze=a.reanalyze, export_timeline=not a.no_export, remember=not a.no_memory, upscale=a.upscale,
    )
    res = run_job(a.video, opt)
    print("\n" + res.summary)
    print("\nVideo thành phẩm:")
    for p in res.outputs:
        print(f"  {p}")
    print(f"\nKế hoạch dựng (để sửa bằng `director revise`): {', '.join(str(p) for p in res.plans)}")
    return 0


def cmd_revise(a: argparse.Namespace) -> int:
    from .pipeline import JobOptions, revise_job

    opt = JobOptions(out_dir=Path(a.out), draft=a.draft, use_llm=False if a.no_llm else None)
    res = revise_job(a.plan, a.instruction, opt)
    print("\n" + res.summary)
    for p in res.outputs:
        print(f"  {p}")
    return 0


def cmd_analyze(a: argparse.Namespace) -> int:
    from .pipeline import job_dir_for
    from .perception.analyze import analyze

    idx = analyze(a.video, job_dir_for(Path(a.video), Path(a.out)), genre_hint=a.genre, separate=not a.no_separate, force=a.reanalyze)
    print(f"Thể loại: {idx.genre} ({idx.genre_confidence:.2f}) | {idx.source.duration:.1f}s | {len(idx.sentences)} câu | {len(idx.scenes)} cảnh")
    print(f"Phụ đề có sẵn: {'có' if idx.hardsub.present else 'không'} | nhân vật: {', '.join(c.id for c in idx.characters) or '-'}")
    for s in idx.sentences[: a.limit]:
        print(f"  [{s.t0:7.2f}-{s.t1:7.2f}] {s.character or '-':>3} {s.emotion or '-':>8}  {s.text}")
    print("Highlight:", ", ".join(f"{h.t0:.0f}-{h.t1:.0f}s" for h in idx.highlights[:5]))
    return 0


def cmd_styles(a: argparse.Namespace) -> int:
    from .style.presets import list_presets

    for k, v in list_presets().items():
        print(f"  {k:<20} {v}")
    return 0


def cmd_effects(a: argparse.Namespace) -> int:
    from .effects.catalog import CAPTION_PRESETS, COMBOS, EFFECTS

    by: dict[str, list] = {}
    for e in EFFECTS.values():
        by.setdefault(e.category, []).append(e)
    for cat, items in by.items():
        print(f"[{cat}] {len(items)}")
        for e in items:
            print(f"   {e.id:<18} {e.name}")
    print(f"[combo] {len(COMBOS)}")
    for k, c in COMBOS.items():
        print(f"   {k:<22} {c['name']}")
    print(f"[phụ đề] {', '.join(CAPTION_PRESETS)}")
    return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    from .agent.llm import available
    from .render.remotion import REMOTION_DIR, browser_executable
    from .utils.ffmpeg import ffmpeg_major, nvenc_ok

    def row(ok: bool | None, name: str, detail: str = "") -> None:
        mark = {True: "OK ", False: "THIẾU", None: "--  "}[ok]
        print(f"  [{mark}] {name}{': ' + detail if detail else ''}")

    print("Kiểm tra môi trường Director:")
    row(bool(shutil.which("ffmpeg")), "ffmpeg", f"phiên bản {ffmpeg_major()}" if shutil.which("ffmpeg") else "cài ffmpeg và thêm vào PATH")
    row(nvenc_ok() if shutil.which("ffmpeg") else False, "NVENC (encode bằng GPU NVIDIA)", "không bắt buộc")
    node = shutil.which("node")
    row(bool(node), "Node.js", subprocess.run([node, "-v"], capture_output=True, text=True).stdout.strip() if node else "cài Node.js 18+")
    row((REMOTION_DIR / "node_modules" / "remotion").exists(), "Remotion", "chạy `npm install` trong remotion/" if not (REMOTION_DIR / "node_modules").exists() else "")
    row(True if browser_executable() else None, "Trình duyệt cho Remotion", browser_executable() or "Remotion tự tải khi render lần đầu")
    try:
        import faster_whisper  # noqa: F401

        row(True, "faster-whisper (chép lời)")
    except ImportError:
        row(False, "faster-whisper (chép lời)", "pip install 'director-video[asr]'")
    for mod, name, extra in (("rapidocr_onnxruntime", "OCR phụ đề có sẵn", "ocr"), ("demucs", "Demucs tách thoại/nhạc", "separation"),
                             ("pyannote.audio", "pyannote nhận diện người nói", "diarize"), ("fastapi", "Studio (giao diện web)", "studio")):
        try:
            __import__(mod)
            row(True, name)
        except ImportError:
            row(None, name, f"tuỳ chọn: pip install 'director-video[{extra}]'")
    try:
        import torch  # type: ignore

        archs = torch.cuda.get_arch_list() if torch.cuda.is_available() else []
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "không thấy GPU CUDA"
        ok = torch.cuda.is_available() and (not archs or any(x.startswith("sm_6") for x in archs) or "Pascal" not in gpu)
        row(ok, "PyTorch CUDA", f"{gpu}; arch: {', '.join(archs) or '-'}")
        if torch.cuda.is_available() and "GTX 10" in gpu and archs and not any(x.startswith("sm_61") or x == "sm_60" for x in archs):
            print("     ! GTX 10xx cần bản PyTorch có sm_61 (vd. cu126). Cài: pip install torch --index-url https://download.pytorch.org/whl/cu126")
    except ImportError:
        row(None, "PyTorch", "chỉ cần cho Demucs/pyannote")
    for b in ("realesrgan-ncnn-vulkan", "rife-ncnn-vulkan"):
        row(True if shutil.which(b) or os.environ.get(b.split("-")[0].upper() + "_BIN") else None, b, "tuỳ chọn (nâng nét / slow motion bằng GPU)")
    row(available(), "Claude API", "ANTHROPIC_API_KEY hoặc `ant auth login` (không có vẫn chạy offline)")
    return 0


def cmd_studio(a: argparse.Namespace) -> int:
    from .studio.server import serve

    serve(host=a.host, port=a.port, out_dir=Path(a.out))
    return 0


def cmd_sfx(a: argparse.Namespace) -> int:
    from .render.sfx_synth import SYNTHS, sfx_file

    out = Path(a.dir)
    for k in SYNTHS:
        p = sfx_file(k, Path("/nonexistent"), out)
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="director", description="Director: tool edit video bằng AI (Remotion + ffmpeg + Claude)")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("edit", help="Dựng video từ 1 file video gốc")
    e.add_argument("video")
    e.add_argument("-c", "--command", "--style", dest="command", help='Lệnh/mô tả phong cách, vd: "drama dọc 9:16, hook bằng cú twist, 60 giây"')
    e.add_argument("-f", "--frame", action="append", help='Khung hình (lặp lại được): 9:16, tiktok, youtube, 4:5, 1080x1350, "điện ảnh"...')
    e.add_argument("--preset", help="Preset phong cách (xem `director styles`)")
    e.add_argument("-o", "--out", default="outputs", help="Thư mục kết quả")
    e.add_argument("--draft", action="store_true", help="Chỉ dựng bản nháp nhanh (độ phân giải thấp)")
    e.add_argument("--llm", action="store_true", help="Bắt buộc dùng Claude")
    e.add_argument("--no-llm", action="store_true", help="Không dùng Claude (planner offline)")
    e.add_argument("--critic", type=int, default=2, help="Số vòng tự xem lại & sửa (cần Claude)")
    e.add_argument("--variants", type=int, default=1, choices=[1, 2, 3], help="Số phương án (chuẩn / mạnh tay / an toàn)")
    e.add_argument("--genre", choices=["anime", "cartoon3d", "live", "gameplay"], help="Ghi đè thể loại tự nhận")
    e.add_argument("--whisper-model", help="large-v3-turbo | medium | small ...")
    e.add_argument("--lang", help="Ngôn ngữ lời thoại (vi, en, ja, ko, zh...), mặc định tự nhận")
    e.add_argument("--no-separate", action="store_true", help="Không tách thoại/nhạc bằng Demucs")
    e.add_argument("--reanalyze", action="store_true", help="Phân tích lại video (bỏ cache)")
    e.add_argument("--no-export", action="store_true", help="Không xuất EDL/OTIO")
    e.add_argument("--no-memory", action="store_true", help="Không dùng/ghi bộ nhớ bộ phim & sở thích")
    e.add_argument("--upscale", action="store_true", help="Nâng nét x2 bằng Real-ESRGAN anime (cần realesrgan-ncnn-vulkan, GPU)")
    e.set_defaults(fn=cmd_edit)

    r = sub.add_parser("revise", help="Sửa bản dựng bằng lời: director revise outputs/jobs/.../x.plan.json \"intro nhanh hơn\"")
    r.add_argument("plan")
    r.add_argument("instruction")
    r.add_argument("-o", "--out", default="outputs")
    r.add_argument("--draft", action="store_true")
    r.add_argument("--no-llm", action="store_true")
    r.set_defaults(fn=cmd_revise)

    an = sub.add_parser("analyze", help="Chỉ phân tích video (xem tool hiểu gì)")
    an.add_argument("video")
    an.add_argument("-o", "--out", default="outputs")
    an.add_argument("--genre")
    an.add_argument("--limit", type=int, default=40)
    an.add_argument("--no-separate", action="store_true")
    an.add_argument("--reanalyze", action="store_true")
    an.set_defaults(fn=cmd_analyze)

    sub.add_parser("styles", help="Danh sách preset phong cách").set_defaults(fn=cmd_styles)
    sub.add_parser("effects", help="Danh sách hiệu ứng").set_defaults(fn=cmd_effects)
    sub.add_parser("doctor", help="Kiểm tra môi trường").set_defaults(fn=cmd_doctor)

    s = sub.add_parser("studio", help="Mở giao diện web")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=7860)
    s.add_argument("-o", "--out", default="outputs")
    s.set_defaults(fn=cmd_studio)

    x = sub.add_parser("sfx", help="Xuất toàn bộ tiếng động tổng hợp ra thư mục để nghe thử")
    x.add_argument("dir")
    x.set_defaults(fn=cmd_sfx)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        return 130
    except Exception as ex:  # friendly error at the top level
        if os.environ.get("DIRECTOR_DEBUG"):
            raise
        print(f"\nLỖI: {ex}", file=sys.stderr)
        print("(đặt DIRECTOR_DEBUG=1 để xem chi tiết)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
