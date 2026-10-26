"""Rule-based semantics: emotions, speaking characters, highlights, story beats.
The LLM Director refines these when an API key is configured."""

from __future__ import annotations

import re
import unicodedata

import numpy as np

from .schema import Highlight, Sentence, StoryBeat, VideoIndex

_LEX: dict[str, list[str]] = {
    "shock": [
        "cái gì", "sao cơ", "không thể nào", "không thể", "trời ơi", "trời đất", "thật sao", "hả", "gì cơ",
        "chuyện gì", "sao lại", "là anh", "là cô", "là mày", "con ruột", "phát hiện", "bí mật", "lộ",
        "what", "no way", "impossible", "really", "how could", "oh my god", "?!",
    ],
    "anger": [
        "cút", "câm", "đồ", "khốn", "láo", "mày", "tát", "đánh", "hỗn", "dám", "im đi", "đi ra", "biến",
        "ghét", "hận", "trả thù", "shut up", "get out", "how dare", "hate",
    ],
    "sad": [
        "khóc", "xin lỗi", "đau", "mất", "chết", "chia tay", "tạm biệt", "nhớ", "cô đơn", "buồn", "tha thứ",
        "sorry", "goodbye", "miss you", "cry", "died", "lonely",
    ],
    "comedy": ["haha", "hihi", "hehe", "buồn cười", "ngố", "đồ ngốc", "lol", "funny", "trời má"],
    "romance": ["yêu", "thương", "cưới", "hôn", "anh nhớ em", "em nhớ anh", "love", "marry", "kiss", "darling"],
    "fear": ["sợ", "cứu", "ma", "chạy đi", "nguy hiểm", "help", "run", "scared", "afraid"],
    "villain": ["ha ha ha", "kế hoạch", "tiêu diệt", "phải trả giá", "you will pay", "my plan"],
}

EMOTIONS = ["shock", "anger", "sad", "comedy", "romance", "fear", "villain", "happy", "neutral"]


def _plain(s: str) -> str:
    return s.lower()


def _strip(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def sentence_emotion(s: Sentence) -> tuple[str, float]:
    text = _plain(s.text)
    ascii_only = all(ord(c) < 128 for c in text)
    scores: dict[str, float] = {}
    for emo, words in _LEX.items():
        for w in words:
            if ascii_only and _strip(w) != w and len(w) >= 5:
                w = _strip(w)  # OCR / unaccented input: match multi-syllable cues without diacritics
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text) or (not w[0].isalnum() and w in text):
                scores[emo] = scores.get(emo, 0) + 1
    excl = text.count("!")
    if excl:
        scores["shock"] = scores.get("shock", 0) + 0.5 * excl * (0.5 + s.energy)
        scores["anger"] = scores.get("anger", 0) + 0.3 * excl * s.energy
    if not scores:
        return "neutral", 0.0
    emo = max(scores, key=scores.get)
    return emo, float(min(1.0, 0.35 + 0.25 * scores[emo] + 0.3 * s.energy))


def assign_emotions(idx: VideoIndex) -> None:
    for s in idx.sentences:
        if s.emotion:
            continue
        emo, _ = sentence_emotion(s)
        s.emotion = emo


def assign_characters(idx: VideoIndex) -> None:
    """Who is on screen while a sentence is spoken; speaker ids are mapped to characters by co-occurrence."""
    if not idx.faces or not idx.characters:
        return
    co: dict[str, dict[str, int]] = {}
    for s in idx.sentences:
        votes: dict[str, float] = {}
        t = s.t0
        while t <= s.t1:
            boxes = idx.faces_at(t)
            for b in boxes:
                if b.character:
                    votes[b.character] = votes.get(b.character, 0) + b.w * b.h * (2.0 if len(boxes) == 1 else 1.0)
            t += 1.0 / idx.face_fps
        if votes:
            best = max(votes, key=votes.get)
            if s.speaker:
                co.setdefault(s.speaker, {})
                co[s.speaker][best] = co[s.speaker].get(best, 0) + 1
            else:
                s.character = best
    speaker_char = {spk: max(c, key=c.get) for spk, c in co.items() if c}
    for s in idx.sentences:
        if s.speaker and s.speaker in speaker_char:
            s.character = speaker_char[s.speaker]


def find_highlights(idx: VideoIndex, win: float = 4.0, top: int = 8) -> list[Highlight]:
    d = idx.source.duration
    if d <= 0:
        return []
    n = max(1, int(d / 1.0))
    score = np.zeros(n)
    for i in range(n):
        t0, t1 = i, min(d, i + win)
        e = [idx.energy_at(t) for t in np.arange(t0, t1, 0.25)]
        score[i] += 0.6 * (np.mean(e) if e else 0)
    weight = {"shock": 1.0, "anger": 0.9, "villain": 0.7, "sad": 0.7, "romance": 0.6, "comedy": 0.6, "fear": 0.7}
    for s in idx.sentences:
        w = weight.get(s.emotion or "", 0.0)
        for i in range(max(0, int(s.t0 - win + 1)), min(n, int(s.t1) + 1)):
            score[i] += 0.8 * w * (0.5 + s.energy)
    for t in idx.audio.loud_events:
        for i in range(max(0, int(t - win + 1)), min(n, int(t) + 1)):
            score[i] += 0.5
    picks: list[Highlight] = []
    used = np.zeros(n, bool)
    for i in np.argsort(-score):
        if len(picks) >= top or score[i] <= 0.2:
            break
        if used[max(0, i - int(win)):i + int(win)].any():
            continue
        used[i] = True
        t0, t1 = float(i), float(min(d, i + win))
        reason = []
        emos = {s.emotion for s in idx.sentences if s.t1 > t0 and s.t0 < t1 and s.emotion not in (None, "neutral")}
        if emos:
            reason.append("cảm xúc: " + ", ".join(sorted(e for e in emos if e)))
        if any(t0 <= t <= t1 for t in idx.audio.loud_events):
            reason.append("âm thanh bùng lên")
        picks.append(Highlight(t0=t0, t1=t1, score=round(float(score[i]), 3), reason="; ".join(reason)))
    return sorted(picks, key=lambda h: -h.score)


def rough_story(idx: VideoIndex) -> list[StoryBeat]:
    d = idx.source.duration
    if d <= 0:
        return []
    beats = [StoryBeat(t0=0.0, t1=round(min(d, max(5.0, d * 0.15)), 2), type="setup", intensity=0.3)]
    hl = sorted(idx.highlights, key=lambda h: h.t0)
    if hl:
        top = max(hl, key=lambda h: h.score)
        beats.append(StoryBeat(t0=top.t0, t1=top.t1, type="climax", intensity=1.0, summary=top.reason))
        for h in hl:
            if h is top:
                continue
            kind = "conflict" if h.t0 < top.t0 else "resolution"
            emos = [s.emotion for s in idx.sentences if h.t0 <= s.t0 <= h.t1]
            if "shock" in emos and h.t0 > top.t0:
                kind = "twist"
            beats.append(StoryBeat(t0=h.t0, t1=h.t1, type=kind, intensity=round(min(1.0, h.score / max(top.score, 1e-6)), 2)))
        last = hl[-1]
        if d - last.t1 < max(6.0, d * 0.12):
            beats.append(StoryBeat(t0=last.t0, t1=last.t1, type="cliffhanger", intensity=0.8))
    return sorted(beats, key=lambda b: b.t0)
