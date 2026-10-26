"""Speech: ASR (faster-whisper), OCR of burned-in subtitles (rapidocr), stem separation (demucs),
diarization (pyannote). Every heavy dependency is optional; missing ones degrade gracefully."""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..utils.locks import gpu_lock
from ..utils.log import log, warn
from .schema import Sentence, TextRegion, Word

FILLERS = {
    "vi": {"ừm", "ừ", "ờ", "à", "ơ", "ạ", "hử", "ưm", "ừmm", "ờm", "kiểu", "kiểu là", "thì là", "nói chung là"},
    "en": {"um", "uh", "erm", "hmm", "like", "you know"},
    "ja": {"えー", "あの", "えっと", "まあ"},
    "ko": {"음", "어", "그", "저기"},
    "zh": {"嗯", "呃", "那个", "就是"},
}
_ALL_FILLERS = set().union(*FILLERS.values())


def _norm(w: str) -> str:
    return re.sub(r"[^\w\s]", "", w.lower()).strip()


_DLL_DIRS_ADDED = False


def _add_cuda_dll_dirs() -> None:
    """Windows: CUDA DLLs installed by pip (nvidia-cublas-cu12, nvidia-cudnn-cu12, torch) live inside
    site-packages and are not on PATH, so CTranslate2 cannot find cublas64_12.dll. Register them."""
    global _DLL_DIRS_ADDED
    if _DLL_DIRS_ADDED or sys.platform != "win32":
        return
    _DLL_DIRS_ADDED = True
    import site

    roots = [Path(p) for p in site.getsitepackages()]
    try:
        roots.append(Path(site.getusersitepackages()))
    except Exception:
        pass
    dirs = []
    for r in roots:
        dirs += [d for d in (r / "nvidia").glob("*/bin") if d.is_dir()]
        dirs += [d for d in (r / "torch" / "lib",) if d.is_dir()]
    for env in ("CUDA_PATH", "CUDA_PATH_V12_6", "CUDA_PATH_V12_4"):
        if os.environ.get(env):
            dirs.append(Path(os.environ[env]) / "bin")
    for d in dirs:
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
            except OSError:
                pass
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def _cuda_libs_ok() -> bool:
    if sys.platform != "win32":
        return True
    import ctypes

    for name in ("cublas64_12.dll", "cudnn_ops64_9.dll"):
        try:
            ctypes.WinDLL(name)
        except OSError:
            return False
    return True


def gpu_available() -> bool:
    if os.environ.get("DIRECTOR_WHISPER_DEVICE", "").lower() == "cpu":
        return False
    _add_cuda_dll_dirs()
    try:
        import ctranslate2  # type: ignore

        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False
    if not _cuda_libs_ok():
        warn("Có GPU NVIDIA nhưng thiếu thư viện CUDA 12 (cublas64_12.dll / cuDNN 9) nên Whisper chạy bằng CPU. "
             "Muốn chạy bằng GPU: chạy 5_CAI_THEM_GPU.bat (hoặc pip install nvidia-cublas-cu12 nvidia-cudnn-cu12).")
        return False
    return True


# ---------------------------------------------------------------- ASR


def _run_whisper(WhisperModel, wav, size: str, device: str, compute: str, language: str | None):
    log(f"Chép lời bằng Whisper '{size}' trên {device} ({compute})...")
    try:
        model = WhisperModel(size, device=device, compute_type=compute)
    except ValueError as e:  # unsupported compute type on this device
        warn(f"Không tải được Whisper với {compute} ({e}); thử lại với float32.")
        model = WhisperModel(size, device=device, compute_type="float32")
    segments = info = None
    if device == "cuda":
        # batched inference is several times faster on GPU
        try:
            from faster_whisper import BatchedInferencePipeline  # type: ignore

            batched = BatchedInferencePipeline(model=model)
            segments, info = batched.transcribe(str(wav), language=language, word_timestamps=True,
                                                batch_size=int(os.environ.get("DIRECTOR_WHISPER_BATCH", "8")))
        except (ImportError, TypeError):
            segments = None
    if segments is None:
        segments, info = model.transcribe(
            str(wav),
            language=language,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            beam_size=5 if device == "cuda" else 1,
        )
    sentences: list[Sentence] = []
    for i, seg in enumerate(segments):  # decoding happens lazily here
        words = []
        for w in seg.words or []:
            txt = w.word.strip()
            if not txt:
                continue
            words.append(Word(t0=round(w.start, 3), t1=round(w.end, 3), text=txt, filler=_norm(txt) in _ALL_FILLERS))
        text = seg.text.strip()
        if not text:
            continue
        sentences.append(Sentence(id=f"s{i}", t0=round(seg.start, 3), t1=round(seg.end, 3), text=text, words=words))
    return sentences, getattr(info, "language", None)


