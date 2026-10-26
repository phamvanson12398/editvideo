"""Style DNA from a reference video: "edit it like this one".

Measures pacing (shot length, pauses), cut accents (white flashes), on-screen text (captions: position,
color, line length), color grade (warmth, saturation, contrast -> closest built-in LUT) and energy
(motion + cut rate -> effect budget). With an AI model available, keyframes are also described by the model."""

from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np

from ..perception import audio as A
from ..perception.probe import probe_source
from ..perception.scenes import detect_scenes, extract_frames
from ..perception.vision import detect_text_regions, iter_frames
from ..utils.log import log, warn
from .dna import StyleDNA
from .presets import get_preset


def _color_stats(frames: list[np.ndarray]) -> dict:
    sats, contrasts, warmth, bright = [], [], [], []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
        sats.append(hsv[..., 1].mean() / 255)
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
        contrasts.append(gray.std() / 128)
        bright.append(gray.mean() / 255)
        b, g, r = [f[..., i].astype(np.float32).mean() for i in range(3)]
        warmth.append((r - b) / 255)
    return {"sat": float(np.median(sats)), "contrast": float(np.median(contrasts)),
            "warmth": float(np.median(warmth)), "bright": float(np.median(bright))}


def _pick_lut(c: dict) -> str | None:
    if c["sat"] < 0.06:
        return "bw"
    if c["warmth"] > 0.12 and c["sat"] < 0.3:
        return "sepia" if c["sat"] < 0.18 else "vintage"
    if c["bright"] < 0.32 and c["contrast"] > 0.45:
        return "moody"
    if c["sat"] > 0.55:
        return "pop"
    if c["bright"] > 0.6 and c["contrast"] < 0.35:
        return "pastel"
    if c["warmth"] > 0.07:
        return "warm"
    if c["warmth"] < -0.05:
        return "cool"
    return None


def _caption_color(frames: list[np.ndarray], region) -> str | None:
    if not region.present:
        return None
    cols = []
    for f in frames:
        H, W = f.shape[:2]
        crop = f[int(region.y * H):int((region.y + region.h) * H), int(region.x * W):int((region.x + region.w) * W)]
        if crop.size == 0:
            continue
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        mask = gray > np.percentile(gray, 92)  # text fill is usually the brightest
        if mask.sum() > 20:
            cols.append(crop[mask].mean(axis=0))
    if not cols:
        return None
    b, g, r = np.median(np.array(cols), axis=0)
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))


def _flash_count(frames: list[np.ndarray]) -> int:
    lum = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() for f in frames]
    n = 0
    for a, b, c in zip(lum, lum[1:], lum[2:]):
        if b > 200 and b - a > 60 and b - c > 40:
            n += 1
    return n


def style_from_reference(ref: str | Path, work: Path, base: StyleDNA | None = None, use_llm: bool = False) -> StyleDNA:
    ref = Path(ref)
    work.mkdir(parents=True, exist_ok=True)
    log(f"Học phong cách từ video mẫu: {ref.name}")
    src = probe_source(ref)
    D = max(0.1, src.duration)
    scenes = detect_scenes(ref, D, threshold=0.3)
    cut_rate = len(scenes) / D * 60  # cuts per minute
    avg_shot = D / max(1, len(scenes))
    frames = [f for _, f in iter_frames(ref, 4.0, 360)]
    color = _color_stats(frames[:: max(1, len(frames) // 60)])
    text = detect_text_regions(frames[:: max(1, len(frames) // 80)])
    flashes = _flash_count(frames)
    motion = float(np.mean([np.abs(a.astype(np.int16) - b.astype(np.int16)).mean() for a, b in zip(frames[:-1], frames[1:])])) if len(frames) > 1 else 0
    silence_ratio, pause = 0.0, 0.45
    if src.has_audio:
        wav = A.extract_wav(ref, work / "ref16k.wav")
        info, _, _ = A.analyze_audio(wav)
        sil = sum(b - a for a, b in info.silences)
        silence_ratio = sil / D
        pause = 0.25 if silence_ratio < 0.06 else (0.45 if silence_ratio < 0.15 else 0.8)

    style = base or get_preset("tiktok-nang-dong" if cut_rate > 25 else "anime-drama")
    intensity = "high" if (cut_rate > 30 or flashes / D * 60 > 4) else ("low" if cut_rate < 10 else "medium")
    patch: dict = {
        "name": f"mau-{ref.stem}"[:40],
        "description": f"Học từ video mẫu {ref.name}",
        "pacing": {"avg_shot_sec": round(avg_shot, 2), "remove_silence_over": pause, "keep_pause": 0.08 if pause < 0.3 else 0.12},
        "budget": {"intensity": intensity},
        "transitions": {"frequency": "medium" if flashes > 2 else "low",
                        "accent": ["flash_white"] + (["glitch_cut"] if motion > 25 else ["fade_black"])},
    }
    lut = _pick_lut(color)
    patch["color"] = {"lut": lut, "intensity": 0.6}
    if text.present:
        ypos = text.y + text.h / 2
        cap = {"enabled": True, "position": "top" if ypos < 0.35 else ("middle" if ypos < 0.62 else "auto")}
        col = _caption_color(frames[:: max(1, len(frames) // 40)], text)
        if col:
            cap["color"] = col
        cap["size"] = round(float(np.clip(text.h / 0.08, 0.8, 1.6)), 2)
        patch["captions"] = cap
    else:
        patch["captions"] = {"enabled": False}
    style = style.merged(patch)
    stats = {"cut_rate_per_min": round(cut_rate, 1), "avg_shot": round(avg_shot, 2), "flashes": flashes, "motion": round(motion, 1),
             "silence_ratio": round(silence_ratio, 3), "color": color, "text": text.model_dump(exclude={"lines"})}
    (work / "reference_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  {cut_rate:.0f} lần cắt/phút, shot trung bình {avg_shot:.1f}s, LUT gần nhất: {lut}, chữ trên hình: {'có' if text.present else 'không'}")

    if use_llm:
        try:
            from ..agent.llm import ask_json, image_block
            from ..agent.prompts import STYLE_FIELDS, SYSTEM_DIRECTOR

            kfs = extract_frames(ref, [s.t0 + 0.3 for s in scenes[:: max(1, len(scenes) // 12)]][:12], work / "ref_kf", 640)
            content: list[dict] = []
            for kf in kfs:
                content += [{"type": "text", "text": f"[t={kf['t']:.1f}s]"}, image_block(kf["path"], 640)]
            content.append({"type": "text", "text": f"""These are frames of a REFERENCE video whose editing style the user wants to copy.
Measured: {json.dumps(stats)}
Current style guess: {style.model_dump_json()}
{STYLE_FIELDS}
Describe the caption look (font weight, colors, outline, animation), title/sticker usage, effects you can see
(zooms, shakes, manga lines, emojis, color grade). Return {{"patch": {{...}}, "explain": "tiếng Việt"}}."""})
            data = ask_json(SYSTEM_DIRECTOR, content, effort="medium", max_tokens=8000)
            style = style.merged(data.get("patch") or {})
            log(f"  AI mô tả phong cách mẫu: {data.get('explain', '')}")
        except Exception as e:
            warn(f"AI không phân tích được video mẫu: {e}")
    return style


def user_styles_dir() -> Path:
    d = Path(os.environ.get("DIRECTOR_HOME") or Path.home() / ".director") / "styles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_style(style: StyleDNA, name: str) -> Path:
    p = user_styles_dir() / f"{name}.json"
    style.name = name
    p.write_text(style.model_dump_json(indent=2), encoding="utf-8")
    return p
