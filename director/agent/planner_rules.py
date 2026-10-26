"""Offline rule-based planner: VideoIndex + StyleDNA -> PlanDraft(s).

Works with no API key. The LLM planner produces the same PlanDraft format."""

from __future__ import annotations

from dataclasses import dataclass

from ..effects.catalog import EFFECTS, EMOTION_COMBO
from ..effects.rules import Candidate, apply_rules
from ..perception.schema import Sentence, VideoIndex
from ..plan.schema import (
    DraftCaptions,
    DraftClip,
    DraftEffect,
    DraftMusic,
    DraftSfx,
    DraftTransition,
    PlanDraft,
)
from ..style.dna import StyleDNA

EMOTION_MUSIC = {
    "sad": "sad", "shock": "tense", "anger": "tense", "villain": "tense", "fear": "tense",
    "comedy": "comedy", "romance": "romance", "happy": "happy", "neutral": "happy",
}
EMOJI = {"shock": "😱", "anger": "😡", "sad": "😢", "comedy": "🤣", "romance": "😍", "fear": "😨", "villain": "😈", "happy": "😄"}


@dataclass
class Unit:
    t0: float
    t1: float
    score: float = 0.0
    sentence: Sentence | None = None
    keep: bool = False  # protected (hook/climax)

    @property
    def dur(self) -> float:
        return self.t1 - self.t0


# ---------------------------------------------------------------- 1. units


def speech_units(idx: VideoIndex, style: StyleDNA) -> list[Unit]:
    p = style.pacing
    D = idx.source.duration
    pad = p.keep_pause
    units: list[Unit] = []
    sents = [s for s in idx.sentences if not (p.remove_retakes and s.retake_of)]
    ocr_only = bool(sents) and all(s.source == "ocr" for s in sents)
    if ocr_only and idx.audio.silences:
        # OCR gives text but not word timing: cut on real audio pauses, then attach the sentence on screen
        units = speech_units(idx.model_copy(update={"sentences": []}), style)
        for u in units:
            best, ov = None, 0.0
            for s in sents:
                o = min(s.t1, u.t1) - max(s.t0, u.t0)
                if o > ov:
                    best, ov = s, o
            u.sentence = best
        return units
    if sents:
        for s in sents:
            words = [w for w in s.words if not (p.remove_fillers and w.filler)] if s.words else []
            if not words:
                units.append(Unit(max(0, s.t0 - pad), min(D, s.t1 + pad), sentence=s))
                continue
            cur0, prev = words[0].t0, words[0]
            for w in words[1:]:
                if w.t0 - prev.t1 > p.remove_silence_over:
                    units.append(Unit(max(0, cur0 - pad), min(D, prev.t1 + pad), sentence=s))
                    cur0 = w.t0
                prev = w
            units.append(Unit(max(0, cur0 - pad), min(D, prev.t1 + pad), sentence=s))
        units = _keep_action_gaps(idx, units, style)
    elif idx.source.has_audio and idx.audio.silences:
        t = 0.0
        for a, b in idx.audio.silences:
            if b - a < p.remove_silence_over:
                continue
            if a - t > 0.2:
                units.append(Unit(max(0, t - pad), min(D, a + pad)))
            t = b
        if D - t > 0.2:
            units.append(Unit(max(0, t - pad), D))
        units = _keep_action_gaps(idx, units, style)
    else:
        units = [Unit(s.t0, s.t1) for s in idx.scenes] or [Unit(0, D)]
    return _merge_close(units)


