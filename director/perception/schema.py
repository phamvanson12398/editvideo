"""Video Index: everything Perception learns about a source video."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool = True
    rotation: int = 0


class Word(BaseModel):
    t0: float
    t1: float
    text: str
    emphasis: float = 0.0  # 0..1, loudness relative to its sentence
    filler: bool = False


class Sentence(BaseModel):
    id: str
    t0: float
    t1: float
    text: str
    words: list[Word] = Field(default_factory=list)
    speaker: Optional[str] = None  # speaker id from diarization ("S0"...)
    character: Optional[str] = None  # character id ("C0"...) when known
    energy: float = 0.0  # 0..1
    emotion: Optional[str] = None  # shock|anger|sad|happy|comedy|romance|fear|neutral
    retake_of: Optional[str] = None  # id of the sentence this one repeats (keep the later one)
    source: str = "asr"  # asr | ocr


class Scene(BaseModel):
    t0: float
    t1: float
    quality: float = 1.0
    motion: float = 0.0


class FaceBox(BaseModel):
    x: float  # normalized 0..1 (left)
    y: float  # normalized 0..1 (top)
    w: float
    h: float
    character: Optional[str] = None
    score: float = 1.0


class FaceSample(BaseModel):
    t: float
    boxes: list[FaceBox] = Field(default_factory=list)


class Character(BaseModel):
    id: str
    name: Optional[str] = None
    color: Optional[str] = None  # caption color
    appearances: int = 0
    feature: list[float] = Field(default_factory=list)  # appearance embedding
    thumbnail: Optional[str] = None


class TextRegion(BaseModel):
    """Burned-in text (subtitles etc.) already on the picture."""

    present: bool = False
    x: float = 0.0
    y: float = 0.8
    w: float = 1.0
    h: float = 0.15
    coverage: float = 0.0  # fraction of sampled frames containing text in this region
    lines: list[dict] = Field(default_factory=list)  # OCR lines: {t0, t1, text}


class AudioInfo(BaseModel):
    silences: list[tuple[float, float]] = Field(default_factory=list)
    energy: list[float] = Field(default_factory=list)  # RMS per energy_hop seconds, 0..1
    energy_hop: float = 0.1
    beats: list[float] = Field(default_factory=list)
    tempo: Optional[float] = None
    loud_events: list[float] = Field(default_factory=list)  # sudden loudness jumps
    lufs: Optional[float] = None


class Highlight(BaseModel):
    t0: float
    t1: float
    score: float
    reason: str = ""


class StoryBeat(BaseModel):
    t0: float
    t1: float
    type: str  # setup|conflict|climax|twist|resolution|cliffhanger|comedy|romance
    intensity: float = 0.5
    summary: str = ""


class VideoIndex(BaseModel):
    source: SourceInfo
    genre: str = "unknown"  # anime | cartoon3d | live | gameplay | unknown
    genre_confidence: float = 0.0
    language: Optional[str] = None
    sentences: list[Sentence] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    faces: list[FaceSample] = Field(default_factory=list)
    face_fps: float = 2.0
    characters: list[Character] = Field(default_factory=list)
    hardsub: TextRegion = Field(default_factory=TextRegion)
    audio: AudioInfo = Field(default_factory=AudioInfo)
    highlights: list[Highlight] = Field(default_factory=list)
    story: list[StoryBeat] = Field(default_factory=list)
    story_summary: str = ""
    keyframes: list[dict] = Field(default_factory=list)  # {t, path}
    stems: dict[str, str] = Field(default_factory=dict)  # vocals / no_vocals wav paths
    series_id: Optional[str] = None
    notes: list[str] = Field(default_factory=list)

    def energy_at(self, t: float) -> float:
        e = self.audio.energy
        if not e:
            return 0.0
        i = int(t / self.audio.energy_hop)
        return e[max(0, min(len(e) - 1, i))]

    def faces_at(self, t: float) -> list[FaceBox]:
        if not self.faces:
            return []
        i = int(round(t * self.face_fps))
        i = max(0, min(len(self.faces) - 1, i))
        return self.faces[i].boxes

    def words(self) -> list[Word]:
        return [w for s in self.sentences for w in s.words]
