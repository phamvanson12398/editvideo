"""Procedurally synthesized sound effects (no licensing issues).

Users can override any id by dropping a file named <id>.wav/.mp3 into assets/sfx/ (or a sub-folder).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
_rng = np.random.default_rng(7)


def _t(d: float) -> np.ndarray:
    return np.arange(int(SR * d)) / SR


def _env(n: int, a: float = 0.005, r: float = 0.2, d_total: float | None = None) -> np.ndarray:
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-4), 0, 1)
    dec = np.exp(-t / max(r, 1e-4))
    return att * dec


def _noise(d: float) -> np.ndarray:
    return _rng.standard_normal(int(SR * d)).astype(np.float32)


def _lowpass(x: np.ndarray, cutoff: float | np.ndarray) -> np.ndarray:
    """One-pole low-pass; cutoff may vary per sample."""
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=np.float32), x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def _bandpass(x: np.ndarray, lo: float | np.ndarray, hi: float | np.ndarray) -> np.ndarray:
    return _lowpass(x, hi) - _lowpass(x, lo)


def _sine(f: float | np.ndarray, d: float, phase: float = 0.0) -> np.ndarray:
    f = np.broadcast_to(np.asarray(f, dtype=np.float64), (int(SR * d),))
    return np.sin(2 * np.pi * np.cumsum(f) / SR + phase).astype(np.float32)


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return (x / m * peak).astype(np.float32)


def _pad(x: np.ndarray, d: float) -> np.ndarray:
    n = int(SR * d)
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros(n - len(x), np.float32)])


def _mix(*parts: tuple[float, np.ndarray]) -> np.ndarray:
    n = max(int(o * SR) + len(p) for o, p in parts)
    out = np.zeros(n, np.float32)
    for o, p in parts:
        s = int(o * SR)
        out[s:s + len(p)] += p
    return out


# ---------------------------------------------------------------- generators

def whoosh(d=0.6, f0=300, f1=4000, peak_at=0.6):
    t = _t(d)
    sweep = f0 + (f1 - f0) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    x = _bandpass(_noise(d), sweep * 0.5, sweep)
    env = np.sin(np.pi * np.clip(t / d, 0, 1) ** (np.log(0.5) / np.log(peak_at))) ** 2
    return _norm(x * env, 0.8)


def boom(d=1.4, f=55):
    t = _t(d)
    body = _sine(f * (1 + 1.5 * np.exp(-t * 20)), d) * np.exp(-t * 3.2)
    click = _lowpass(_noise(0.05), 2500) * np.exp(-_t(0.05) * 60)
    return _norm(_mix((0, body), (0, click * 0.6)))


def punch(d=0.35):
    t = _t(d)
    body = _sine(90 * (1 + 2 * np.exp(-t * 40)), d) * np.exp(-t * 14)
    snap = _bandpass(_noise(d), 800, 5000) * np.exp(-t * 45)
    return _norm(body + 0.7 * snap)


def slap(d=0.3):
    t = _t(d)
    x = _bandpass(_noise(d), 1200, 9000) * np.exp(-t * 38)
    body = _sine(220, d) * np.exp(-t * 30) * 0.4
    return _norm(x + body)


def flash_hit(d=0.6):
    t = _t(d)
    x = _bandpass(_noise(d), 3000, 12000) * np.exp(-t * 10)
    return _norm(x * 0.7 + boom(d, 70)[: len(x)] * 0.5)


def riser(d=2.0):
    t = _t(d)
    f = 200 * (8 ** (t / d))
    tone = (_sine(f, d) + 0.5 * _sine(f * 1.5, d)) * (t / d) ** 2
    noise = _bandpass(_noise(d), f * 0.5, f * 2) * (t / d) ** 2
    return _norm(tone * 0.5 + noise)


def downer(d=1.5):
    return _norm(riser(d)[::-1])


def tick(d=0.08):
    t = _t(d)
    return _norm(_sine(2800, d) * np.exp(-t * 120) + _bandpass(_noise(d), 2000, 8000) * np.exp(-t * 200) * 0.5)


def click(d=0.05):
    return _norm(_bandpass(_noise(d), 1500, 7000) * np.exp(-_t(d) * 250))


def pop(d=0.18):
    t = _t(d)
    return _norm(_sine(600 * (1 + 2 * np.exp(-t * 60)), d) * np.exp(-t * 30))


def ding(d=1.2, f=1320):
    t = _t(d)
    x = sum(a * _sine(f * k, d) for k, a in [(1, 1.0), (2.76, 0.4), (5.4, 0.2)]) * np.exp(-t * 3.5)
    return _norm(x, 0.7)


def chime(d=1.8):
    return _norm(_mix((0, ding(d, 1046)), (0.12, ding(d, 1318) * 0.8), (0.24, ding(d, 1568) * 0.7)), 0.7)


def notification(d=0.6):
    return _norm(_mix((0, ding(0.4, 880) * 0.8), (0.12, ding(0.5, 1320))), 0.7)


def sparkle(d=1.2):
    parts = []
    for i in range(10):
        f = float(_rng.uniform(2500, 6000))
        parts.append((i * 0.08, ding(0.4, f) * float(_rng.uniform(0.3, 0.7))))
    return _norm(_mix(*parts), 0.6)


def boing(d=0.7):
    t = _t(d)
    f = 180 + 120 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 4) + 200 * np.exp(-t * 6)
    return _norm(_sine(f, d) * np.exp(-t * 4))


def glitch(d=0.45):
    n = int(SR * d)
    out = np.zeros(n, np.float32)
    pos = 0
    while pos < n:
        ln = int(_rng.uniform(0.01, 0.05) * SR)
        kind = _rng.integers(0, 3)
        if kind == 0:
            chunk = np.sign(_sine(float(_rng.uniform(200, 2000)), ln / SR))
        elif kind == 1:
            chunk = _noise(ln / SR)
        else:
            chunk = np.zeros(ln, np.float32)
        chunk = _pad(chunk.astype(np.float32), ln / SR)
        m = max(0, min(len(chunk), n - pos))
        out[pos:pos + m] = chunk[:m]
        pos += ln
    return _norm(out, 0.6)


def glass_break(d=1.2):
    t = _t(d)
    shards = _mix(*[(float(_rng.uniform(0, 0.4)), ding(0.5, float(_rng.uniform(3000, 9000))) * 0.5) for _ in range(25)])
    crash = _bandpass(_noise(d), 2000, 12000) * np.exp(-t * 6)
    return _norm(_mix((0, crash), (0, _pad(shards, d))))


def thunder(d=2.5):
    t = _t(d)
    rumble = _lowpass(_noise(d), 180) * (np.exp(-t * 1.2)) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))
    crack = _bandpass(_noise(0.3), 1000, 8000) * np.exp(-_t(0.3) * 15)
    return _norm(_mix((0, rumble * 3), (0, crack)))


def heartbeat(d=1.6, bpm=70):
    beat = 60 / bpm
    def thump(f=50, dd=0.2):
        tt = _t(dd)
        return _sine(f, dd) * np.exp(-tt * 25)
    parts = []
    t = 0.0
    while t < d - 0.3:
        parts += [(t, thump()), (t + 0.18, thump(45) * 0.7)]
        t += beat
    return _norm(_pad(_mix(*parts), d))


def dun_dun_dun(d=2.4):
    def hit(f, dd):
        tt = _t(dd)
        tone = sum(a * np.sign(_sine(f * k, dd)) for k, a in [(1, 1.0), (2, 0.4), (3, 0.25)])
        return _lowpass(tone, 1200) * np.exp(-tt * 1.8) * np.clip(tt / 0.01, 0, 1)
    return _norm(_mix((0, hit(110, 0.45)), (0.5, hit(104, 0.45)), (1.0, hit(98, 1.4))))


def stinger(d=2.0, chord=(220, 277, 330), dark=False):
    t = _t(d)
    x = sum(_sine(f, d) + 0.3 * np.sign(_sine(f * 2, d)) for f in chord) * np.exp(-t * 1.6)
    hit = boom(d, 50) * 0.8
    return _norm(_lowpass(x, 2500 if not dark else 900) + hit[: len(x)])


def villain_hit(d=2.0):
    return stinger(d, (98, 116.5, 138.6), dark=True)


def tape_stop(d=1.0):
    t = _t(d)
    f = 400 * (1 - t / d) ** 2 + 20
    return _norm(np.sign(_sine(f, d)) * _lowpass(np.ones(len(t), np.float32), 1) * (1 - t / d))


def rewind_tape(d=1.2):
    t = _t(d)
    f = 1500 + 900 * np.sin(2 * np.pi * 7 * t)
    x = _bandpass(_noise(d), f * 0.7, f * 1.3) + 0.3 * _sine(f, d)
    return _norm(x * np.sin(np.pi * t / d))


def record_scratch(d=0.6):
    t = _t(d)
    f = 500 + 1500 * np.abs(np.sin(2 * np.pi * 3 * t))
    return _norm(_bandpass(_noise(d), f * 0.5, f) * np.exp(-t * 3))


def crow(d=0.9):
    parts = []
    for k in range(2):
        dd = 0.32
        tt = _t(dd)
        f = 650 + 200 * np.exp(-tt * 8)
        tone = np.sign(_sine(f, dd)) * 0.5 + _bandpass(_noise(dd), 600, 2400)
        parts.append((k * 0.42, _bandpass(tone, 500, 2500) * np.sin(np.pi * tt / dd)))
    return _norm(_mix(*parts))


def crickets(d=2.0):
    parts = []
    t0 = 0.0
    while t0 < d - 0.3:
        for k in range(3):
            dd = 0.04
            tt = _t(dd)
            parts.append((t0 + k * 0.06, _sine(4300, dd) * np.sin(np.pi * tt / dd) * 0.6))
        t0 += 0.5
    return _norm(_pad(_mix(*parts), d), 0.5)


def trombone_sad(d=2.2):
    notes = [(0.0, 311, 0.45), (0.5, 294, 0.45), (1.0, 277, 0.45), (1.5, 262, 0.7)]
    parts = []
    for o, f, dd in notes:
        tt = _t(dd)
        vib = f * (1 + 0.01 * np.sin(2 * np.pi * 5 * tt) * (o > 1.4))
        tone = _lowpass(np.sign(_sine(vib, dd)), 1400)
        parts.append((o, tone * np.clip(tt / 0.03, 0, 1) * np.exp(-tt * 1.0)))
    return _norm(_mix(*parts), 0.7)


def swish(d=0.4):
    return whoosh(d, 1500, 7000, 0.4)


def aura(d=2.0):
    t = _t(d)
    x = _lowpass(_noise(d), 400) * 2 + 0.3 * _sine(80 + 10 * np.sin(2 * np.pi * 2 * t), d)
    return _norm(x * np.sin(np.pi * t / d))


def shing(d=1.0):
    t = _t(d)
    return _norm(_bandpass(_noise(d), 4000, 12000) * np.exp(-t * 3) + ding(d, 2400)[: len(t)] * 0.5)


def alarm(d=1.6):
    t = _t(d)
    f = np.where((t * 2.5) % 1 < 0.5, 960, 720)
    return _norm(np.sign(_sine(f, d)) * 0.4, 0.5)


def wind(d=3.0):
    t = _t(d)
    f = 500 + 300 * np.sin(2 * np.pi * 0.3 * t)
    return _norm(_bandpass(_noise(d), f * 0.5, f) * np.sin(np.pi * t / d), 0.6)


def page_flip(d=0.5):
    t = _t(d)
    return _norm(_bandpass(_noise(d), 1000, 6000) * np.sin(np.pi * t / d) ** 3)


def camera_shutter(d=0.25):
    return _norm(_mix((0, click(0.05)), (0.09, click(0.05) * 0.8)))


def typing(d=1.5):
    parts = [(float(i * 0.11 + _rng.uniform(0, 0.03)), click(0.04) * float(_rng.uniform(0.5, 1))) for i in range(int(d / 0.11))]
    return _norm(_pad(_mix(*parts), d), 0.6)


def applause(d=2.5):
    parts = [(float(_rng.uniform(0, d - 0.05)), _bandpass(_noise(0.02), 800, 6000) * float(_rng.uniform(0.2, 1))) for _ in range(int(d * 120))]
    return _norm(_pad(_mix(*parts), d) * np.sin(np.pi * _t(d) / d) ** 0.5, 0.6)


def teleport(d=0.6):
    t = _t(d)
    return _norm(_sine(300 + 3000 * (t / d) ** 2, d) * np.sin(np.pi * t / d) * 0.6 + whoosh(d, 2000, 8000)[: len(t)] * 0.4)


def door_slam(d=0.8):
    return _norm(_mix((0, boom(d, 75) * 0.8), (0, punch(0.3) * 0.6)))


SYNTHS = {
    "whoosh_fast": lambda: whoosh(0.35, 400, 5000, 0.5),
    "whoosh_heavy": lambda: whoosh(0.7, 150, 2500, 0.6),
    "whoosh_slow": lambda: whoosh(1.2, 200, 3000, 0.6),
    "swoosh": lambda: whoosh(0.5, 600, 6000, 0.45),
    "swish": swish,
    "riser": riser,
    "downer": downer,
    "reverse_cymbal": lambda: _norm(_bandpass(_noise(2.0), 4000, 14000) * (_t(2.0) / 2.0) ** 3),
    "impact_boom": boom,
    "impact_punch": punch,
    "hit_flash": flash_hit,
    "slap": slap,
    "glass_break": glass_break,
    "door_slam": door_slam,
    "thunder": thunder,
    "dun_dun_dun": dun_dun_dun,
    "heartbeat": heartbeat,
    "heartbeat_fast": lambda: heartbeat(1.6, 130),
    "tick": tick,
    "clock_tick": lambda: _norm(_pad(_mix(*[(i * 0.5, tick()) for i in range(6)]), 3.0)),
    "wind": wind,
    "record_scratch": record_scratch,
    "boing": boing,
    "crow": crow,
    "crickets": crickets,
    "trombone_sad": trombone_sad,
    "pop": pop,
    "ding": ding,
    "click": click,
    "ting": lambda: ding(0.8, 2093),
    "notification": notification,
    "typing": typing,
    "camera_shutter": camera_shutter,
    "applause": applause,
    "chime": chime,
    "sparkle": sparkle,
    "shing": shing,
    "aura": aura,
    "teleport": teleport,
    "glitch": glitch,
    "page_flip": page_flip,
    "rewind_tape": rewind_tape,
    "tape_stop": tape_stop,
    "alarm": alarm,
    "stinger_drama": lambda: stinger(2.0, (220, 261.6, 329.6)),
    "stinger_suspense": lambda: stinger(2.4, (233, 277, 349), dark=True),
    "stinger_epic": lambda: stinger(2.0, (196, 247, 294, 392)),
    "villain_hit": villain_hit,
}

SFX_PACKS = {
    "drama": ["dun_dun_dun", "impact_boom", "heartbeat", "heartbeat_fast", "clock_tick", "wind", "record_scratch", "stinger_drama"],
    "transition": ["whoosh_fast", "whoosh_heavy", "whoosh_slow", "swoosh", "riser", "downer", "reverse_cymbal"],
    "impact": ["impact_punch", "impact_boom", "slap", "glass_break", "door_slam", "thunder"],
    "comedy": ["boing", "crow", "crickets", "trombone_sad", "pop", "ding"],
    "ui": ["click", "pop", "ting", "ding", "notification", "typing", "camera_shutter"],
    "emotion": ["applause", "heartbeat", "chime"],
    "anime": ["sparkle", "swish", "shing", "aura", "teleport"],
}


def write_wav(path: Path, x: np.ndarray) -> None:
    x = np.clip(x, -1, 1)
    stereo = np.repeat((x * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


def find_user_sfx(sfx_id: str, assets: Path) -> Path | None:
    d = assets / "sfx"
    if not d.exists():
        return None
    for ext in (".wav", ".mp3", ".ogg", ".flac", ".m4a"):
        hits = list(d.rglob(f"{sfx_id}{ext}"))
        if hits:
            return hits[0]
    return None


def sfx_file(sfx_id: str, assets: Path, cache: Path) -> Path | None:
    user = find_user_sfx(sfx_id, assets)
    if user:
        return user
    gen = SYNTHS.get(sfx_id)
    if gen is None:
        return None
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{sfx_id}.wav"
    if not out.exists():
        write_wav(out, gen())
    return out