def _keep_action_gaps(idx: VideoIndex, units: list[Unit], style: StyleDNA) -> list[Unit]:
    """Silent stretches that contain action (loud events, motion, highlights) are kept (max 3s)."""
    out: list[Unit] = []
    prev_end = 0.0
    events = idx.audio.loud_events
    for u in sorted(units, key=lambda u: u.t0):
        gap0, gap1 = prev_end, u.t0
        if gap1 - gap0 > style.pacing.remove_silence_over:
            hot = [t for t in events if gap0 <= t <= gap1]
            moving = any(s.motion > 0.35 and s.t1 > gap0 and s.t0 < gap1 for s in idx.scenes)
            if hot:
                c = hot[0]
                out.append(Unit(max(gap0, c - 0.8), min(gap1, c + 1.2)))
            elif moving and gap1 - gap0 < 4:
                out.append(Unit(gap0, min(gap1, gap0 + 3.0)))
        out.append(u)
        prev_end = u.t1
    return out


def _merge_close(units: list[Unit], gap: float = 0.08, min_len: float = 0.45) -> list[Unit]:
    units = sorted(units, key=lambda u: u.t0)
    merged: list[Unit] = []
    for u in units:
        if merged and u.t0 - merged[-1].t1 <= gap:
            merged[-1].t1 = max(merged[-1].t1, u.t1)
            if merged[-1].sentence is None:
                merged[-1].sentence = u.sentence
        else:
            merged.append(Unit(u.t0, u.t1, sentence=u.sentence))
    out: list[Unit] = []
    for u in merged:
        if u.dur < min_len and out and u.t0 - out[-1].t1 < 1.0:
            out[-1].t1 = u.t1
        else:
            out.append(u)
    return [u for u in out if u.dur >= 0.25]


# ---------------------------------------------------------------- 2. scoring / trimming

EMO_W = {"shock": 1.0, "anger": 0.9, "villain": 0.8, "sad": 0.75, "fear": 0.7, "romance": 0.65, "comedy": 0.65}


def score_units(idx: VideoIndex, units: list[Unit]) -> None:
    for u in units:
        s = u.sentence
        sc = 0.2
        if s:
            sc += 0.4 * s.energy + 0.6 * EMO_W.get(s.emotion or "", 0.0)
        for h in idx.highlights:
            if h.t1 > u.t0 and h.t0 < u.t1:
                sc += 0.5 * min(1.0, h.score)
        for b in idx.story:
            if b.t1 > u.t0 and b.t0 < u.t1 and b.type in ("climax", "twist", "cliffhanger"):
                sc += 0.6 * b.intensity
                u.keep = u.keep or b.type in ("climax", "twist")
        u.score = round(sc, 3)


def trim_to_target(units: list[Unit], target: float) -> list[Unit]:
    total = sum(u.dur for u in units)
    if total <= target:
        return units
    order = sorted(range(len(units)), key=lambda i: (units[i].keep, units[i].score))
    drop: set[int] = set()
    for i in order:
        if total <= target:
            break
        if units[i].keep and total - units[i].dur < target * 0.9:
            continue
        drop.add(i)
        total -= units[i].dur
    return [u for i, u in enumerate(units) if i not in drop]


def split_parts(units: list[Unit], parts: int) -> list[list[Unit]]:
    if parts <= 1:
        return [units]
    total = sum(u.dur for u in units)
    per = total / parts
    groups: list[list[Unit]] = [[]]
    acc = 0.0
    for i, u in enumerate(units):
        groups[-1].append(u)
        acc += u.dur
        remaining_units = len(units) - i - 1
        if acc >= per * len(groups) and len(groups) < parts and remaining_units > 0:
            groups.append([])
    return [g for g in groups if g]


# ---------------------------------------------------------------- 3. hook


def pick_hook(idx: VideoIndex, units: list[Unit], style: StyleDNA) -> Unit | None:
    h = style.hook
    if not h.enabled or h.strategy == "none" or not units:
        return None
    D = idx.source.duration
    best, best_sc = None, -1.0
    for u in units:
        late = u.t0 > 0.25 * D
        bonus = 0.3 if (h.strategy == "twist-first-then-rewind" and late) else 0.0
        if u.sentence and u.sentence.emotion in ("shock", "anger", "villain"):
            bonus += 0.3
        sc = u.score + bonus
        if sc > best_sc:
            best, best_sc = u, sc
    if best is None or best.t0 < 2.0:
        return None
    t1 = min(best.t1, best.t0 + h.max_sec)
    if best.sentence and best.sentence.words:
        ends = [w.t1 for w in best.sentence.words if best.t0 < w.t1 <= best.t0 + h.max_sec]
        if ends:
            t1 = ends[-1] + 0.15
    return Unit(best.t0, t1, score=best.score, sentence=best.sentence)


