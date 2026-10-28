"""LLM Director: understands the command and the story, plans the edit, revises it from chat."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .. import i18n
from ..effects.catalog import COMBOS, EFFECTS, catalog_for_llm
from ..memory.store import preference_notes
from ..perception.schema import StoryBeat, VideoIndex
from ..plan.schema import DraftEffect, EditPlan, PlanDraft
from ..style.dna import StyleDNA
from ..style.parse import parse_style
from ..utils.log import log
from .llm import ask_json, image_block, provider, video_block
from .planner_rules import plan_rules
from .prompts import PLAN_SCHEMA, STYLE_FIELDS, SYSTEM_DIRECTOR

# ---------------------------------------------------------------- digests


def index_digest(idx: VideoIndex, words: bool = True, max_chars: int = 400_000) -> str:
    s = idx.source
    chars = ", ".join(f"{c.id}={c.name or '?'} ({c.appearances} lần)" for c in idx.characters) or "không phát hiện"
    lines = [
        f"VIDEO: {Path(s.path).name}, {s.width}x{s.height}, {s.fps:.2f}fps, {s.duration:.2f}s, thể loại: {idx.genre}, ngôn ngữ: {idx.language}",
        f"NHÂN VẬT: {chars}",
        f"PHỤ ĐỀ CÓ SẴN TRÊN HÌNH: {'có, vùng y=%.2f..%.2f (KHÔNG được che/xoá)' % (idx.hardsub.y, idx.hardsub.y + idx.hardsub.h) if idx.hardsub.present else 'không'}",
        f"TÓM TẮT: {idx.story_summary or '(chưa có)'}",
        "CẢNH (t0-t1 motion quality): " + "; ".join(f"{sc.t0:.2f}-{sc.t1:.2f} m{sc.motion:.2f} q{sc.quality:.2f}" for sc in idx.scenes),
        "KHOẢNG LẶNG: " + "; ".join(f"{a:.2f}-{b:.2f}" for a, b in idx.audio.silences),
        "ĐIỂM ÂM THANH BÙNG NỔ: " + ", ".join(f"{t:.2f}" for t in idx.audio.loud_events),
        f"BEAT NHẠC: tempo {idx.audio.tempo}, " + ", ".join(f"{t:.2f}" for t in idx.audio.beats[:200]),
        "HIGHLIGHT: " + "; ".join(f"{h.t0:.1f}-{h.t1:.1f} ({h.score:.2f} {h.reason})" for h in idx.highlights),
        "NHỊP TRUYỆN: " + "; ".join(f"{b.type} {b.t0:.1f}-{b.t1:.1f} ({b.intensity:.2f}) {b.summary}" for b in idx.story),
        "LỜI THOẠI (id [t0-t1] nhân vật cảm xúc năng lượng retake: text | từ: t0 text):",
    ]
    for se in idx.sentences:
        who = se.character or se.speaker or "-"
        head = f"{se.id} [{se.t0:.2f}-{se.t1:.2f}] {who} {se.emotion or '-'} e{se.energy:.2f}{' RETAKE→' + se.retake_of if se.retake_of else ''}: {se.text}"
        if words and se.words:
            head += " | " + " ".join(f"{w.t0:.2f}{'*' if w.emphasis >= 0.8 else ''}{'~' if w.filler else ''} {w.text}" for w in se.words)
        lines.append(head)
    out = "\n".join(lines)
    if len(out) > max_chars:
        return index_digest(idx, words=False, max_chars=max_chars * 2)[:max_chars]
    return out


def keyframe_blocks(idx: VideoIndex, limit: int = 16) -> list[dict]:
    kfs = idx.keyframes
    if len(kfs) > limit:
        step = len(kfs) / limit
        kfs = [kfs[int(i * step)] for i in range(limit)]
    blocks: list[dict] = []
    for kf in kfs:
        try:
            blocks.append({"type": "text", "text": f"[khung hình t={kf['t']:.2f}s]"})
            blocks.append(image_block(kf["path"], 640))
        except Exception:
            continue
    return blocks


# ---------------------------------------------------------------- style


def refine_style(command: str, style: StyleDNA, idx: VideoIndex) -> StyleDNA:
    prompt = f"""User command (Vietnamese, free form): {command!r}
