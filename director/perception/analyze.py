"""Perception orchestrator: source video -> VideoIndex (cached in the job folder)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..utils.log import log
from . import audio as A
from . import scenes as S
from . import semantics as M
from . import speech as SP
from .probe import probe_source
from .schema import VideoIndex
from .vision import analyze_vision

INDEX_VERSION = 3


def source_key(path: str | Path) -> str:
    p = Path(path).resolve()
    st = p.stat()
    h = hashlib.sha1(f"{p}|{st.st_size}|{int(st.st_mtime)}|v{INDEX_VERSION}".encode()).hexdigest()
    return h[:12]


def analyze(
    video: str | Path,
    workdir: str | Path,
    *,
    genre_hint: str | None = None,
    whisper_model: str | None = None,
    language: str | None = None,
    separate: bool = True,
    force: bool = False,
) -> VideoIndex:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    cache = workdir / "index.json"
    key = source_key(video)
    if cache.exists() and not force:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("_key") == key:
            log("Dùng lại kết quả phân tích đã lưu.")
            data.pop("_key", None)
            return VideoIndex.model_validate(data)

    log(f"Phân tích video: {video}")
    src = probe_source(video)
    log(f"  {src.width}x{src.height}, {src.fps:.2f} fps, {src.duration:.1f}s, âm thanh: {'có' if src.has_audio else 'không'}")
    idx = VideoIndex(source=src)

    # ---- audio
    rms = None
    if src.has_audio:
        wav = A.extract_wav(video, workdir / "audio16k.wav")
        idx.audio, rms, _ = A.analyze_audio(wav)
        idx.audio.lufs = A.measure_lufs(video)
        log(f"  Âm thanh: {len(idx.audio.silences)} khoảng lặng, tempo {idx.audio.tempo}, {len(idx.audio.loud_events)} điểm bùng nổ")

    # ---- scenes
    idx.scenes = S.detect_scenes(video, src.duration, threshold=0.3)
    log(f"  {len(idx.scenes)} cảnh")

    # ---- vision
    vis = analyze_vision(video, src.duration, idx.scenes, genre_hint=genre_hint, thumb_dir=workdir / "characters")
    idx.genre = vis["genre"]
    idx.genre_confidence = vis["genre_confidence"]
    idx.faces = vis["faces"]
    idx.characters = vis["characters"]
    idx.hardsub = vis["hardsub"]
    if idx.genre == "anime":
        # drawn animation has held frames; re-run scene detection with a slightly lower threshold
        idx.scenes = S.detect_scenes(video, src.duration, threshold=0.25)

    # ---- speech
    asr_wav = workdir / "audio16k.wav" if src.has_audio else None
    if src.has_audio and separate:
        stereo = workdir / "audio44k.wav"
        if not stereo.exists():
            A.extract_wav(video, stereo, sr=44100, mono=False)
        idx.stems = SP.separate_stems(stereo, workdir)
        if idx.stems.get("vocals"):
            asr_wav = A.extract_wav(idx.stems["vocals"], workdir / "vocals16k.wav")
    if asr_wav:
        idx.sentences, idx.language = SP.transcribe(asr_wav, whisper_model, language)
    if idx.hardsub.present:
        lines = SP.ocr_subtitles(video, idx.hardsub, src.duration)
        idx.hardsub.lines = lines
        if lines and not idx.sentences:
            idx.sentences = SP.sentences_from_ocr(lines)
            idx.notes.append("Lời thoại lấy từ phụ đề có sẵn trên hình (OCR).")
        elif lines:
            n = SP.merge_ocr_text(idx.sentences, lines)
            if n:
                idx.notes.append(f"Đã sửa {n} câu theo phụ đề có sẵn trên hình.")
    if rms is not None and idx.sentences:
        A.word_emphasis(rms, 0.01, idx.words(), idx.sentences)
    if idx.sentences:
        n = SP.mark_retakes(idx.sentences)
        if n:
            log(f"  Phát hiện {n} câu nói lại (giữ lần nói sau).")
        if asr_wav:
            SP.diarize(asr_wav, idx.sentences)

    # ---- semantics
    M.assign_emotions(idx)
    M.assign_characters(idx)
    idx.highlights = M.find_highlights(idx)
    idx.story = M.rough_story(idx)

    # ---- keyframes for the LLM / critic
    times = S.keyframe_times(idx.scenes, src.duration)
    idx.keyframes = S.extract_frames(video, times, workdir / "keyframes")

    data = idx.model_dump()
    data["_key"] = key
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log("Phân tích xong.")
    return idx
