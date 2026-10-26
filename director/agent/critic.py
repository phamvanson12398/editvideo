"""Critic loop: render a fast draft, look at it (automatic checks + Claude vision), fix the plan, repeat."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from ..effects.catalog import catalog_for_llm
from ..perception.schema import VideoIndex
from ..plan.compiler import compile_plan, summarize
from ..plan.schema import EditPlan
from ..style.dna import StyleDNA
from ..utils.ffmpeg import run, run_stderr
from ..utils.log import log
from .director import _validate_drafts
from .llm import ask_json, image_block
from .prompts import PLAN_SCHEMA, SYSTEM_DIRECTOR

PASS_SCORE = 8.0


def auto_check(plan: EditPlan, style: StyleDNA, video: Path | None = None) -> list[str]:
    """Deterministic checks a human editor would do. Returns readable issues."""
    issues: list[str] = []
    for c in plan.clips:
        if c.duration < 0.3 and c.role == "main":
            issues.append(f"Đoạn {c.id} ở {c.start:.1f}s quá ngắn ({c.duration:.2f}s), gây giật.")
    if style.target_duration:
        target = style.target_duration
        if abs(plan.duration - target) > max(3.0, 0.15 * target):
            issues.append(f"Thời lượng {plan.duration:.1f}s lệch mục tiêu {target:.0f}s.")
    vertical = any(o.height > o.width for o in plan.outputs)
    for ln in plan.captions.lines:
        chars = sum(len(w.text) + 1 for w in ln.words)
        if chars > (26 if vertical else 48) * plan.captions.size ** -1:
            issues.append(f"Dòng phụ đề ở {ln.t0:.1f}s quá dài ({chars} ký tự).")
            break
    starts = sorted(s.start for s in plan.audio.sfx)
    for a, b, c in zip(starts, starts[1:], starts[2:]):
        if c - a < 0.4:
            issues.append(f"Quá nhiều tiếng động chồng nhau quanh {a:.1f}s.")
            break
    strong = [e for e in plan.effects if e.id in ("flash_white", "snap_zoom", "impact_frame", "glitch_cut")]
    for a, b in zip(strong, strong[1:]):
        if b.start - a.start < 2.0:
            issues.append(f"Hiệu ứng mạnh dồn dập ở {a.start:.1f}s và {b.start:.1f}s.")
            break
    if video and video.exists():
        err = run_stderr(["-i", str(video), "-vf", "blackdetect=d=0.4:pix_th=0.06", "-an", "-f", "null", "-"])
        for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", err):
            issues.append(f"Khung đen {float(m.group(1)):.1f}-{float(m.group(2)):.1f}s.")
    return issues


def sample_frames(plan: EditPlan, video: Path, out_dir: Path, limit: int = 24) -> list[tuple[float, Path]]:
    times = set()
    for c in plan.clips:
        times.add(round(c.start + min(0.4, c.duration / 2), 2))
    for e in plan.effects:
        if e.category in ("text", "manga", "tx", "camera", "overlap") and e.end - e.start < 20:
            times.add(round((e.start + e.end) / 2, 2))
    ts = sorted(t for t in times if t < plan.duration - 0.05)
    if len(ts) > limit:
        step = len(ts) / limit
        ts = [ts[int(i * step)] for i in range(limit)]
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, t in enumerate(ts):
        p = out_dir / f"crit_{i:03d}.jpg"
        try:
            run(["-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "4", str(p)])
            frames.append((t, p))
        except Exception:
            continue
    return frames


def critique_loop(plan: EditPlan, idx: VideoIndex, style: StyleDNA, job: Path, name: str, *, rounds: int,
                  render_draft: Callable[[EditPlan], list[Path]]) -> EditPlan:
    history = []
    for r in range(rounds):
        log(f"Vòng tự xem lại {r + 1}/{rounds}: dựng bản nháp...")
        videos = render_draft(plan)
        video = videos[0]
        issues = auto_check(plan, style, video)
        frames = sample_frames(plan, video, job / "critic" / f"r{r}")
        content: list[dict] = []
        for t, p in frames:
            content.append({"type": "text", "text": f"[bản nháp t={t:.2f}s]"})
            content.append(image_block(p, 640))
        content.append({"type": "text", "text": f"""You are reviewing a DRAFT render of your own edit ({plan.outputs[0].width}x{plan.outputs[0].height}).
Style requested: {style.description or style.name}
Plan summary:
{summarize(plan)}
Timeline: {json.dumps([{'id': c.id, 'out': [round(c.start, 2), round(c.start + c.duration, 2)], 'src': [c.src_in, c.src_out], 'role': c.role} for c in plan.clips])}
Effects: {json.dumps([{'id': e.id, 't': [round(e.start, 2), round(e.end, 2)]} for e in plan.effects])}
Captions (first 40 lines): {json.dumps([{'t': round(l.t0, 2), 'text': ' '.join(w.text for w in l.words)} for l in plan.captions.lines[:40]], ensure_ascii=False)}
Automatic checks found: {issues or 'nothing'}
Previous rounds: {history or 'none'}

Score the draft 0-10 against: matches the requested style; 3-second hook strength; no cut mid-word; captions readable,
correct, not covering faces or burned-in text; pacing (no dull stretch); effects motivated and not overused; frame/reframe
keeps the subject in view. Then fix the plan.

{PLAN_SCHEMA}
EFFECT CATALOG (ids):
{catalog_for_llm()}
CURRENT DRAFT: {plan.draft.model_dump_json() if plan.draft else 'null'}

Return JSON: {{"score": float, "pass": bool, "issues": [{{"t": float, "problem": "tiếng Việt", "fix": "..."}}],
"draft": PlanDraft (the corrected draft; identical to the current one if pass is true)}}"""})
        D = idx.source.duration

        def validate(d):
            if not isinstance(d, dict) or "score" not in d:
                raise ValueError("cần score/pass/issues/draft")
            fixed = _validate_drafts({"parts": [d["draft"]]}, D)[0] if d.get("draft") else None
            return d, fixed

        data, fixed = ask_json(SYSTEM_DIRECTOR, content, validate=validate, effort="high", max_tokens=48000)
        score = float(data.get("score", 0))
        log(f"  Điểm bản nháp: {score:.1f}/10; {len(data.get('issues', []))} vấn đề.")
        for it in data.get("issues", [])[:8]:
            log(f"   - {it.get('t', '?')}s: {it.get('problem', '')}")
        history.append({"round": r + 1, "score": score, "issues": [i.get("problem") for i in data.get("issues", [])][:10]})
        (job / f"{name}.critic.json").write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
        if data.get("pass") or score >= PASS_SCORE or fixed is None:
            break
        plan = compile_plan(fixed, idx, style, plan.outputs)
    return plan
