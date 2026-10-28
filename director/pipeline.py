"""End-to-end job: video + command -> finished videos."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agent.llm import provider_label
from .agent.planner_rules import plan_rules
from .perception.analyze import analyze
from .perception.schema import VideoIndex
from .plan.compiler import compile_plan, summarize
from .plan.frames import parse_frames
from .plan.schema import EditPlan, PlanDraft
from .render.audio_mix import build_soundtrack
from .render.prep import prepare_clips
from .render.remotion import render_output
from .style.dna import StyleDNA
from .style.parse import parse_style
from .utils.ffmpeg import run
from .utils.log import log, reset_clock, warn


@dataclass
class JobOptions:
    command: str = ""
    frames: list[str] | None = None
    preset: str | None = None
    out_dir: Path = Path("outputs")
    draft: bool = False
    use_llm: bool | None = None  # None = auto (when an API key is configured)
    critic_rounds: int | None = None  # None = auto: 1 round for outputs up to 3 minutes, 0 for longer
    fast: bool = False  # 720p output: roughly twice as fast to render
    sfx_volume: float | None = None  # % (None = cau_hinh.json / style default 50)
    music_volume: float | None = None
    bgm_volume: float | None = None
    variants: int = 1
    genre: str | None = None
    whisper_model: str | None = None
    language: str | None = None
    separate: bool = True
    force_analyze: bool = False
    export_timeline: bool = True
    remember: bool = True
    upscale: bool = False
    reference: Path | None = None  # "edit like this video"
    text_language: str | None = None  # added on-screen text: vi | ko | en | ja | zh ... (None = spoken language)


@dataclass
class JobResult:
    job_dir: Path
    outputs: list[Path] = field(default_factory=list)
    plans: list[Path] = field(default_factory=list)
    summary: str = ""


def job_dir_for(video: Path, root: Path) -> Path:
    h = hashlib.sha1(str(video.resolve()).encode()).hexdigest()[:8]
    return root / "jobs" / f"{video.stem}_{h}"


def llm_enabled(opt: JobOptions) -> bool:
    if opt.use_llm is False:
        return False
    from .agent.llm import available

    ok = available()
    if opt.use_llm and not ok:
        warn("Chưa có Antigravity CLI (chạy 6_CAI_ANTIGRAVITY.bat để cài và đăng nhập): dùng bộ lập kế hoạch offline.")
    return ok


def _ref_dir(opt: JobOptions) -> Path:
    ref = Path(opt.reference)  # type: ignore[arg-type]
    return Path(opt.out_dir) / "jobs" / f"ref_{ref.stem}"


CONFIG_FILE = Path(__file__).resolve().parents[1] / "cau_hinh.json"


def load_config() -> dict:
    """User defaults from cau_hinh.json (repo root); missing/broken file = built-in defaults."""
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as e:
        warn(f"Không đọc được {CONFIG_FILE.name} ({e}), dùng mặc định.")
        return {}


def apply_config(opt: JobOptions) -> None:
    cfg = load_config()
    if opt.sfx_volume is None and "am_luong_tieng_dong" in cfg:
        opt.sfx_volume = float(cfg["am_luong_tieng_dong"])
    if opt.music_volume is None and "am_luong_nhac_them" in cfg:
        opt.music_volume = float(cfg["am_luong_nhac_them"])
    if opt.bgm_volume is None and "am_luong_nhac_goc" in cfg:
        opt.bgm_volume = float(cfg["am_luong_nhac_goc"])
    if not opt.text_language and cfg.get("ngon_ngu_chu") not in (None, "", "auto"):
        opt.text_language = str(cfg["ngon_ngu_chu"])
    if not opt.fast and cfg.get("dung_nhanh_720p"):
        opt.fast = True


def resolve_style(idx: VideoIndex, opt: JobOptions, use_llm: bool) -> StyleDNA:
    from .style.presets import get_preset

    base = get_preset(opt.preset) if opt.preset else None
    if opt.reference:
        from .style.reference import style_from_reference

        base = style_from_reference(opt.reference, _ref_dir(opt), base, use_llm)
    style = parse_style(opt.command, idx.genre, base)
    if use_llm and opt.command.strip() and os.environ.get("DIRECTOR_AI_FULL"):
        try:
            from .agent.director import refine_style

            style = refine_style(opt.command, style, idx)
        except Exception as e:  # never block a job on the LLM
            warn(f"LLM đọc lệnh phong cách lỗi, dùng kết quả offline: {e}")
    if opt.frames:
        style.frames = opt.frames
    if opt.text_language and opt.text_language != "auto":
        style.text_language = opt.text_language
    # volumes: config / options give the baseline, an explicit percentage in the command wins
    said_sfx = "sfx_volume" in str(opt.command) or any(k in opt.command.lower() for k in ("tiếng động", "sfx", "hiệu ứng âm thanh"))
    if opt.sfx_volume is not None and not said_sfx:
        style.audio.sfx_volume = opt.sfx_volume
    if opt.music_volume is not None and "nhạc" not in opt.command.lower():
        style.audio.music_volume = opt.music_volume
    if opt.bgm_volume is not None:
        style.audio.bgm_volume = opt.bgm_volume
    if opt.remember:
        from .memory.store import apply_series_memory

        apply_series_memory(idx, style)
    return style


def make_drafts(idx: VideoIndex, style: StyleDNA, opt: JobOptions, use_llm: bool) -> list[list[PlanDraft]]:
    """Returns variants -> parts -> draft."""
    intensities = [None, "high", "low"][: max(1, opt.variants)]
    labels = ["chuẩn", "mạnh tay", "an toàn"]
    out: list[list[PlanDraft]] = []
    for i, inten in enumerate(intensities):
        drafts = None
        if use_llm:
            try:
                from .agent.director import plan_with_llm

                drafts = plan_with_llm(idx, style, opt.command, variant=labels[i] if opt.variants > 1 else None)
            except Exception as e:
                warn(f"LLM lập kế hoạch lỗi, dùng planner offline: {e}")
        if not drafts:
            drafts = plan_rules(idx, style, intensity=inten)
        out.append(drafts)
    return out


def render_plan(plan: EditPlan, job: Path, name: str, out_dir: Path, *, draft: bool, has_audio: bool,
                upscale: bool = False) -> list[Path]:
    public = job / "render"
    public.mkdir(parents=True, exist_ok=True)
    prepare_clips(plan, public, draft=draft, upscale=upscale)
    mix = job / f"{name}_mix.wav"
    build_soundtrack(plan, job, mix, source_has_audio=has_audio)
    results = []
    for out in plan.outputs:
        silent = job / f"{name}_{out.id}_video.mp4"
        render_output(plan, out.id, public, silent, draft=draft)
        final = out_dir / f"{name}_{out.id}{'_nhap' if draft else ''}.mp4"
        final.parent.mkdir(parents=True, exist_ok=True)
        run(["-i", str(silent), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", str(final)])
        results.append(final)
        log(f"Xong: {final}")
    return results


def run_job(video: str | Path, opt: JobOptions) -> JobResult:
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(video)
    out_dir = Path(opt.out_dir)
    job = job_dir_for(video, out_dir)
    job.mkdir(parents=True, exist_ok=True)
    res = JobResult(job_dir=job)

    apply_config(opt)
    reset_clock()
    t_start = time.time()
    idx = analyze(video, job, genre_hint=opt.genre, whisper_model=opt.whisper_model, language=opt.language,
                  separate=opt.separate, force=opt.force_analyze)
    use_llm = llm_enabled(opt)
    if use_llm and ((job / "story.json").exists() or os.environ.get("DIRECTOR_AI_FULL")):
        # cached story (instant) — otherwise the planning call understands the story itself
        try:
            from .agent.director import understand_story

            understand_story(idx, job)
        except Exception as e:
            warn(f"LLM phân tích câu chuyện lỗi, dùng phân tích offline: {e}")
    style = resolve_style(idx, opt, use_llm)
    (job / "style.json").write_text(style.model_dump_json(indent=2), encoding="utf-8")
    outputs = parse_frames(style.frames, idx.source.width, idx.source.height)
    if opt.fast:
        for o in outputs:
            k = min(1.0, 1280 / max(o.width, o.height))
            o.width, o.height = int(o.width * k) // 2 * 2, int(o.height * k) // 2 * 2
    log(f"[{time.time() - t_start:.0f}s] Phân tích xong.")
    log(f"Phong cách: {style.name} | khung: {', '.join(o.id for o in outputs)} | AI: {provider_label() if use_llm else 'tắt (offline)'}")

    variants = make_drafts(idx, style, opt, use_llm)
    if use_llm and idx.story_summary and not (job / "story.json").exists():
        (job / "story.json").write_text(json.dumps({
            "summary": idx.story_summary,
            "characters": {c.id: {"name": c.name} for c in idx.characters if c.name},
            "beats": [b.model_dump() for b in idx.story],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    summaries = []
    for vi, parts in enumerate(variants):
        for pi, draft in enumerate(parts):
            name = video.stem
            if len(variants) > 1:
                name += f"_v{vi + 1}"
            if len(parts) > 1:
                name += f"_phan{pi + 1}"
            plan = compile_plan(draft, idx, style, outputs)
            rounds = opt.critic_rounds
            if rounds is None:
                rounds = 1 if plan.duration <= float(os.environ.get("DIRECTOR_CRITIC_MAX_SEC", "180")) else 0
                if use_llm and rounds == 0:
                    log("Video dài: bỏ qua vòng tự xem lại để tiết kiệm thời gian (bật bằng --critic 1).")
            if use_llm and rounds > 0 and not opt.draft:
                try:
                    from .agent.critic import critique_loop

                    plan = critique_loop(plan, idx, style, job, name, rounds=rounds,
                                         render_draft=lambda p: render_plan(p, job, f"{name}_critic", job / "drafts", draft=True,
                                                                            has_audio=idx.source.has_audio))
                except Exception as e:
                    warn(f"Vòng tự xem lại lỗi, giữ bản hiện tại: {e}")
            plan_path = job / f"{name}.plan.json"
            plan_path.write_text(plan.model_dump_json(indent=1), encoding="utf-8")
            res.plans.append(plan_path)
            summaries.append(f"== {name} ==\n{summarize(plan)}")
            t_render = time.time()
            res.outputs += render_plan(plan, job, name, out_dir, draft=opt.draft, has_audio=idx.source.has_audio,
                                       upscale=opt.upscale)
            log(f"Dựng '{name}' mất {time.time() - t_render:.0f}s (video dài {plan.duration:.0f}s).")
            if opt.export_timeline:
                from .export.timeline import export_edl, export_otio

                export_edl(plan, out_dir / f"{name}.edl")
                export_otio(plan, out_dir / f"{name}.otio")
    if opt.remember:
        from .memory.store import remember_job

        remember_job(idx, style, opt.command)
    res.summary = "\n".join(summaries)
    (job / "last_job.json").write_text(json.dumps({"video": str(video.resolve()), "command": opt.command,
                                                    "outputs": [str(p) for p in res.outputs],
                                                    "plans": [str(p) for p in res.plans]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def revise_job(plan_path: str | Path, instruction: str, opt: JobOptions) -> JobResult:
    """Change an existing plan with a chat instruction, re-render only that plan."""
    plan_path = Path(plan_path)
    plan = EditPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    job = plan_path.parent
    idx = VideoIndex.model_validate(json.loads((job / "index.json").read_text(encoding="utf-8")))
    style = StyleDNA.model_validate_json((job / "style.json").read_text(encoding="utf-8"))
    from .agent.director import revise_draft

    draft, style = revise_draft(plan, idx, style, instruction, use_llm=llm_enabled(opt))
    outputs = parse_frames(style.frames, idx.source.width, idx.source.height)
    new_plan = compile_plan(draft, idx, style, outputs)
    new_plan.version = plan.version + 1
    name = plan_path.name.replace(".plan.json", "")
    hist = job / "history"
    hist.mkdir(exist_ok=True)
    shutil.copy(plan_path, hist / f"{name}.v{plan.version}.plan.json")
    plan_path.write_text(new_plan.model_dump_json(indent=1), encoding="utf-8")
    (job / "style.json").write_text(style.model_dump_json(indent=2), encoding="utf-8")
    res = JobResult(job_dir=job, plans=[plan_path], summary=summarize(new_plan))
    res.outputs = render_plan(new_plan, job, name, Path(opt.out_dir), draft=opt.draft, has_audio=idx.source.has_audio)
    if opt.remember:
        from .memory.store import remember_revision

        remember_revision(idx, instruction)
    return res