# ---------------------------------------------------------------- 4. effects


def _timeline_of(clips: list[DraftClip]) -> list[float]:
    starts, t = [], 0.0
    for c in clips:
        starts.append(t)
        t += (c.src_out - c.src_in) / max(c.speed, 1e-3)
    return starts


def plan_effects(idx: VideoIndex, style: StyleDNA, clips: list[DraftClip], units: list[Unit | None]) -> tuple[list[DraftEffect], list[DraftSfx]]:
    starts = _timeline_of(clips)
    duration = starts[-1] + (clips[-1].src_out - clips[-1].src_in) / clips[-1].speed if clips else 0
    cands: list[Candidate] = []
    cam = style.camera
    emo_seen: set[str] = set()

    for ci, (c, u) in enumerate(zip(clips, units)):
        if c.role != "main":
            continue
        s = u.sentence if u else None
        t_clip = starts[ci]

        def tl(src_t: float) -> float:
            return t_clip + (src_t - c.src_in) / c.speed

        # anchor = loudest emphasized word inside the clip, or a loud event
        anchor_src = None
        if s and s.words:
            ws = [w for w in s.words if c.src_in <= w.t0 < c.src_out]
            if ws:
                w = max(ws, key=lambda w: w.emphasis)
                if w.emphasis >= 0.7:
                    anchor_src = w.t0
        events = [t for t in idx.audio.loud_events if c.src_in <= t < c.src_out]
        if events:
            anchor_src = events[0]
        emo = s.emotion if s else None
        if anchor_src is None and emo and emo != "neutral":
            anchor_src = c.src_in + 0.25 * (c.src_out - c.src_in)

        if emo in EMOTION_COMBO and anchor_src is not None:
            prio = 0.5 + 0.5 * (s.energy if s else 0.5)
            cid = EMOTION_COMBO[emo]
            # escalate: the very strongest moment of the video gets the strong combo
            cands.append(Candidate(cid, tl(anchor_src), prio, {"clip": ci, "at": anchor_src, "emo": emo}))
            emo_seen.add(emo)
        if emo in cam.punch_in_on and anchor_src is not None:
            cands.append(Candidate("punch_in", tl(anchor_src), 0.45, {"clip": ci, "at": anchor_src}))
        if emo in cam.shake_on and anchor_src is not None:
            cands.append(Candidate("shake", tl(anchor_src) + 0.01, 0.4, {"clip": ci, "at": anchor_src}))
        if cam.punch_in_on_emphasis and s and s.words:
            for w in s.words:
                if c.src_in <= w.t0 < c.src_out and w.emphasis >= 0.85:
                    cands.append(Candidate("punch_in", tl(w.t0), 0.3, {"clip": ci, "at": w.t0, "scale": 1.15}))
        # color by emotion (persistent across the clip)
        per = style.color.per_emotion
        if emo in per and per[emo] in EFFECTS:
            params = {"color": "#FF0000", "amount": 0.22} if per[emo] == "tint" and emo == "anger" else {}
            if per[emo] == "tint" and emo == "villain":
                params = {"color": "#3A0066", "amount": 0.3}
            cands.append(Candidate(per[emo], tl(c.src_in), 0.6, {"clip": ci, "at": c.src_in, "dur": (c.src_out - c.src_in) / c.speed, **params}, forced=True))
        # slow down on chosen emotions
        if emo in style.pacing.slow_down_on and (c.src_out - c.src_in) < 4:
            slow = "slow_hold" if idx.genre in ("anime", "cartoon3d") else "slow_interp"
            cands.append(Candidate(slow, tl(c.src_in), 0.5, {"clip": ci, "at": c.src_in, "factor": 0.75}))
        # long static anime shots get a gentle Ken Burns
        clip_len = (c.src_out - c.src_in) / c.speed
        static = any(sc.motion < 0.08 and sc.t0 <= c.src_in < sc.t1 for sc in idx.scenes)
        if cam.ken_burns_static and clip_len > 3.5 and static and emo in (None, "neutral"):
            cands.append(Candidate("ken_burns", tl(c.src_in), 0.2, {"clip": ci, "at": c.src_in, "dur": clip_len}))
        # emoji captions
        if style.captions.emoji and emo in EMOJI and anchor_src is not None:
            cands.append(Candidate("emoji_pop", tl(anchor_src) + 0.2, 0.25, {"clip": ci, "at": anchor_src + 0.2, "emoji": EMOJI[emo]}))

    for pid in style.preferred_effects:
        if pid in EFFECTS and EFFECTS[pid].category in ("stylize", "particles") and clips:
            cands.append(Candidate(pid, 0.0, 0.5, {"clip": 0, "at": clips[0].src_in, "dur": duration}, forced=True))

    kept = apply_rules(cands, style, duration)
    effects: list[DraftEffect] = []
    sfx: list[DraftSfx] = []
    for k in kept:
        p = dict(k.payload)
        ci, at = p.pop("clip"), p.pop("at")
        dur = p.pop("dur", None)
        p.pop("emo", None)
        d = EFFECTS[k.id].dur if k.id in EFFECTS else 1.0
        effects.append(DraftEffect(id=k.id, clip=ci, at=round(at, 3), dur=round(dur if dur else d, 3), params=p))
    return effects, sfx


