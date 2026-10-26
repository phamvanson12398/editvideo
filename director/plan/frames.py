"""Turn frame requests ("tiktok", "4:5", "1080x1350", "điện ảnh"...) into OutputSpecs."""

from __future__ import annotations

import re
import unicodedata

from .schema import OutputSpec, SafeZone

# keyword -> (aspect, width, height, platform)
_KEYWORDS: list[tuple[tuple[str, ...], tuple[str, int, int, str | None]]] = [
    (("tiktok", "tik tok"), ("9:16", 1080, 1920, "tiktok")),
    (("reels", "reel"), ("9:16", 1080, 1920, "reels")),
    (("shorts", "short", "youtube short"), ("9:16", 1080, 1920, "shorts")),
    (("doc", "dọc", "vertical", "story", "stories"), ("9:16", 1080, 1920, None)),
    (("instagram feed", "khung instagram", "insta feed", "ig feed", "bai dang instagram", "instagram"), ("4:5", 1080, 1350, "instagram")),
    (("vuong", "vuông", "square", "facebook feed", "fb feed"), ("1:1", 1080, 1080, "facebook")),
    (("cinematic", "dien anh", "điện ảnh", "phim rap", "scope"), ("2.39:1", 1920, 804, None)),
    (("ultrawide", "21:9"), ("21:9", 2560, 1080, None)),
    (("youtube", "ngang", "horizontal", "landscape"), ("16:9", 1920, 1080, "youtube")),
]

_MAX_LONG_SIDE = 1920


def _strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _even(x: float) -> int:
    v = int(round(x))
    return v if v % 2 == 0 else v + 1


def size_for_aspect(aw: float, ah: float, long_side: int = _MAX_LONG_SIDE) -> tuple[int, int]:
    if aw >= ah:
        return _even(long_side), _even(long_side * ah / aw)
    return _even(long_side * aw / ah), _even(long_side)


def parse_frame(req: str, source_w: int, source_h: int) -> OutputSpec:
    raw = req.strip()
    low = raw.lower()
    plain = _strip_accents(low)
    four_k = "4k" in plain
    uid = re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "out"

    if plain in ("source", "goc", "khung goc", "original", "giu nguyen"):
        w, h = _even(source_w), _even(source_h)
        return OutputSpec(id="source", aspect="source", width=w, height=h)

    m = re.search(r"(\d{3,4})\s*[x×*]\s*(\d{3,4})", plain)
    if m:
        w, h = _even(int(m.group(1))), _even(int(m.group(2)))
        return OutputSpec(id=f"{w}x{h}", aspect=f"{w}:{h}", width=w, height=h)

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)", plain)
    if m:
        aw, ah = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        if aw > 0 and ah > 0:
            short = 2160 if four_k else 1080
            if aw >= ah:
                w, h = _even(short * aw / ah), _even(short)
            else:
                w, h = _even(short), _even(short * ah / aw)
            limit = 3840 if four_k else 2560
            if max(w, h) > limit:
                w, h = size_for_aspect(aw, ah, limit)
            aspect = f"{m.group(1)}:{m.group(2)}"
            platform = "tiktok" if aspect == "9:16" else ("youtube" if aspect == "16:9" else None)
            return OutputSpec(id=aspect.replace(":", "x").replace(".", "_"), aspect=aspect, width=w, height=h, platform=platform)

    m = re.search(r"(\d{3,4})p", plain)
    if m:
        lines = int(m.group(1))
        vertical = any(k in plain for k in ("doc", "vertical"))
        if vertical:
            w, h = _even(lines), _even(lines * 16 / 9)
        else:
            w, h = _even(lines * 16 / 9), _even(lines)
        return OutputSpec(id=f"{w}x{h}", aspect=f"{w}:{h}", width=w, height=h)

    for keys, (aspect, w, h, platform) in _KEYWORDS:
        if any(_strip_accents(k) in plain for k in keys):
            if four_k:
                w, h = w * 2, h * 2
            if aspect == "2.39:1" and "16:9" in plain:
                return OutputSpec(id="cinematic", aspect="16:9", width=1920, height=1080, letterbox=True)
            return OutputSpec(id=platform or uid, aspect=aspect, width=w, height=h, platform=platform)

    raise ValueError(f"Không hiểu yêu cầu khung hình: {req!r}")


def parse_frames(reqs: list[str] | None, source_w: int, source_h: int) -> list[OutputSpec]:
    if not reqs:
        return [parse_frame("source", source_w, source_h)]
    out: list[OutputSpec] = []
    seen: set[str] = set()
    for r in reqs:
        spec = parse_frame(r, source_w, source_h)
        dup = next((o for o in out if (o.width, o.height, o.letterbox) == (spec.width, spec.height, spec.letterbox)), None)
        if dup is not None:
            if spec.platform and not dup.platform:
                dup.platform, dup.id = spec.platform, spec.id if spec.id not in seen else dup.id
                seen.add(dup.id)
            continue
        base, i = spec.id, 2
        while spec.id in seen:
            spec.id = f"{base}-{i}"
            i += 1
        seen.add(spec.id)
        out.append(spec)
    return out


def frames_from_text(text: str) -> list[str]:
    """Pull frame requests out of a free-form Vietnamese/English command."""
    plain = _strip_accents(text.lower())
    found: list[str] = []
    for m in re.finditer(r"\d{3,4}\s*[x×]\s*\d{3,4}", plain):
        found.append(m.group(0))
    for m in re.finditer(r"(?<![\d.:])(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)(?![\d:])", plain):
        a, b = m.group(1), m.group(2)
        # skip timestamps such as 0:40 or 1:05
        if b.startswith("0") and len(b) > 1:
            continue
        if 0 < float(a) <= 21 and 0 < float(b) <= 21 and 0.3 <= float(a) / float(b) <= 3.5:
            found.append(f"{a}:{b}")
    low = text.lower()
    for keys, _ in _KEYWORDS:
        for k in keys:
            has_diacritics = _strip_accents(k) != k
            hay, needle = (low, k) if has_diacritics else (plain, k)
            if not has_diacritics and len(k) <= 3:
                continue
            if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay):
                found.append(k)
                break
    # de-duplicate while keeping order and dropping keywords subsumed by an explicit ratio
    uniq: list[str] = []
    for f in found:
        if f not in uniq:
            uniq.append(f)
    return uniq


# Platform UI safe zones (fractions of the frame that UI overlays cover).
_SAFE = {
    "tiktok": SafeZone(top=0.10, bottom=0.20, left=0.04, right=0.14),
    "reels": SafeZone(top=0.10, bottom=0.22, left=0.04, right=0.12),
    "shorts": SafeZone(top=0.08, bottom=0.18, left=0.04, right=0.12),
    "instagram": SafeZone(top=0.04, bottom=0.06, left=0.04, right=0.04),
    "facebook": SafeZone(top=0.04, bottom=0.06, left=0.04, right=0.04),
    "youtube": SafeZone(top=0.05, bottom=0.10, left=0.04, right=0.04),
}


def safe_zone(spec: OutputSpec) -> SafeZone:
    if spec.platform in _SAFE:
        return _SAFE[spec.platform]
    if spec.height > spec.width * 1.4:
        return _SAFE["tiktok"]
    return SafeZone(top=0.05, bottom=0.08, left=0.05, right=0.05)
