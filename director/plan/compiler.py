"""Compile a PlanDraft (source-time decisions) into a timeline EditPlan for the renderer."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import i18n
from ..effects.catalog import COMBOS, EFFECTS
from ..perception.schema import VideoIndex
from ..render.sfx_synth import sfx_file
from ..style.dna import StyleDNA
from ..utils.log import warn
from .frames import safe_zone
from .schema import (
    AudioClipFx,
    AudioPlan,
    CaptionLine,
    CaptionTrack,
    CaptionWord,
    Clip,
    ClipReframe,
    EditPlan,
    Effect,
    MusicCue,
    OutputSpec,
    PlanDraft,
    ReframeKey,
    SfxCue,
    VolumeEvent,
)

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"

EMOJI_FOR = {"shock": "😱", "anger": "😡", "sad": "😢", "comedy": "🤣", "romance": "😍", "fear": "😨", "villain": "😈"}
NO_CAPTION_ROLES = {"rewind", "freeze", "stutter", "replay", "reverse"}
SILENT_ROLES = {"rewind", "freeze"}


@dataclass
class WClip:
    src_in: float
    src_out: float
    orig: int
    speed: float = 1.0
    reverse: bool = False
    freeze: float | None = None  # source time to hold
    hold_len: float = 0.0  # output seconds for freeze clips
    role: str = "main"
    reframe: str | None = None
    interp: bool = False
    filters: list[str] = field(default_factory=list)  # extra ffmpeg filters at prep (e.g. colorhold)

    @property
    def out_dur(self) -> float:
        if self.freeze is not None:
            return self.hold_len
        return max(0.04, (self.src_out - self.src_in) / max(self.speed, 1e-3))

    def contains(self, t: float) -> bool:
        return self.src_in - 1e-3 <= t <= self.src_out + 1e-3


@dataclass
class IEffect:
    id: str
    at: float  # source time
    dur: float
    params: dict[str, Any]
    orig: int | None = None  # resolve against clips with this draft index
    target: WClip | None = None  # or a fixed working clip
    reason: str = ""


@dataclass
class ISfx:
    id: str
    at: float
    orig: int | None = None
    target: WClip | None = None
    gain_db: float = 0.0


def _resolve(clips: list[WClip], orig: int | None, target: WClip | None, at: float) -> WClip | None:
    if target is not None and target in clips:
        return target
    cands = [c for c in clips if c.orig == orig and c.freeze is None and c.role not in ("rewind", "stutter")]
    for c in cands:
        if c.contains(at):
            return c
    if cands:
        return min(cands, key=lambda c: min(abs(c.src_in - at), abs(c.src_out - at)))
    return None


# ---------------------------------------------------------------- step 1: combos & auto sfx


def expand(draft: PlanDraft, style: StyleDNA) -> tuple[list[IEffect], list[ISfx], list]:
    effects: list[IEffect] = []
    sfx: list[ISfx] = []
    transitions = list(draft.transitions)
    want_sfx = style.audio.sfx
    for e in draft.effects:
        if e.clip < 0 or e.clip >= len(draft.clips):
            continue
        speed = draft.clips[e.clip].speed or 1.0
        if e.id in COMBOS:
            for step_id, off, dur, params in COMBOS[e.id]["steps"]:
                at = e.at + off * speed
                if step_id.startswith("sfx:"):
                    if want_sfx:
                        sfx.append(ISfx(step_id[4:], at, orig=e.clip))
                    continue
                d = dur if dur is not None else (EFFECTS[step_id].dur if step_id in EFFECTS else 1.0)
                if step_id in EFFECTS and EFFECTS[step_id].category in ("overlap", "tx") and step_id not in ("flash_white", "fade_black"):
                    pass
                effects.append(IEffect(step_id, at, d, {**params, **e.params}, orig=e.clip, reason=e.reason or e.id))
        elif e.id in EFFECTS:
            effects.append(IEffect(e.id, e.at, e.dur or EFFECTS[e.id].dur, dict(e.params), orig=e.clip, reason=e.reason))
            if want_sfx and EFFECTS[e.id].sfx and EFFECTS[e.id].category not in ("time",):
                sfx.append(ISfx(EFFECTS[e.id].sfx, e.at, orig=e.clip))
        else:
            warn(f"Bỏ qua hiệu ứng không có trong thư viện: {e.id}")
    for s in draft.sfx:
        if want_sfx:
            sfx.append(ISfx(s.id, s.at, orig=s.clip, gain_db=s.gain_db))
    return effects, sfx, transitions


# ---------------------------------------------------------------- step 2: time effects


def apply_time_effects(clips: list[WClip], effects: list[IEffect], sfx: list[ISfx], genre: str) -> list[IEffect]:
    rest: list[IEffect] = []
    time_fx = [e for e in effects if e.id in EFFECTS and EFFECTS[e.id].category == "time"]
    rest = [e for e in effects if e not in time_fx]
    for e in sorted(time_fx, key=lambda e: (e.orig or 0, e.at), reverse=True):
        c = _resolve(clips, e.orig, e.target, e.at)
        if c is None:
            continue
        i = clips.index(c)
        p = e.params
        at = min(max(e.at, c.src_in), c.src_out)
        if e.id in ("speed", "timelapse"):
            c.speed = float(p.get("factor", EFFECTS[e.id].params.get("factor", 1.5)))
        elif e.id in ("slow_hold", "slow_interp"):
            c.speed = float(p.get("factor", 0.5))
            c.interp = e.id == "slow_interp" and genre not in ("anime", "cartoon3d")
        elif e.id == "reverse":
            c.reverse = True
        elif e.id == "boomerang":
            back = copy.copy(c)
            back.reverse, back.role = True, "reverse"
            clips.insert(i + 1, back)
        elif e.id == "replay":
            a, b = max(c.src_in, at - 0.6), min(c.src_out, at + 1.2)
            if b - a > 0.3:
                rep = WClip(a, b, c.orig, speed=float(p.get("factor", 0.5)), role="replay", interp=genre not in ("anime", "cartoon3d"))
                clips.insert(i + 1, rep)
                rest.append(IEffect("punch_in", a, rep.out_dur, {"scale": 1.3}, target=rep))
                rest.append(IEffect("vignette", a, rep.out_dur, {"amount": 0.4}, target=rep))
        elif e.id == "stutter":
            ln = float(p.get("length", 0.15))
            n = int(p.get("repeats", 3))
            if at + ln < c.src_out and at - c.src_in > 0.1:
                head = copy.copy(c)
                head.src_out = at
                tail = copy.copy(c)
                tail.src_in = at
                reps = [WClip(at, at + ln, c.orig, speed=c.speed, role="stutter") for _ in range(n - 1)]
                clips[i:i + 1] = [head] + reps + [tail]
        elif e.id in ("freeze_frame", "freeze_intro"):
            hold = WClip(at, at, c.orig, freeze=at, hold_len=max(0.4, e.dur), role="freeze")
            if at - c.src_in > 0.15 and c.src_out - at > 0.15:
                head = copy.copy(c)
                head.src_out = at
                tail = copy.copy(c)
                tail.src_in = at
                clips[i:i + 1] = [head, hold, tail]
            else:
                clips.insert(i + 1 if at >= c.src_out - 0.15 else i, hold)
            if e.id == "freeze_intro":
                rest.append(IEffect("character_card", at, e.dur, {"text": p.get("text", ""), "subtitle": p.get("subtitle", "")}, target=hold))
            rest.append(IEffect("vignette", at, e.dur, {"amount": 0.35}, target=hold))
        elif e.id == "rewind":
            a = max(c.src_in, c.src_out - 3.0)
            rw = WClip(a, c.src_out, c.orig, speed=max(2.5, (c.src_out - a) / max(0.5, e.dur)), reverse=True, role="rewind")
            clips.insert(i + 1, rw)
            rest.append(IEffect("vhs", a, rw.out_dur, {"rewind": True}, target=rw))
            sfx.append(ISfx("rewind_tape", a, target=rw))
        elif e.id == "speed_ramp":
            lo, hi = float(p.get("low", 0.5)), float(p.get("high", 2.0))
            a, b = max(c.src_in, at - 0.2), min(c.src_out, at + 0.8)
            pieces = []
            if a - c.src_in > 0.3:
                pieces.append(WClip(c.src_in, a, c.orig, speed=hi, role=c.role))
            pieces.append(WClip(a, b, c.orig, speed=lo, role=c.role, interp=genre not in ("anime", "cartoon3d")))
            if c.src_out - b > 0.3:
                pieces.append(WClip(b, c.src_out, c.orig, speed=hi, role=c.role))
            clips[i:i + 1] = pieces
    return rest


# ---------------------------------------------------------------- step 3: reframe


def crop_size(src_w: int, src_h: int, out: OutputSpec) -> tuple[float, float]:
    """Largest crop of the output aspect that fits the source, in source-normalized units."""
    a_src = src_w / src_h
    a_out = out.width / out.height
    if out.letterbox:
        a_out = 2.39
    if a_out < a_src:
        return a_out / a_src, 1.0
    return 1.0, a_src / a_out


def _main_box(boxes, prefer: str | None):
    if not boxes:
        return None
    if prefer:
        for b in boxes:
            if b.character == prefer:
                return b
    return max(boxes, key=lambda b: b.w * b.h)


def follow_keys(idx: VideoIndex, c: WClip, cw: float, ch: float, prefer: str | None) -> list[ReframeKey]:
    keys: list[ReframeKey] = []
    step = 0.5
    t = c.src_in if c.freeze is None else c.freeze
    end = c.src_out if c.freeze is None else c.freeze
    cx, cy = 0.5, 0.5
    first = True
    while True:
        box = _main_box(idx.faces_at(t), prefer)
        if box is not None:
            tx = box.x + box.w / 2
            ty = box.y + box.h * 0.75  # keep headroom: face sits in the upper part of the frame
            if first:
                cx, cy = tx, ty
            else:
                if abs(tx - cx) > 0.06 * cw:
                    cx += 0.35 * (tx - cx)
                if abs(ty - cy) > 0.06 * ch:
                    cy += 0.35 * (ty - cy)
            first = False
        kx = min(max(cx, cw / 2), 1 - cw / 2)
        ky = min(max(cy, ch / 2), 1 - ch / 2)
        if c.freeze is not None:
            rel = 0.0
        elif c.reverse:
            rel = (c.src_out - t) / c.speed
        else:
            rel = (t - c.src_in) / c.speed
        keys.append(ReframeKey(t=round(rel, 3), cx=round(kx, 4), cy=round(ky, 4)))
        if t >= end:
            break
        t = min(end, t + step)
    keys.sort(key=lambda k: k.t)
    return keys


def clip_has_dialogue(idx: VideoIndex, c: WClip) -> bool:
    return any(s.t1 > c.src_in and s.t0 < c.src_out for s in idx.sentences) or (
        idx.hardsub.present and any(l["t1"] > c.src_in and l["t0"] < c.src_out for l in idx.hardsub.lines)
    )


def speaking_character(idx: VideoIndex, c: WClip) -> str | None:
    best, ov = None, 0.0
    for s in idx.sentences:
        o = min(s.t1, c.src_out) - max(s.t0, c.src_in)
        if o > ov and s.character:
            best, ov = s.character, o
    return best


def decide_reframe(idx: VideoIndex, style: StyleDNA, c: WClip, out: OutputSpec) -> ClipReframe:
    sw, sh = idx.source.width, idx.source.height
    cw, ch = crop_size(sw, sh, out)
    if out.letterbox:
        return ClipReframe(mode="letterbox", keys=[ReframeKey(t=0, cx=0.5, cy=0.5)])
    if abs(cw - 1) < 0.03 and abs(ch - 1) < 0.03:
        return ClipReframe(mode="center", keys=[ReframeKey(t=0, cx=0.5, cy=0.5)])
    mode = (c.reframe or style.camera.reframe or "auto").replace("_", "-")
    hs = idx.hardsub
    if mode == "auto":
        cuts_text = hs.present and style.existing_text == "avoid" and (cw < hs.w + 0.02 or ch < 1 - hs.y + 0.02)
        if cuts_text and clip_has_dialogue(idx, c):
            return ClipReframe(mode="fit-blur", keys=[ReframeKey(t=0, cx=0.5, cy=0.5)])
        mode = "follow-face" if idx.faces and any(f.boxes for f in idx.faces) else "center"
    if mode in ("fit-blur", "fit-pad", "letterbox"):
        return ClipReframe(mode=mode, keys=[ReframeKey(t=0, cx=0.5, cy=0.5)])
    if mode == "split":
        tracks = []
        chars = [ch_.id for ch_ in idx.characters[:2]]
        for ch_id in chars:
            tracks.append(follow_keys(idx, c, cw, ch, ch_id))
        if len(tracks) == 2:
            return ClipReframe(mode="split", keys=tracks[0], split_keys=tracks)
        mode = "follow-face"
    if mode in ("follow-face", "follow-character", "follow", "follow-subject", "speaker-switch"):
        prefer = speaking_character(idx, c)
        return ClipReframe(mode="follow", keys=follow_keys(idx, c, cw, ch, prefer))
    return ClipReframe(mode="center", keys=[ReframeKey(t=0, cx=0.5, cy=0.5)])


# ---------------------------------------------------------------- step 4: captions


def _is_emphasis(w, emotion: str | None) -> bool:
    return w.emphasis >= 0.8 or w.text.strip(".,!?…").lower() in {"không", "sao", "gì", "cái gì", "trời", "chết", "yêu", "ghét"} and emotion not in (None, "neutral")


def build_captions(idx: VideoIndex, style: StyleDNA, draft: PlanDraft, clips: list[Clip], wclips: list[WClip], chars: dict) -> CaptionTrack:
    cs = style.captions
    track = CaptionTrack(
        enabled=draft.captions.enabled and cs.enabled and draft.captions.mode != "none",
        preset=draft.captions.preset or cs.preset, mode=draft.captions.mode, font=cs.font, weight=cs.weight,
        color=cs.color, highlight=cs.highlight, stroke=cs.stroke, size=cs.size, uppercase=cs.uppercase,
        position=cs.position, emotion_styles=cs.emotion_styles,
    )
    if not track.enabled:
        return track
    emphasis_only = draft.captions.mode == "emphasis-only"
    if emphasis_only:
        track.preset = "highlight_keyword"
    lines: list[CaptionLine] = []
    wpl = max(1, cs.words_per_line)
    for clip, wc in zip(clips, wclips):
        if wc.role in NO_CAPTION_ROLES or wc.reverse:
            continue
        for s in idx.sentences:
            if s.t1 <= wc.src_in or s.t0 >= wc.src_out:
                continue
            color = chars.get(s.character or "", {}).get("color") if cs.color_by_character else None
            inner = s.text.startswith("(") or s.text.startswith("*")
            ws = []
            for w in s.words:
                if not (wc.src_in - 0.05 <= w.t0 < wc.src_out) or (style.pacing.remove_fillers and w.filler):
                    continue
                t0 = clip.start + (max(w.t0, wc.src_in) - wc.src_in) / wc.speed
                t1 = clip.start + (min(w.t1, wc.src_out) - wc.src_in) / wc.speed
                emph = _is_emphasis(w, s.emotion)
                emoji = EMOJI_FOR.get(s.emotion or "") if (cs.emoji and emph) else None
                ws.append(CaptionWord(t0=round(t0, 3), t1=round(max(t1, t0 + 0.08), 3), text=w.text, emphasis=emph, emoji=emoji))
            if not ws:
                continue
            if emphasis_only:
                for w in ws:
                    if w.emphasis:
                        lines.append(CaptionLine(t0=w.t0, t1=w.t0 + 0.9, words=[w], speaker=s.character, color=color, emotion=s.emotion))
                continue
            cur: list[CaptionWord] = []
            for w in ws:
                if cur and (len(cur) >= wpl or w.t0 - cur[-1].t1 > 0.7):
                    lines.append(CaptionLine(t0=cur[0].t0, t1=cur[-1].t1, words=cur, speaker=s.character, color=color, emotion=s.emotion, inner_voice=inner))
                    cur = []
                cur.append(w)
                if w.text[-1:] in ".?!。？！" and len(cur) >= max(2, wpl // 2):
                    lines.append(CaptionLine(t0=cur[0].t0, t1=cur[-1].t1, words=cur, speaker=s.character, color=color, emotion=s.emotion, inner_voice=inner))
                    cur = []
            if cur:
                lines.append(CaptionLine(t0=cur[0].t0, t1=cur[-1].t1, words=cur, speaker=s.character, color=color, emotion=s.emotion, inner_voice=inner))
    lines.sort(key=lambda l: l.t0)
    for a, b in zip(lines, lines[1:]):
        a.t1 = round(min(b.t0, a.t1 + 0.35), 3)
    if lines:
        lines[-1].t1 = round(lines[-1].t1 + 0.35, 3)
    track.lines = lines
    return track


# ---------------------------------------------------------------- step 5: audio helpers


def music_file(mood: str, assets: Path) -> Path | None:
    d = assets / "music"
    if not d.exists():
        return None
    exts = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
    sub = d / mood
    files = [p for p in sub.rglob("*") if p.suffix.lower() in exts] if sub.exists() else []
    if not files:
        files = [p for p in d.rglob("*") if p.suffix.lower() in exts and mood in p.stem.lower()]
    return sorted(files)[0] if files else None


def _pct_db(pct: float) -> float:
    """Volume percent -> dB (100% = 0 dB, 50% = -6 dB)."""
    import math

    return round(20 * math.log10(max(pct, 1.0) / 100.0), 2)


AUDIO_FX = {"echo", "reverb", "muffled", "radio", "phone", "pitch_up", "pitch_down", "slow_audio", "tape_stop", "bass_boost", "stereo_pan"}


# ---------------------------------------------------------------- main


def compile_plan(
    draft: PlanDraft,
    idx: VideoIndex,
    style: StyleDNA,
    outputs: list[OutputSpec],
    *,
    assets: Path = ASSETS,
    cache: Path | None = None,
) -> EditPlan:
    cache = cache or (assets / "cache")
    D = idx.source.duration
    lang = i18n.resolve(style.text_language, idx.language)
    chars = {c.id: {"name": draft.character_names.get(c.id) or c.name or i18n.t("character", lang, n=i + 1), "color": c.color}
             for i, c in enumerate(idx.characters)}

    # sanitize clips
    wclips: list[WClip] = []
    for i, dc in enumerate(draft.clips):
        a, b = max(0.0, min(dc.src_in, D)), max(0.0, min(dc.src_out, D))
        if dc.freeze is not None:
            wclips.append(WClip(dc.freeze, dc.freeze, i, freeze=dc.freeze, hold_len=max(0.3, b - a), role=dc.role))
            continue
        if b - a < 0.1:
            continue
        wclips.append(WClip(a, b, i, speed=max(0.1, min(dc.speed, 16)), reverse=dc.reverse, role=dc.role, reframe=dc.reframe))

    effects, sfx, transitions = expand(draft, style)
    effects = apply_time_effects(wclips, effects, sfx, idx.genre)

    # whole-video grading switches and per-clip framing overrides
    grade: dict[str, bool] = {}
    if style.color.auto_color and idx.genre not in ("anime", "cartoon3d"):
        grade["auto_color"] = True
    for e in list(effects):
        if e.id in ("auto_color", "match_color", "sharpen", "upscale"):
            grade[e.id] = True
            effects.remove(e)
        elif e.id in ("fit_blur", "fit_pad", "stacked_title"):
            c = _resolve(wclips, e.orig, e.target, e.at)
            if c:
                c.reframe = "fit-blur" if e.id == "fit_blur" else "fit-pad"
            if e.id == "stacked_title" and draft.title:
                effects.append(IEffect("title_reveal", e.at, max(2.0, e.dur), {"text": draft.title}, orig=e.orig, target=e.target))
            effects.remove(e)

    # color_pop needs ffmpeg at prep
    for e in list(effects):
        if e.id == "color_pop":
            c = _resolve(wclips, e.orig, e.target, e.at)
            if c:
                col = e.params.get("color", "#FF0000").lstrip("#")
                c.filters.append(f"colorhold=color=0x{col}:similarity=0.25:blend=0.1")
            effects.remove(e)

    # ---- timeline
    clips: list[Clip] = []
    t = 0.0
    for k, wc in enumerate(wclips):
        clips.append(Clip(
            id=f"c{k}", file=f"clips/c{k}.mp4", start=round(t, 3), duration=round(wc.out_dur, 3),
            src_in=wc.src_in, src_out=wc.src_out, speed=wc.speed, reverse=wc.reverse, freeze=wc.freeze, role=wc.role,
            interp=wc.interp, filters=list(wc.filters),
        ))
        t += wc.out_dur
    total = round(t, 3)

    def timeline(wc: WClip, src_t: float) -> float:
        cl = clips[wclips.index(wc)]
        if wc.freeze is not None:
            return cl.start
        src_t = min(max(src_t, wc.src_in), wc.src_out)
        rel = (wc.src_out - src_t) / wc.speed if wc.reverse else (src_t - wc.src_in) / wc.speed
        return cl.start + rel

    out_effects: list[Effect] = []

    # ---- transitions
    for tr in transitions:
        if tr.id == "cut" or tr.id not in EFFECTS:
            continue
        a_list = [w for w in wclips if w.orig == tr.after_clip]
        if not a_list:
            continue
        a = a_list[-1]
        ai = wclips.index(a)
        if ai + 1 >= len(wclips):
            continue
        b = wclips[ai + 1]
        cut = clips[ai + 1].start
        d = max(0.15, min(tr.dur or EFFECTS[tr.id].dur, clips[ai].duration * 0.9, clips[ai + 1].duration * 0.9))
        cat = EFFECTS[tr.id].category
        tid = tr.id
        if cat == "overlap":
            avail_a = (D - a.src_out) / a.speed if a.freeze is None and not a.reverse else (99 if a.freeze is not None else a.src_in / a.speed)
            avail_b = b.src_in / b.speed if b.freeze is None and not b.reverse else (99 if b.freeze is not None else (D - b.src_out) / b.speed)
            if min(avail_a, avail_b) < d / 2:
                tid, cat = "fade_black", "tx"
            else:
                clips[ai].handle_post = max(clips[ai].handle_post, round(d / 2, 3))
                clips[ai + 1].handle_pre = max(clips[ai + 1].handle_pre, round(d / 2, 3))
        if cat == "edit":
            continue
        out_effects.append(Effect(id=tid, category=cat, start=round(cut - d / 2, 3), end=round(cut + d / 2, 3),
                                  params={**EFFECTS[tid].params, **tr.params}, clip=clips[ai + 1].id))
        if style.audio.sfx and EFFECTS[tid].sfx:
            sfx.append(ISfx(EFFECTS[tid].sfx, b.src_in, target=b))

    # ---- regular effects
    audio_fx: list[AudioClipFx] = []
    volume: list[VolumeEvent] = []
    for e in effects:
        if e.id not in EFFECTS:
            continue
        wc = _resolve(wclips, e.orig, e.target, e.at)
        if wc is None:
            continue
        cl = clips[wclips.index(wc)]
        start = timeline(wc, e.at)
        cat = EFFECTS[e.id].category
        if cat == "audio":
            if e.id in AUDIO_FX:
                audio_fx.append(AudioClipFx(id=e.id, clip=cl.id, params=e.params))
            elif e.id == "music_drop":
                for tgt in ("music", "bgm"):
                    volume.append(VolumeEvent(target=tgt, start=round(start, 3), end=round(start + e.dur, 3), gain=0.08))
            elif e.id == "silence_beat":
                volume.append(VolumeEvent(target="all", start=round(start, 3), end=round(start + e.dur, 3), gain=0.0))
            elif e.id == "music_swell":
                volume.append(VolumeEvent(target="music", start=round(start, 3), end=round(start + e.dur, 3), gain=1.6))
            elif e.id == "stinger":
                sfx.append(ISfx("stinger_drama", e.at, target=wc))
            continue
        if cat == "edit":
            continue
        dur = e.dur if e.dur > 0 else cl.duration
        end = min(total, start + dur)
        if end - start < 0.05:
            continue
        params = {**EFFECTS[e.id].params, **e.params}
        if cat in ("tx", "overlap"):
            # used as a standalone accent (e.g. inside a combo): center it on the moment
            start, end = max(0.0, start - dur / 2), min(total, start + dur / 2)
            cat = "tx"
        out_effects.append(Effect(id=e.id, category=cat, start=round(start, 3), end=round(end, 3), params=params,
                                  clip=cl.id, reason=e.reason))

    # ---- global effects from style
    ex = style.extras
    if ex.progress_bar:
        out_effects.append(Effect(id="progress_bar", category="layout", start=0, end=total, params={"color": style.captions.highlight}))
    if ex.episode_badge:
        m_ep = re.fullmatch(r"Tập\s*(\d+)", ex.episode_badge.strip())
        badge = i18n.t("episode", lang, n=m_ep.group(1)) if m_ep else ex.episode_badge
        out_effects.append(Effect(id="episode_badge", category="layout", start=0, end=total, params={"text": badge}))
    if ex.watermark:
        out_effects.append(Effect(id="watermark", category="layout", start=0, end=total, params={"text": ex.watermark}))
    default_names = {i18n.t("character", lang, n=i + 1) for i in range(len(idx.characters))}
    if ex.character_cards and chars:
        seen: set[str] = set()
        for cl, wc in zip(clips, wclips):
            if wc.role != "main":
                continue
            who = speaking_character(idx, wc)
            if who and who not in seen and chars.get(who, {}).get("name") and chars[who]["name"] not in default_names:
                seen.add(who)
                out_effects.append(Effect(id="lower_third", category="text", start=cl.start + 0.2, end=min(total, cl.start + 2.8),
                                          params={"text": chars[who]["name"], "subtitle": "", "color": chars[who]["color"]}, clip=cl.id))

    # added on-screen text follows the chosen language (defaults from the catalog get translated)
    for e in out_effects:
        if e.category != "text":
            continue
        txt = e.params.get("text")
        key = i18n.DEFAULT_TEXT_KEYS.get(txt or "") if txt else i18n.EFFECT_TEXT_KEY.get(e.id)
        if key:
            e.params["text"] = i18n.t(key, lang)

    out_effects.sort(key=lambda e: e.start)

    # ---- reframe + faces per clip
    for cl, wc in zip(clips, wclips):
        for out in outputs:
            cl.reframe[out.id] = decide_reframe(idx, style, wc, out)
        faces = []
        if idx.faces:
            tt = wc.src_in if wc.freeze is None else wc.freeze
            end = wc.src_out if wc.freeze is None else wc.freeze
            while tt <= end + 1e-6:
                boxes = idx.faces_at(tt)
                if boxes:
                    if wc.freeze is not None:
                        rel = 0.0
                    elif wc.reverse:
                        rel = (wc.src_out - tt) / wc.speed
                    else:
                        rel = (tt - wc.src_in) / wc.speed
                    faces.append({"t": round(rel, 3), "boxes": [b.model_dump() for b in boxes]})
                if wc.freeze is not None:
                    break
                tt += 0.5
        cl.faces = faces

    # ---- captions
    captions = build_captions(idx, style, draft, clips, wclips, chars)

    # ---- audio
    au = style.audio
    stems = idx.stems
    audio = AudioPlan(
        voice_source="vocals" if stems.get("vocals") else "original",
        bgm_source=stems.get("no_vocals") if (stems.get("no_vocals") and au.keep_original_bgm) else None,
        denoise=au.denoise, voice_enhance=au.voice_enhance, duck_db=au.duck_db, loudness_lufs=au.loudness_lufs,
        clip_fx=audio_fx, volume=volume, bgm_gain_db=_pct_db(au.bgm_volume),
    )
    for m in draft.music:
        f = music_file(m.mood, assets)
        if f is None:
            continue
        a = clips[max(0, min(m.from_clip, len(clips) - 1))].start if clips else 0
        last = clips[m.to_clip if m.to_clip >= 0 else -1] if clips else None
        b = last.start + last.duration if last else total
        audio.music.append(MusicCue(file=str(f), start=round(a, 3), end=round(b, 3), gain_db=m.gain_db + _pct_db(au.music_volume), mood=m.mood))
        if audio.bgm_source:
            audio.volume.append(VolumeEvent(target="bgm", start=a, end=b, gain=0.3))
    if au.sfx_volume <= 0:
        sfx = []
    for s in sfx:
        wc = _resolve(wclips, s.orig, s.target, s.at)
        if wc is None:
            continue
        f = sfx_file(s.id, assets, cache / "sfx")
        if f is None:
            continue
        audio.sfx.append(SfxCue(id=s.id, file=str(f), start=round(timeline(wc, s.at), 3), gain_db=s.gain_db - 3.0 + _pct_db(au.sfx_volume)))
    # de-duplicate SFX that land on top of each other
    audio.sfx.sort(key=lambda s: s.start)
    dedup: list[SfxCue] = []
    for s in audio.sfx:
        if dedup and s.id == dedup[-1].id and s.start - dedup[-1].start < 0.6:
            continue
        if len([d for d in dedup if s.start - d.start < 0.25]) >= 2:
            continue
        dedup.append(s)
    audio.sfx = dedup

    hs = idx.hardsub
    return EditPlan(
        source=idx.source.path,
        source_size=(idx.source.width, idx.source.height),
        source_fps=idx.source.fps,
        duration=total,
        outputs=outputs,
        safe_zones={o.id: safe_zone(o) for o in outputs},
        clips=clips,
        effects=out_effects,
        captions=captions,
        audio=audio,
        lut=draft.lut,
        lut_intensity=draft.lut_intensity,
        grade=grade,
        hardsub={"x": hs.x, "y": hs.y, "w": hs.w, "h": hs.h} if hs.present else None,
        characters=chars,
        genre=idx.genre,
        text_language=lang,
        style_name=style.name,
        notes=draft.notes,
        draft=draft,
    )


def summarize(plan: EditPlan) -> str:
    cats: dict[str, int] = {}
    for e in plan.effects:
        cats[e.category] = cats.get(e.category, 0) + 1
    lines = [
        f"Thời lượng: {plan.duration:.1f}s, {len(plan.clips)} đoạn cắt, khung: {', '.join(f'{o.id} {o.width}x{o.height}' for o in plan.outputs)}",
        "Hiệu ứng: " + (", ".join(f"{k}={v}" for k, v in sorted(cats.items())) or "không có"),
        f"Phụ đề: {'tắt' if not plan.captions.enabled else plan.captions.preset + ' / ' + plan.captions.mode} ({len(plan.captions.lines)} dòng)",
        f"Âm thanh: {len(plan.audio.sfx)} tiếng động, {len(plan.audio.music)} đoạn nhạc, giọng từ {plan.audio.voice_source}",
    ]
    return "\n".join(lines)


