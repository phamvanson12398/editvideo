"""Audio analysis with numpy only: silences, energy, onsets, beats, loud events, loudness."""

from __future__ import annotations

import re
import wave
from pathlib import Path

import numpy as np

from ..utils.ffmpeg import run, run_stderr
from .schema import AudioInfo

SR = 16000


def extract_wav(src: str | Path, dst: str | Path, sr: int = SR, mono: bool = True) -> Path:
    dst = Path(dst)
    args = ["-i", str(src), "-vn", "-ac", "1" if mono else "2", "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)]
    run(args)
    return dst


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        ch = wf.getnchannels()
        data = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, sr


def rms_frames(x: np.ndarray, sr: int, hop_s: float = 0.01, win_s: float = 0.03) -> np.ndarray:
    hop = max(1, int(sr * hop_s))
    win = max(hop, int(sr * win_s))
    if len(x) < win:
        return np.zeros(1, dtype=np.float32)
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx]
    return np.sqrt((frames ** 2).mean(axis=1) + 1e-12)


def detect_silences(rms: np.ndarray, hop_s: float, min_len: float = 0.25) -> list[tuple[float, float]]:
    db = 20 * np.log10(rms + 1e-9)
    if len(db) == 0:
        return []
    # adaptive threshold: relative to speech level (90th percentile)
    ref = np.percentile(db, 90)
    floor = np.percentile(db, 10)
    thr = max(floor + 6.0, ref - 28.0, -55.0)
    quiet = db < thr
    out: list[tuple[float, float]] = []
    start = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * hop_s >= min_len:
                out.append((round(start * hop_s, 3), round(i * hop_s, 3)))
            start = None
    if start is not None and (len(quiet) - start) * hop_s >= min_len:
        out.append((round(start * hop_s, 3), round(len(quiet) * hop_s, 3)))
    return out


def onset_envelope(x: np.ndarray, sr: int, hop_s: float = 0.01) -> np.ndarray:
    hop = int(sr * hop_s)
    n_fft = 1024
    if len(x) < n_fft:
        return np.zeros(1, dtype=np.float32)
    n = 1 + (len(x) - n_fft) // hop
    window = np.hanning(n_fft).astype(np.float32)
    env = np.zeros(n, dtype=np.float32)
    prev = None
    chunk = 2048  # frames per batch to bound memory
    for c0 in range(0, n, chunk):
        c1 = min(n, c0 + chunk)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(c0, c1)[:, None]
        spec = np.abs(np.fft.rfft(x[idx] * window, axis=1))
        spec = np.log1p(spec * 10)
        if prev is not None:
            spec_full = np.vstack([prev[None, :], spec])
        else:
            spec_full = np.vstack([spec[:1], spec])
        flux = np.maximum(0, np.diff(spec_full, axis=0)).sum(axis=1)
        env[c0:c1] = flux
        prev = spec[-1]
    env -= env.mean()
    env = np.maximum(env, 0)
    if env.max() > 0:
        env /= env.max()
    return env


def estimate_beats(env: np.ndarray, hop_s: float) -> tuple[float | None, list[float]]:
    if len(env) < int(4 / hop_s):
        return None, []
    # tempo by autocorrelation in 60..180 BPM
    e = env - env.mean()
    max_lag = int(60 / 60 / hop_s)
    min_lag = int(60 / 180 / hop_s)
    seg = e[: min(len(e), int(120 / hop_s))]
    ac = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
    if len(ac) <= max_lag:
        return None, []
    lags = np.arange(min_lag, max_lag + 1)
    best = lags[np.argmax(ac[min_lag:max_lag + 1])]
    if ac[best] <= 0.1 * ac[0]:
        return None, []
    period = best
    tempo = 60.0 / (period * hop_s)
    # phase: offset with max summed energy
    phases = [env[p::period].sum() for p in range(period)]
    phase = int(np.argmax(phases))
    beats = []
    i = phase
    while i < len(env):
        lo, hi = max(0, i - 3), min(len(env), i + 4)
        j = lo + int(np.argmax(env[lo:hi]))
        beats.append(round(j * hop_s, 3))
        i += period
    return round(float(tempo), 1), beats


def loud_events(rms: np.ndarray, hop_s: float) -> list[float]:
    """Moments where loudness jumps sharply after a quieter stretch (shouts, impacts)."""
    db = 20 * np.log10(rms + 1e-9)
    if len(db) < 50:
        return []
    k = int(0.5 / hop_s)
    out = []
    last = -10.0
    ref = np.percentile(db, 75)
    for i in range(k, len(db)):
        before = db[i - k:i].mean()
        now = db[i]
        t = i * hop_s
        if now > ref + 3 and now - before > 12 and t - last > 2.0:
            out.append(round(t, 2))
            last = t
    return out


def measure_lufs(src: str | Path) -> float | None:
    try:
        err = run_stderr(["-i", str(src), "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    except Exception:
        return None
    m = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", err)
    return float(m[-1]) if m else None


def analyze_audio(wav: str | Path, energy_hop: float = 0.1) -> tuple[AudioInfo, np.ndarray, int]:
    x, sr = read_wav(wav)
    hop_s = 0.01
    rms = rms_frames(x, sr, hop_s)
    silences = detect_silences(rms, hop_s)
    step = int(energy_hop / hop_s)
    energy = [float(rms[i:i + step].mean()) for i in range(0, len(rms), step)]
    mx = max(energy) if energy else 1.0
    energy = [round(e / mx, 4) if mx > 0 else 0.0 for e in energy]
    env = onset_envelope(x, sr, hop_s)
    tempo, beats = estimate_beats(env, hop_s)
    info = AudioInfo(
        silences=silences,
        energy=energy,
        energy_hop=energy_hop,
        beats=beats,
        tempo=tempo,
        loud_events=loud_events(rms, hop_s),
    )
    return info, rms, sr


def word_emphasis(rms: np.ndarray, hop_s: float, words: list, sentences: list) -> None:
    """Fill Word.emphasis (0..1) = loudness of the word relative to its sentence."""
    db = 20 * np.log10(rms + 1e-9)

    def level(t0: float, t1: float) -> float:
        a, b = int(t0 / hop_s), max(int(t0 / hop_s) + 1, int(t1 / hop_s))
        seg = db[a:b]
        return float(seg.max()) if len(seg) else -90.0

    for s in sentences:
        if not s.words:
            continue
        levels = [level(w.t0, w.t1) for w in s.words]
        mean = float(np.mean(levels))
        std = float(np.std(levels)) or 1.0
        for w, lv in zip(s.words, levels):
            z = (lv - mean) / std
            w.emphasis = round(float(np.clip((z + 0.5) / 2.5, 0, 1)), 3)
        s.energy = float(max(levels))
    # rank-normalize sentence loudness so "energy" means "louder than most lines in this video"
    voiced = [s for s in sentences if s.words]
    if voiced:
        order = sorted(voiced, key=lambda s: s.energy)
        for rank, s in enumerate(order):
            s.energy = round(rank / max(1, len(order) - 1), 3) if len(order) > 1 else 0.5
