"""Plan schemas.

Two levels:
- PlanDraft: what a planner (rule-based or LLM) decides, anchored to SOURCE time.
  Easy to write and to revise.
- EditPlan: the compiled, timeline-based plan consumed by the renderer (Remotion + ffmpeg).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Outputs (frames)
# ---------------------------------------------------------------------------


class OutputSpec(BaseModel):
    id: str
    aspect: str  # "9:16", "16:9", "2.39:1", "source"...
    width: int
    height: int
    fps: float = 30.0
    platform: Optional[str] = None  # tiktok | youtube | shorts | reels | instagram | facebook | None
    letterbox: bool = False  # for "cinematic" delivered inside 16:9


# ---------------------------------------------------------------------------
# Draft (source-time)
# ---------------------------------------------------------------------------


class DraftClip(BaseModel):
    src_in: float
    src_out: float
    speed: float = 1.0
    reverse: bool = False
    freeze: Optional[float] = None  # hold this source time for (src_out - src_in) seconds
    role: str = "main"  # main | hook | replay | broll
    reframe: Optional[str] = None  # override reframe mode for this clip
    note: str = ""


class DraftEffect(BaseModel):
    id: str  # effect id or combo id ("combo.shock")
    clip: int  # index into clips
    at: float  # SOURCE time inside the clip
    dur: float = 1.0  # duration in output seconds
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class DraftTransition(BaseModel):
    after_clip: int
    id: str = "cut"
    dur: float = 0.4
    params: dict[str, Any] = Field(default_factory=dict)


class DraftSfx(BaseModel):
    id: str
    clip: int
    at: float  # SOURCE time
    gain_db: float = 0.0


class DraftMusic(BaseModel):
    mood: str
    from_clip: int = 0
    to_clip: int = -1  # inclusive, -1 = last
    gain_db: float = -6.0


class DraftCaptions(BaseModel):
    enabled: bool = True
    preset: Optional[str] = None
    mode: str = "full"  # full | emphasis-only | none


class PlanDraft(BaseModel):
    clips: list[DraftClip]
    effects: list[DraftEffect] = Field(default_factory=list)
    transitions: list[DraftTransition] = Field(default_factory=list)
    sfx: list[DraftSfx] = Field(default_factory=list)
    music: list[DraftMusic] = Field(default_factory=list)
    captions: DraftCaptions = Field(default_factory=DraftCaptions)
    title: Optional[str] = None
    lut: Optional[str] = None
    lut_intensity: float = 0.7
    character_names: dict[str, str] = Field(default_factory=dict)
    notes: str = ""


# ---------------------------------------------------------------------------
# Compiled EditPlan (timeline-time)
# ---------------------------------------------------------------------------


class ReframeKey(BaseModel):
    t: float  # seconds relative to clip start (output time)
    cx: float  # crop center x in source-normalized coords
    cy: float
    zoom: float = 1.0  # 1 = largest crop of the target aspect that fits the source


class ClipReframe(BaseModel):
    mode: str = "center"  # center | follow | fit-blur | fit-pad | letterbox | split
    keys: list[ReframeKey] = Field(default_factory=list)
    split_keys: list[list[ReframeKey]] = Field(default_factory=list)  # for split: one track per panel


class Clip(BaseModel):
    id: str
    file: str  # prepared clip file (relative to render public dir)
    start: float  # timeline seconds
    duration: float
    src_in: float
    src_out: float
    speed: float = 1.0
    reverse: bool = False
    freeze: Optional[float] = None
    handle_pre: float = 0.0  # extra seconds available before start (for overlap transitions)
    handle_post: float = 0.0
    role: str = "main"
    interp: bool = False  # motion-interpolated slow motion at prep
    filters: list[str] = Field(default_factory=list)  # extra ffmpeg video filters at prep
    reframe: dict[str, ClipReframe] = Field(default_factory=dict)  # output id -> reframe
    faces: list[dict] = Field(default_factory=list)  # [{t (clip-relative), boxes:[{x,y,w,h,character}]}]


class Effect(BaseModel):
    id: str
    category: str
    start: float
    end: float
    params: dict[str, Any] = Field(default_factory=dict)
    clip: Optional[str] = None
    reason: str = ""


class CaptionWord(BaseModel):
    t0: float
    t1: float
    text: str
    emphasis: bool = False
    emoji: Optional[str] = None


class CaptionLine(BaseModel):
    t0: float
    t1: float
    words: list[CaptionWord]
    speaker: Optional[str] = None
    color: Optional[str] = None
    emotion: Optional[str] = None
    inner_voice: bool = False


class CaptionTrack(BaseModel):
    enabled: bool = True
    preset: str = "word_pop"
    mode: str = "full"
    font: str = "Be Vietnam Pro"
    weight: int = 800
    color: str = "#FFFFFF"
    highlight: str = "#FFD400"
    stroke: str = "#000000"
    size: float = 1.0
    uppercase: bool = False
    position: str = "auto"
    emotion_styles: bool = False
    lines: list[CaptionLine] = Field(default_factory=list)


class AudioClipFx(BaseModel):
    id: str
    clip: str
    params: dict[str, Any] = Field(default_factory=dict)


class MusicCue(BaseModel):
    file: str
    start: float
    end: float
    gain_db: float = -6.0
    fade_in: float = 1.0
    fade_out: float = 1.5
    mood: str = ""


class SfxCue(BaseModel):
    id: str
    file: str
    start: float
    gain_db: float = 0.0


class VolumeEvent(BaseModel):
    """Timeline volume automation: target = 'all' | 'music' | 'voice'."""

    target: str
    start: float
    end: float
    gain: float  # linear multiplier


class AudioPlan(BaseModel):
    voice_source: str = "original"  # original | vocals (separated stem)
    bgm_source: Optional[str] = None  # no_vocals stem when separated
    bgm_gain_db: float = 0.0
    denoise: bool = True
    voice_enhance: bool = True
    duck_db: float = -14.0
    loudness_lufs: float = -14.0
    clip_fx: list[AudioClipFx] = Field(default_factory=list)
    music: list[MusicCue] = Field(default_factory=list)
    sfx: list[SfxCue] = Field(default_factory=list)
    volume: list[VolumeEvent] = Field(default_factory=list)


class SafeZone(BaseModel):
    top: float = 0.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0


class EditPlan(BaseModel):
    version: int = 1
    source: str
    source_size: tuple[int, int]
    source_fps: float
    duration: float
    outputs: list[OutputSpec]
    safe_zones: dict[str, SafeZone] = Field(default_factory=dict)
    clips: list[Clip]
    effects: list[Effect] = Field(default_factory=list)
    captions: CaptionTrack = Field(default_factory=CaptionTrack)
    audio: AudioPlan = Field(default_factory=AudioPlan)
    lut: Optional[str] = None
    lut_intensity: float = 0.7
    hardsub: Optional[dict] = None  # {x,y,w,h} normalized source coords of burned-in text
    characters: dict[str, dict] = Field(default_factory=dict)  # id -> {name, color}
    genre: str = "unknown"
    style_name: str = ""
    notes: str = ""
    draft: Optional[PlanDraft] = None