def transcribe(wav: str | Path, model_size: str | None = None, language: str | None = None) -> tuple[list[Sentence], str | None]:
    _add_cuda_dll_dirs()
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        warn("Chưa cài faster-whisper nên không chép được lời. Cài: pip install 'director-video[asr]'")
        return [], None

    gpu = gpu_available()
    size = model_size or os.environ.get("DIRECTOR_WHISPER_MODEL") or ("large-v3-turbo" if gpu else "small")
    # Pascal GPUs (GTX 10xx) have slow FP16: int8 is the fast, accurate choice there.
    compute = os.environ.get("DIRECTOR_WHISPER_COMPUTE") or ("int8_float32" if gpu else "int8")
    try:
        if gpu:
            with gpu_lock("Whisper"):
                sentences, lang = _run_whisper(WhisperModel, wav, size, "cuda", compute, language)
        else:
            sentences, lang = _run_whisper(WhisperModel, wav, size, "cpu", compute, language)
    except RuntimeError as e:
        if not gpu:
            raise
        # Missing/incompatible CUDA libraries show up only when decoding starts: fall back to CPU.
        warn(f"Whisper trên GPU lỗi ({e}). Chuyển sang CPU (chậm hơn). "
             "Sửa: chạy 5_CAI_THEM_GPU.bat hoặc pip install nvidia-cublas-cu12 nvidia-cudnn-cu12.")
        cpu_size = model_size or os.environ.get("DIRECTOR_WHISPER_MODEL") or "small"
        sentences, lang = _run_whisper(WhisperModel, wav, cpu_size, "cpu", "int8", language)
    log(f"Chép được {len(sentences)} câu (ngôn ngữ: {lang}).")
    return _split_long(sentences), lang


def _split_long(sentences: list[Sentence], max_len: float = 7.0) -> list[Sentence]:
    """Split long ASR segments at punctuation / pauses so editing has finer units."""
    out: list[Sentence] = []
    for s in sentences:
        if s.t1 - s.t0 <= max_len or len(s.words) < 4:
            out.append(s)
            continue
        cur: list[Word] = []
        for i, w in enumerate(s.words):
            cur.append(w)
            nxt = s.words[i + 1] if i + 1 < len(s.words) else None
            gap = (nxt.t0 - w.t1) if nxt else 0
            punct = w.text[-1:] in ".?!,;:。？！，"
            if nxt is None or (cur[-1].t1 - cur[0].t0 > 2.0 and (punct or gap > 0.35)) or cur[-1].t1 - cur[0].t0 > max_len:
                out.append(Sentence(
                    id=f"{s.id}_{len(out)}", t0=cur[0].t0, t1=cur[-1].t1,
                    text=" ".join(x.text for x in cur), words=cur, source=s.source,
                ))
                cur = []
    for i, s in enumerate(out):
        s.id = f"s{i}"
    return out


# ---------------------------------------------------------------- retakes