Video genre: {idx.genre}; duration {idx.source.duration:.1f}s; burned-in subtitles: {idx.hardsub.present}.
Current style (from a rule-based parser, may be incomplete or wrong):
{style.model_dump_json(indent=1)}

{STYLE_FIELDS}
Return a JSON object {{"patch": {{...}}, "explain": "short Vietnamese explanation"}} with only the fields that must change
so the style matches the user's command exactly. Do not invent requirements the user did not ask for."""
    data = ask_json(SYSTEM_DIRECTOR, prompt, effort="medium", max_tokens=8000)
    patch = data.get("patch") or {}
    new = style.merged(patch)
    log(f"AI hiểu lệnh: {data.get('explain', '')}")
    return new


# ---------------------------------------------------------------- story


def understand_story(idx: VideoIndex, job: Path) -> None:
    cache = job / "story.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        content: list[dict] = [{"type": "text", "text": index_digest(idx)}]
        for c in idx.characters[:8]:
            if c.thumbnail and Path(c.thumbnail).exists():
                content.append({"type": "text", "text": f"[ảnh nhân vật {c.id}]"})
                content.append(image_block(c.thumbnail, 256))
        content += keyframe_blocks(idx)
        if provider() in ("antigravity", "gemini") and idx.source.duration <= 3600:
            # Gemini watches the whole video (picture + sound), not just sampled frames
            content.append({"type": "text", "text": "[toàn bộ video gốc]"})
            content.append(video_block(idx.source.path))
        content.append({"type": "text", "text": """Analyse this video for editing. Return JSON:
{"summary": "2-4 câu tóm tắt câu chuyện (tiếng Việt)",
 "characters": {"C0": {"name": "tên nếu biết từ lời thoại, hoặc vai như 'Mẹ chồng'", "role": "nữ chính|phản diện|..."}},
 "sentences": {"s3": {"emotion": "shock|anger|sad|comedy|romance|fear|villain|happy|neutral", "character": "C0|null"}},
 "beats": [{"t0": 12.0, "t1": 18.5, "type": "setup|conflict|climax|twist|resolution|cliffhanger|comedy|romance", "intensity": 0.0-1.0, "summary": "..."}],
 "retakes": ["s5"],
 "hook_candidates": [{"t0": 40.1, "t1": 43.0, "why": "..."}]}
Only include sentences whose emotion/character you are correcting. Times are source seconds."""})
        data = ask_json(SYSTEM_DIRECTOR, content, effort="high", max_tokens=16000)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    apply_story(idx, data)
    log(f"AI tóm tắt: {idx.story_summary[:200]}")


def apply_story(idx: VideoIndex, data: dict) -> None:
    idx.story_summary = data.get("summary") or idx.story_summary
    for cid, info in (data.get("characters") or {}).items():
        for c in idx.characters:
            if c.id == cid and isinstance(info, dict) and info.get("name"):
                c.name = info["name"]
    by_id = {s.id: s for s in idx.sentences}
    for sid, info in (data.get("sentences") or {}).items():
        s = by_id.get(sid)
        if s and isinstance(info, dict):
            if info.get("emotion"):
                s.emotion = info["emotion"]
            if info.get("character"):
                s.character = info["character"]
    for sid in data.get("retakes") or []:
        s = by_id.get(sid)
        if s and not s.retake_of:
            s.retake_of = "llm"
    beats = []
    for b in data.get("beats") or []:
        try:
            beats.append(StoryBeat(**{k: b[k] for k in ("t0", "t1", "type") if k in b}, intensity=float(b.get("intensity", 0.5)), summary=b.get("summary", "")))
        except Exception:
            continue
    if beats:
        idx.story = sorted(beats, key=lambda b: b.t0)


# ---------------------------------------------------------------- planning


