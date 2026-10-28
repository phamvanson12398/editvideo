"""Style DNA: a structured description of an editing style."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Pacing(BaseModel):
    avg_shot_sec: float = 2.5
    remove_silence_over: float = 0.45  # seconds; silences longer than this get cut
    keep_pause: float = 0.12  # padding kept around speech
    cut_on_beat: bool = False
    remove_fillers: bool = True
    remove_retakes: bool = True
    slow_down_on: list[str] = Field(default_factory=list)  # emotions that get slowed down


class Hook(BaseModel):
    enabled: bool = True
    min_sec: float = 3.0  # hook length range (seconds)
    max_sec: float = 5.0
    strategy: str = "best-moment-first"  # best-moment-first | twist-first-then-rewind | question | none


class Captions(BaseModel):
    enabled: bool = True
    preset: str = "word_pop"
    font: str = "Be Vietnam Pro"
    weight: int = 800
    color: str = "#FFFFFF"
    highlight: str = "#FFD400"
    stroke: str = "#000000"
    position: str = "auto"  # auto | top | middle | bottom
    words_per_line: int = 4
    size: float = 1.0  # scale multiplier
    color_by_character: bool = False
    emotion_styles: bool = False
    uppercase: bool = False
    emoji: bool = False
    if_hardsub: str = "none"  # none | emphasis-only | full  (video already has subtitles)


class Camera(BaseModel):
    reframe: str = "auto"  # auto | follow-face | follow-character | center | fit-blur | fit-pad | letterbox | split | speaker-switch
    punch_in_on_emphasis: bool = True
    punch_in_on: list[str] = Field(default_factory=lambda: ["shock", "anger"])
    shake_on: list[str] = Field(default_factory=lambda: ["shock"])
    zoom_range: tuple[float, float] = (1.0, 1.3)
    ken_burns_static: bool = True


class Transitions(BaseModel):
    default: str = "cut"
    accent: list[str] = Field(default_factory=lambda: ["whip_pan", "zoom_blur", "flash_white"])
    frequency: str = "low"  # none | low | medium | high


class ColorStyle(BaseModel):
    lut: Optional[str] = None  # name of a built-in LUT or path to .cube
    intensity: float = 0.7
    per_emotion: dict[str, str] = Field(default_factory=dict)  # emotion -> color effect id
    auto_color: bool = True


class AudioStyle(BaseModel):
    denoise: bool = True
    voice_enhance: bool = True
    keep_original_bgm: bool = True
    music_mood: Optional[str] = None  # None = auto by emotion (when music library exists)
    bgm_by_emotion: bool = False
    duck_db: float = -14.0
    sfx: bool = True
    sfx_pack: str = "drama"
    loudness_lufs: float = -14.0
    music_drop_on_shock: bool = True
    sfx_after_hook: bool = False  # sound effect at the hook -> story jump (rewind tape etc.); off = quiet jump
    sfx_volume: float = 50.0  # % loudness of sound effects (0 = off, 100 = full, up to 200)
    music_volume: float = 100.0  # % loudness of added background music
    bgm_volume: float = 100.0  # % loudness of the video's own music (when separated)


class EffectBudget(BaseModel):
    strong_combo_every_sec: float = 15.0  # at most one strong combo per N seconds
    small_effect_every_sec: float = 4.0  # at most one small effect per N seconds
    cooldown_sec: float = 6.0  # same effect id not repeated within N seconds
    intensity: str = "medium"  # minimal | low | medium | high | extreme


class Extras(BaseModel):
    progress_bar: bool = False
    cta: bool = False
    continue_card: bool = False
    character_cards: bool = False
    episode_badge: Optional[str] = None
    watermark: Optional[str] = None  # text or image path
    title: Optional[str] = None  # explicit title text for the hook card


class StyleDNA(BaseModel):
    name: str = "default"
    description: str = ""
    genre: Optional[str] = None
    pacing: Pacing = Field(default_factory=Pacing)
    hook: Hook = Field(default_factory=Hook)
    captions: Captions = Field(default_factory=Captions)
    camera: Camera = Field(default_factory=Camera)
    transitions: Transitions = Field(default_factory=Transitions)
    color: ColorStyle = Field(default_factory=ColorStyle)
    audio: AudioStyle = Field(default_factory=AudioStyle)
    budget: EffectBudget = Field(default_factory=EffectBudget)
    extras: Extras = Field(default_factory=Extras)
    preferred_effects: list[str] = Field(default_factory=list)
    banned_effects: list[str] = Field(default_factory=list)
    target_duration: Optional[float] = None  # seconds
    parts: int = 1  # split into N parts
    frames: Optional[list[str]] = None  # raw frame requests ("tiktok", "4:5", "1080x1350"...)
    existing_text: str = "avoid"
    text_language: Optional[str] = None  # language of ADDED text (titles, cards); None = language spoken in the video

    def merged(self, patch: dict) -> "StyleDNA":
        """Deep-merge a partial dict into a copy of this style."""
        base = self.model_dump()
        _deep_merge(base, patch)
        return StyleDNA.model_validate(base)


def _deep_merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