def mark_retakes(sentences: list[Sentence], thr: float = 0.72) -> int:
    """If a sentence is (nearly) repeated by one of the next two sentences, mark the earlier as a retake."""
    n = 0
    for i, s in enumerate(sentences):
        a = _norm(s.text)
        if len(a) < 8:
            continue
        for j in (i + 1, i + 2):
            if j >= len(sentences):
                break
            b = _norm(sentences[j].text)
            if not b or sentences[j].t0 - s.t1 > 8:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            prefix = b.startswith(a[: max(6, len(a) // 2)])
            if ratio >= thr or (prefix and len(b) >= len(a) * 0.8):
                s.retake_of = sentences[j].id
                n += 1
                break
    return n


# ---------------------------------------------------------------- OCR of burned-in subtitles


def ocr_subtitles(src: str | Path, region: TextRegion, duration: float, every: float = 0.5) -> list[dict]:
    """Read burned-in subtitle lines over time. Returns [{t0, t1, text}]."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except ImportError:
        return []
    import cv2

    from .vision import iter_frames

    import numpy as np

    engine = RapidOCR()
    log("Đọc phụ đề có sẵn trên hình (OCR)...")
    lines: list[dict] = []
    last_sig = None
    for t, frame in iter_frames(src, 1.0 / every, 960):
        H, W = frame.shape[:2]
        y0 = max(0, int((region.y - 0.03) * H))
        y1 = min(H, int((region.y + region.h + 0.03) * H))
        crop = frame[y0:y1]
        if crop.size == 0:
            continue
        sig = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (96, 12)).astype(np.float32)
        if last_sig is not None and float(np.abs(sig - last_sig).mean()) < 2.5:
            if lines and lines[-1]["t1"] >= t - every * 1.01:
                lines[-1]["t1"] = round(t + every, 3)
            continue  # subtitle unchanged: skip the expensive OCR call
        last_sig = sig
        result, _ = engine(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        text = " ".join(r[1] for r in (result or []) if r[2] > 0.6).strip()
        if lines and text and difflib.SequenceMatcher(None, lines[-1]["text"], text).ratio() > 0.8:
            lines[-1]["t1"] = round(t + every, 3)
        elif text:
            lines.append({"t0": round(t, 3), "t1": round(t + every, 3), "text": text})
    log(f"OCR đọc được {len(lines)} dòng phụ đề.")
    return lines


def sentences_from_ocr(lines: list[dict]) -> list[Sentence]:
    out = []
    for i, ln in enumerate(lines):
        toks = ln["text"].split()
        if not toks:
            continue
        # CJK lines have no spaces: one token per character group
        if len(toks) == 1 and len(toks[0]) > 4:
            toks = list(toks[0])
        dur = (ln["t1"] - ln["t0"]) / len(toks)
        words = [Word(t0=round(ln["t0"] + k * dur, 3), t1=round(ln["t0"] + (k + 1) * dur, 3), text=tok) for k, tok in enumerate(toks)]
        out.append(Sentence(id=f"s{i}", t0=ln["t0"], t1=ln["t1"], text=ln["text"], words=words, source="ocr"))
    return out


def merge_ocr_text(sentences: list[Sentence], lines: list[dict]) -> int:
    """Prefer exact on-screen text when ASR and OCR overlap in time (subtitles are authored text)."""
    n = 0
    for s in sentences:
        best, best_ov = None, 0.0
        for ln in lines:
            ov = min(s.t1, ln["t1"]) - max(s.t0, ln["t0"])
            if ov > best_ov:
                best, best_ov = ln, ov
        if best and best_ov > 0.5 * (s.t1 - s.t0):
            # never replace accented ASR text with OCR output that lost its diacritics
            if any(ord(c) > 127 for c in s.text) and all(ord(c) < 128 for c in best["text"]):
                continue
            ratio = difflib.SequenceMatcher(None, _norm(s.text), _norm(best["text"])).ratio()
            if 0.45 < ratio < 0.98 and len(s.words) == len(best["text"].split()):
                for w, tok in zip(s.words, best["text"].split()):
                    w.text = tok
                s.text = best["text"]
                n += 1
    return n


# ---------------------------------------------------------------- stems


def separation_gpu_ok() -> bool:
    if os.environ.get("DIRECTOR_DEMUCS_CPU"):
        return True
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def separate_stems(wav_stereo: str | Path, out_dir: str | Path) -> dict[str, str]:
    """Split dialogue from music/SFX with Demucs (two stems). Returns {} if unavailable."""
    out_dir = Path(out_dir)
    vocals = out_dir / "vocals.wav"
    rest = out_dir / "no_vocals.wav"
    if vocals.exists() and rest.exists():
        return {"vocals": str(vocals), "no_vocals": str(rest)}
    try:
        import demucs  # type: ignore  # noqa: F401
    except ImportError:
        return {}
    log("Tách thoại khỏi nhạc nền bằng Demucs (có thể mất vài phút)...")
    tmp = out_dir / "demucs"
    cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "--segment", "7", "-o", str(tmp), str(wav_stereo)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    with gpu_lock("Demucs"):
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        warn(f"Demucs lỗi, bỏ qua tách nhạc: {proc.stderr[-500:]}")
        return {}
    found_v = list(tmp.rglob("vocals.wav"))
    found_r = list(tmp.rglob("no_vocals.wav"))
    if not found_v or not found_r:
        return {}
    shutil.move(str(found_v[0]), vocals)
    shutil.move(str(found_r[0]), rest)
    shutil.rmtree(tmp, ignore_errors=True)
    return {"vocals": str(vocals), "no_vocals": str(rest)}


# ---------------------------------------------------------------- diarization


def diarize(wav: str | Path, sentences: list[Sentence]) -> int:
    """Assign speaker ids with pyannote (needs HF_TOKEN). Returns number of speakers found."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token or not sentences:
        return 0
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except ImportError:
        return 0
    log("Nhận diện người nói (pyannote)...")
    try:
        pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                pipe.to(torch.device("cuda"))
        except Exception:
            pass
        with gpu_lock("pyannote"):
            dia = pipe(str(wav))
    except Exception as e:
        warn(f"Diarization lỗi: {e}")
        return 0
    turns = [(seg.start, seg.end, spk) for seg, _, spk in dia.itertracks(yield_label=True)]
    speakers: dict[str, str] = {}
    for s in sentences:
        votes: dict[str, float] = {}
        for a, b, spk in turns:
            ov = min(s.t1, b) - max(s.t0, a)
            if ov > 0:
                votes[spk] = votes.get(spk, 0) + ov
        if votes:
            spk = max(votes, key=votes.get)
            speakers.setdefault(spk, f"S{len(speakers)}")
            s.speaker = speakers[spk]
    return len(speakers)