def _validate_drafts(data: Any, D: float) -> list[PlanDraft]:
    parts = data.get("parts") if isinstance(data, dict) else data
    if isinstance(data, dict) and "clips" in data:
        parts = [data]
    if not isinstance(parts, list) or not parts:
        raise ValueError("cần {'parts': [PlanDraft, ...]}")
    out = []
    for pi, p in enumerate(parts):
        d = PlanDraft.model_validate(p)
        problems = []
        for i, c in enumerate(d.clips):
            if not (0 <= c.src_in < c.src_out <= D + 0.05) and c.freeze is None:
                problems.append(f"part {pi} clip {i}: khoảng {c.src_in}-{c.src_out} sai (video dài {D:.2f}s)")
        for e in d.effects:
            if e.id not in EFFECTS and e.id not in COMBOS:
                problems.append(f"part {pi}: hiệu ứng không tồn tại '{e.id}'")
            elif not (0 <= e.clip < len(d.clips)):
                problems.append(f"part {pi}: effect {e.id} clip index {e.clip} sai")
            else:
                c = d.clips[e.clip]
                if not (c.src_in - 0.05 <= e.at <= c.src_out + 0.05) and c.freeze is None:
                    problems.append(f"part {pi}: effect {e.id} at={e.at} nằm ngoài clip {e.clip} ({c.src_in}-{c.src_out})")
        for tr in d.transitions:
            if tr.id not in EFFECTS:
                problems.append(f"part {pi}: chuyển cảnh không tồn tại '{tr.id}'")
        if problems:
            raise ValueError("; ".join(problems[:20]))
        out.append(d)
    return out


def plan_with_llm(idx: VideoIndex, style: StyleDNA, command: str, variant: str | None = None) -> list[PlanDraft]:
    baseline = plan_rules(idx, style)
    prefs = preference_notes()
    D = idx.source.duration
    need_story = not idx.story_summary  # one AI call does story understanding + planning (much faster)
    content: list[dict] = [
        {"type": "text", "text": index_digest(idx)},
        *keyframe_blocks(idx, 12),
    ]
    if need_story and provider() in ("antigravity", "gemini") and idx.source.duration <= 3600:
        content += [{"type": "text", "text": "[toàn bộ video gốc]"}, video_block(idx.source.path)]
    story_req = ("""
ALSO understand the story first and return it in "story": {"summary": "2-4 câu tóm tắt (tiếng Việt)",
 "characters": {"C0": {"name": "tên từ lời thoại hoặc vai"}}, "sentences": {"s3": {"emotion": "...", "character": "C0"}},
 "beats": [{"t0": 0, "t1": 0, "type": "setup|conflict|climax|twist|resolution|cliffhanger", "intensity": 0.0, "summary": ""}]}
Only include sentences you correct.""" if need_story else "")
    content += [
        {"type": "text", "text": f"""EFFECT CATALOG:
{catalog_for_llm()}

{PLAN_SCHEMA}

STYLE (must follow):
{style.model_dump_json(indent=1)}

USER COMMAND: {command!r}
{('VARIANT: make this the "' + variant + '" version (chuẩn = balanced, mạnh tay = bold/many effects, an toàn = restrained).') if variant else ''}
USER TASTE (recent requests, newest first): {prefs or 'none'}
ON-SCREEN TEXT LANGUAGE: {i18n.name(i18n.resolve(style.text_language, idx.language))} ({i18n.resolve(style.text_language, idx.language)}). Spoken language: {idx.language}.
TARGET DURATION: {style.target_duration or 'as needed'} s; PARTS: {style.parts}; HOOK: {style.hook.strategy}, hook clip {style.hook.min_sec:g}-{style.hook.max_sec:g} s long, ending after a complete word; no SFX on the jump from the hook back into the story.
CAPTIONS: burned-in subtitles present = {idx.hardsub.present} -> follow captions.if_hardsub = {style.captions.if_hardsub}.

An automatic baseline plan (valid, rule-based) is below. Improve it like a top editor: better hook, smarter cuts at
word boundaries (use word timings), effects/sfx placed exactly on the right words/beats, music, titles in the on-screen text language.
Baseline: {json.dumps({'parts': [b.model_dump() for b in baseline]}, ensure_ascii=False)}

{story_req}
Return JSON: {{{'"story": {...}, ' if need_story else ''}"parts": [PlanDraft, ...]}} with exactly {style.parts} part(s)."""},
    ]
    holder: dict = {}

    def validate(d: Any):
        holder["story"] = d.get("story") if isinstance(d, dict) else None
        return _validate_drafts(d, D)

    drafts = ask_json(SYSTEM_DIRECTOR, content, validate=validate, effort="high", max_tokens=64000)
    if holder.get("story"):
        try:
            apply_story(idx, holder["story"])
            log(f"AI tóm tắt: {idx.story_summary[:200]}")
        except Exception:
            pass
    for d in drafts:
        log(f"AI lên kế hoạch: {len(d.clips)} đoạn, {len(d.effects)} hiệu ứng. {d.notes}")
    return drafts