def plan_transitions(idx: VideoIndex, style: StyleDNA, clips: list[DraftClip]) -> list[DraftTransition]:
    freq = {"none": 0, "low": 4, "medium": 2, "high": 1}.get(style.transitions.frequency, 4)
    accents = [a for a in style.transitions.accent if a in EFFECTS and a not in style.banned_effects]
    out: list[DraftTransition] = []
    k = 0
    for i in range(len(clips) - 1):
        a, b = clips[i], clips[i + 1]
        if a.role != "main" or b.role != "main":
            continue
        jump = b.src_in - a.src_out
        scene_change = any(a.src_out <= sc.t0 <= b.src_in + 0.05 for sc in idx.scenes) or jump > 2.0
        if scene_change and freq and accents:
            k += 1
            if k % freq == 0:
                tid = accents[(k // freq) % len(accents)]
                out.append(DraftTransition(after_clip=i, id=tid, dur=EFFECTS[tid].dur))
    return out


# ---------------------------------------------------------------- 5. main


def build_clips(units: list[Unit], hook: Unit | None) -> tuple[list[DraftClip], list[Unit | None]]:
    clips: list[DraftClip] = []
    owners: list[Unit | None] = []
    if hook:
        clips.append(DraftClip(src_in=round(hook.t0, 3), src_out=round(hook.t1, 3), role="hook", note="hook"))
        owners.append(hook)
    for u in units:
        clips.append(DraftClip(src_in=round(u.t0, 3), src_out=round(u.t1, 3)))
        owners.append(u)
    return clips, owners


def jump_cut_zoom(idx: VideoIndex, clips: list[DraftClip], effects: list[DraftEffect], style: StyleDNA) -> None:
    """Alternate a subtle zoom on consecutive clips of the same shot so jump cuts read as intentional."""
    if style.budget.intensity == "minimal":
        return
    toggle = False
    for i in range(1, len(clips)):
        a, b = clips[i - 1], clips[i]
        same_scene = not any(a.src_out <= sc.t0 <= b.src_in + 0.05 for sc in idx.scenes)
        if same_scene and 0.05 < b.src_in - a.src_out < 3.0 and b.role == "main":
            toggle = not toggle
            if toggle:
                effects.append(DraftEffect(id="zoom_hold", clip=i, at=b.src_in, dur=(b.src_out - b.src_in) / b.speed, params={"scale": 1.08}))
        else:
            toggle = False


def plan_rules(idx: VideoIndex, style: StyleDNA, intensity: str | None = None) -> list[PlanDraft]:
    if intensity:
        style = style.merged({"budget": {"intensity": intensity}})
    units = speech_units(idx, style)
    score_units(idx, units)
    if style.target_duration:
        units = trim_to_target(units, style.target_duration * max(1, style.parts) - (style.hook.max_sec if style.hook.enabled else 0))
    groups = split_parts(units, style.parts)
    drafts: list[PlanDraft] = []
    for gi, group in enumerate(groups):
        hook = pick_hook(idx, group, style)
        clips, owners = build_clips(group, hook)
        if not clips:
            continue
        effects, sfx = plan_effects(idx, style, clips, owners)
        transitions = plan_transitions(idx, style, clips)
        jump_cut_zoom(idx, clips, effects, style)
        title = style.extras.title
        if hook:
            # hook -> quick VHS rewind -> "Trước đó..." -> story
            effects.append(DraftEffect(id="rewind", clip=0, at=clips[0].src_out - 0.01, dur=1.0))
            effects.append(DraftEffect(id="time_skip", clip=1, at=clips[1].src_in, dur=1.4, params={"text": "Trước đó..."}))
            if title:
                effects.append(DraftEffect(id="title_slam", clip=0, at=clips[0].src_in, dur=min(2.0, clips[0].src_out - clips[0].src_in), params={"text": title}))
        elif title:
            effects.append(DraftEffect(id="title_slam", clip=0, at=clips[0].src_in, dur=1.8, params={"text": title}))
        if style.hook.strategy == "question" and title:
            effects.append(DraftEffect(id="question_hook", clip=0, at=clips[0].src_in, dur=2.4, params={"text": title}))
        last = len(clips) - 1
        if len(groups) > 1 and gi < len(groups) - 1:
            effects.append(DraftEffect(id="combo.cliffhanger", clip=last, at=max(clips[last].src_in, clips[last].src_out - 1.2), dur=1.2))
        elif style.extras.continue_card:
            effects.append(DraftEffect(id="continue_card", clip=last, at=max(clips[last].src_in, clips[last].src_out - 2.2), dur=2.2))
        if style.extras.cta:
            effects.append(DraftEffect(id="cta", clip=last, at=max(clips[last].src_in, clips[last].src_out - 2.5), dur=2.5))

        captions = DraftCaptions(enabled=style.captions.enabled, preset=style.captions.preset, mode="full")
        if idx.hardsub.present:
            mode = style.captions.if_hardsub
            captions.mode = "none" if mode == "none" else ("full" if mode == "full" else "emphasis-only")
        if not idx.sentences:
            captions.enabled = False

        music: list[DraftMusic] = []
        if style.audio.music_mood:
            music.append(DraftMusic(mood=style.audio.music_mood, from_clip=0, to_clip=-1))
        elif style.audio.bgm_by_emotion:
            run_mood, run_start = None, 0
            for ci, u in enumerate(owners):
                mood = EMOTION_MUSIC.get((u.sentence.emotion if u and u.sentence else None) or "neutral", "happy")
                if mood != run_mood:
                    if run_mood is not None:
                        music.append(DraftMusic(mood=run_mood, from_clip=run_start, to_clip=ci - 1))
                    run_mood, run_start = mood, ci
            if run_mood:
                music.append(DraftMusic(mood=run_mood, from_clip=run_start, to_clip=len(clips) - 1))

        drafts.append(PlanDraft(
            clips=clips, effects=effects, transitions=transitions, sfx=sfx, music=music, captions=captions,
            title=title, lut=style.color.lut, lut_intensity=style.color.intensity,
            notes=f"Phần {gi + 1}/{len(groups)} (planner offline)" if len(groups) > 1 else "planner offline",
        ))
    return drafts
