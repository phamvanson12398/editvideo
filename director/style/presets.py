"""Built-in Style DNA presets and genre defaults."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .dna import StyleDNA

_PRESETS: dict[str, dict] = {
    "anime-drama": {
        "description": "Hoạt hình drama: hook bằng cú twist, phụ đề màu theo nhân vật, combo hiệu ứng theo cảm xúc",
        "genre": "anime",
        "pacing": {"avg_shot_sec": 2.2, "remove_silence_over": 0.5, "slow_down_on": ["sad"], "cut_on_beat": False},
        "hook": {"enabled": True, "max_sec": 3.0, "strategy": "twist-first-then-rewind"},
        "captions": {"preset": "color_by_character", "color_by_character": True, "emotion_styles": True,
                     "words_per_line": 5, "weight": 800, "if_hardsub": "emphasis-only"},
        "camera": {"reframe": "auto", "punch_in_on": ["shock", "anger"], "shake_on": ["shock", "anger"]},
        "transitions": {"default": "cut", "accent": ["flash_white", "fade_black", "glitch_cut"], "frequency": "low"},
        "color": {"lut": "anime_vivid", "intensity": 0.5,
                  "per_emotion": {"sad": "desaturate", "anger": "tint", "villain": "tint"}},
        "audio": {"keep_original_bgm": True, "sfx_pack": "drama", "music_drop_on_shock": True},
        "budget": {"strong_combo_every_sec": 12.0, "small_effect_every_sec": 3.5, "cooldown_sec": 6.0, "intensity": "medium"},
        "extras": {"progress_bar": False, "character_cards": True, "continue_card": False},
    },
    "tiktok-nang-dong": {
        "description": "TikTok năng động: cắt nhanh, từng từ bật lên, zoom theo nhấn giọng",
        "pacing": {"avg_shot_sec": 1.6, "remove_silence_over": 0.25, "keep_pause": 0.08, "cut_on_beat": True},
        "hook": {"strategy": "best-moment-first", "max_sec": 2.5},
        "captions": {"preset": "word_pop", "words_per_line": 3, "weight": 900, "uppercase": False, "emoji": True},
        "camera": {"punch_in_on_emphasis": True, "zoom_range": [1.0, 1.35]},
        "transitions": {"accent": ["whip_pan", "zoom_blur", "zoom_in_out"], "frequency": "medium"},
        "color": {"lut": "pop", "intensity": 0.6},
        "budget": {"strong_combo_every_sec": 10.0, "small_effect_every_sec": 2.5, "intensity": "high"},
        "extras": {"progress_bar": True},
        "frames": ["9:16"],
    },
    "youtube-ke-chuyen": {
        "description": "YouTube kể chuyện: nhịp vừa, phụ đề cổ điển, chuyển cảnh nhẹ",
        "pacing": {"avg_shot_sec": 3.5, "remove_silence_over": 0.6},
        "captions": {"preset": "classic", "words_per_line": 8},
        "camera": {"punch_in_on_emphasis": False},
        "transitions": {"accent": ["crossfade", "fade_black"], "frequency": "low"},
        "color": {"lut": "warm", "intensity": 0.4},
        "budget": {"strong_combo_every_sec": 30.0, "small_effect_every_sec": 8.0, "intensity": "low"},
        "frames": ["16:9"],
    },
    "toi-gian": {
        "description": "Tối giản: chỉ cắt gọn, phụ đề sạch, gần như không hiệu ứng",
        "pacing": {"remove_silence_over": 0.5},
        "hook": {"enabled": False, "strategy": "none"},
        "captions": {"preset": "classic", "words_per_line": 6},
        "camera": {"punch_in_on_emphasis": False, "punch_in_on": [], "shake_on": []},
        "transitions": {"accent": [], "frequency": "none"},
        "audio": {"sfx": False, "music_drop_on_shock": False},
        "budget": {"strong_combo_every_sec": 9999, "small_effect_every_sec": 9999, "intensity": "minimal"},
    },
    "dien-anh": {
        "description": "Điện ảnh: viền đen, màu teal-orange, nhịp chậm, chuyển cảnh mờ",
        "pacing": {"avg_shot_sec": 4.0, "remove_silence_over": 0.9, "remove_fillers": False},
        "captions": {"preset": "classic", "weight": 500, "words_per_line": 8, "size": 0.85},
        "camera": {"punch_in_on_emphasis": False, "reframe": "letterbox"},
        "transitions": {"accent": ["crossfade", "fade_black"], "frequency": "low"},
        "color": {"lut": "cinematic", "intensity": 0.8},
        "budget": {"strong_combo_every_sec": 40.0, "small_effect_every_sec": 10.0, "intensity": "low"},
        "preferred_effects": ["film_grain", "letterbox", "slow_push"],
    },
    "hai-huoc": {
        "description": "Hài hước: emoji, tiếng động hài, zoom méo, lặp giật",
        "pacing": {"avg_shot_sec": 1.8, "remove_silence_over": 0.3},
        "captions": {"preset": "bounce", "emoji": True, "words_per_line": 4},
        "transitions": {"accent": ["spin", "zoom_in_out", "iris"], "frequency": "medium"},
        "audio": {"sfx_pack": "comedy"},
        "budget": {"strong_combo_every_sec": 10.0, "small_effect_every_sec": 3.0, "intensity": "high"},
        "preferred_effects": ["combo.comedy", "emoji_pop", "question_marks", "sweat_drop", "boomerang"],
    },
    "kinh-di": {
        "description": "Kinh dị / hồi hộp: tối, chập chờn, nhịp tim",
        "captions": {"preset": "typewriter"},
        "color": {"lut": "moody", "intensity": 0.8},
        "audio": {"sfx_pack": "drama"},
        "preferred_effects": ["combo.fear", "flicker", "vignette", "handheld", "glitch"],
    },
    "lang-man": {
        "description": "Lãng mạn: sáng ấm, tim bay, chuyển cảnh mềm",
        "captions": {"preset": "handwritten"},
        "color": {"lut": "pastel", "intensity": 0.6},
        "transitions": {"accent": ["crossfade", "light_leak", "shape_mask"], "frequency": "low"},
        "preferred_effects": ["combo.romance", "glow", "petals", "slow_push"],
    },
}

GENRE_DEFAULT = {"anime": "anime-drama", "cartoon3d": "anime-drama", "live": "tiktok-nang-dong", "gameplay": "tiktok-nang-dong"}


def _user_dir() -> Path:
    return Path(os.environ.get("DIRECTOR_HOME") or Path.home() / ".director") / "styles"


def list_presets() -> dict[str, str]:
    out = {k: v.get("description", "") for k, v in _PRESETS.items()}
    d = _user_dir()
    if d.exists():
        for p in sorted(d.glob("*.json")):
            try:
                out[p.stem] = "(của bạn) " + json.loads(p.read_text(encoding="utf-8")).get("description", "")
            except Exception:
                continue
    return out


def get_preset(name: str) -> StyleDNA:
    user = _user_dir() / f"{name}.json"
    if user.exists():
        return StyleDNA.model_validate_json(user.read_text(encoding="utf-8"))
    if name not in _PRESETS:
        raise KeyError(f"Không có preset phong cách '{name}'. Có: {', '.join(list_presets())}")
    return StyleDNA(name=name).merged(_PRESETS[name])


def default_for_genre(genre: str) -> StyleDNA:
    return get_preset(GENRE_DEFAULT.get(genre, "anime-drama"))