# ---------------------------------------------------------------- revision


_TS = re.compile(r"(\d{1,2}):(\d{2})")


def _rule_revise(plan: EditPlan, idx: VideoIndex, style: StyleDNA, instruction: str) -> tuple[PlanDraft, StyleDNA]:
    """Offline revision: style-level changes via the parser, plus a few direct edits."""
    text = instruction.lower()
    new_style = parse_style(instruction, idx.genre, style)
    draft = plan.draft.model_copy(deep=True) if plan.draft else plan_rules(idx, new_style)[0]
    structural = any(k in text for k in ("nhanh", "chậm", "giây", "phút", "phần", "hook", "cắt", "hiệu ứng", "tối giản", "nhiều"))
    if structural:
        draft = plan_rules(idx, new_style)[0]
    # "bỏ đoạn 0:40" -> drop the clip playing at that output time
    if "bỏ" in text or "xoá" in text or "xóa" in text:
        for m in _TS.finditer(text):
            t = int(m.group(1)) * 60 + int(m.group(2))
            hit = next((c for c in plan.clips if c.start <= t < c.start + c.duration), None)
            if hit is not None:
                keep = [i for i, dc in enumerate(draft.clips) if not (abs(dc.src_in - hit.src_in) < 0.05 and abs(dc.src_out - hit.src_out) < 0.05)]
                remap = {old: new for new, old in enumerate(keep)}
                draft.clips = [draft.clips[i] for i in keep]
                draft.effects = [e.model_copy(update={"clip": remap[e.clip]}) for e in draft.effects if e.clip in remap]
                draft.sfx = [s.model_copy(update={"clip": remap[s.clip]}) for s in draft.sfx if s.clip in remap]
                draft.transitions = [tr.model_copy(update={"after_clip": remap[tr.after_clip]}) for tr in draft.transitions if tr.after_clip in remap]
    if "tiêu đề" in text:
        m = re.search(r"tiêu đề\s*(?:là|:)?\s*[\"“]?([^\"”\n]+)", instruction, re.IGNORECASE)
        if m:
            draft.title = m.group(1).strip()
            draft.effects = [e for e in draft.effects if e.id != "title_slam"]
            draft.effects.append(DraftEffect(id="title_slam", clip=0, at=draft.clips[0].src_in, dur=1.8, params={"text": draft.title}))
    return draft, new_style


def revise_draft(plan: EditPlan, idx: VideoIndex, style: StyleDNA, instruction: str, use_llm: bool) -> tuple[PlanDraft, StyleDNA]:
    if not use_llm:
        return _rule_revise(plan, idx, style, instruction)
    D = idx.source.duration
    timeline = "\n".join(f"{c.id} output {c.start:.2f}-{c.start + c.duration:.2f} <- source {c.src_in:.2f}-{c.src_out:.2f} ({c.role})" for c in plan.clips)
    content = [{"type": "text", "text": f"""{index_digest(idx)}

EFFECT CATALOG:
{catalog_for_llm()}

{PLAN_SCHEMA}
{STYLE_FIELDS}

CURRENT STYLE: {style.model_dump_json()}
CURRENT DRAFT: {plan.draft.model_dump_json() if plan.draft else 'null'}
CURRENT OUTPUT TIMELINE (what the user watched; times the user mentions refer to OUTPUT time):
{timeline}

ON-SCREEN TEXT LANGUAGE: {i18n.resolve(style.text_language, idx.language)}
USER REQUEST: {instruction!r}

Change ONLY what the request needs; keep everything else identical. Return JSON:
{{"style_patch": {{...}}, "draft": PlanDraft, "explain": "ngắn gọn, tiếng Việt"}}"""}]

    def validate(d: Any):
        if not isinstance(d, dict) or "draft" not in d:
            raise ValueError("cần {'style_patch', 'draft'}")
        return d, _validate_drafts({"parts": [d["draft"]]}, D)[0]

    data, draft = ask_json(SYSTEM_DIRECTOR, content, validate=validate, effort="high", max_tokens=48000)
    new_style = style.merged(data.get("style_patch") or {})
    log(f"AI sửa: {data.get('explain', '')}")
    return draft, new_style
