"""Rule-based understanding of free-form style commands (Vietnamese + English).

The LLM Director (when configured) re-reads the command too; this parser guarantees the
tool still does the right thing offline."""

from __future__ import annotations

import re
import unicodedata

from ..plan.frames import frames_from_text
from .dna import StyleDNA
from .presets import default_for_genre, get_preset


def _plain(s: str) -> str:
    s = s.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _has(text: str, *keys: str) -> bool:
    """Match accented keys against the accented text; unaccented keys against the stripped text."""
    low = text.lower()
    plain = _plain(text)
    for k in keys:
        if _plain(k) != k.lower():
            if re.search(rf"(?<!\w){re.escape(k.lower())}(?!\w)", low):
                return True
        elif re.search(rf"(?<!\w){re.escape(k)}(?!\w)", plain):
            return True
    return False


PRESET_KEYS = [
    ("toi-gian", ("tối giản", "đơn giản", "minimal", "nhẹ nhàng thôi")),
    ("dien-anh", ("điện ảnh", "cinematic", "kiểu phim")),
    ("hai-huoc", ("hài hước", "hài", "funny", "comedy", "vui nhộn")),
    ("kinh-di", ("kinh dị", "hồi hộp", "horror", "rùng rợn")),
    ("lang-man", ("lãng mạn", "romance", "romantic", "ngôn tình")),
    ("youtube-ke-chuyen", ("kể chuyện", "storytelling", "review")),
    ("anime-drama", ("drama", "hoạt hình", "anime", "cartoon", "phim hoạt hình")),
    ("tiktok-nang-dong", ("tiktok", "năng động", "reels", "shorts", "viral")),
]

LUT_KEYS = [
    ("bw", ("đen trắng", "black and white", "b&w")),
    ("sepia", ("nâu cũ", "sepia")),
    ("vintage", ("cổ điển", "vintage", "hoài niệm", "retro")),
    ("teal_orange", ("teal orange", "teal-orange", "xanh cam")),
    ("cinematic", ("màu điện ảnh",)),
    ("warm", ("màu ấm", "ấm áp", "tông ấm", "warm")),
    ("cool", ("màu lạnh", "tông lạnh", "cool tone", "xanh lạnh")),
    ("pop", ("màu tươi", "rực rỡ", "tươi sáng", "vivid", "saturated")),
    ("moody", ("u tối", "tông tối", "moody", "dark tone")),
    ("pastel", ("pastel", "nhẹ nhàng dịu")),
    ("night", ("ban đêm", "tông đêm")),
]

COLOR_WORDS = {
    "vàng": "#FFD400", "trắng": "#FFFFFF", "đỏ": "#FF3B30", "xanh lá": "#34C759", "xanh dương": "#0A84FF",
    "xanh": "#4FC3F7", "hồng": "#FF6B9D", "cam": "#FF9500", "tím": "#AF52DE", "đen": "#000000",
    "yellow": "#FFD400", "white": "#FFFFFF", "red": "#FF3B30", "green": "#34C759", "blue": "#0A84FF", "pink": "#FF6B9D",
}

CAPTION_KEYS = [
    ("karaoke", ("karaoke",)),
    ("word_pop", ("từng từ", "word by word", "bật từng chữ")),
    ("speech_bubble", ("bong bóng thoại", "speech bubble")),
    ("typewriter", ("đánh máy", "gõ chữ", "typewriter")),
    ("neon", ("neon", "phát sáng")),
    ("handwritten", ("viết tay", "handwritten")),
    ("box", ("nền hộp", "khối nền", "box")),
    ("highlight_keyword", ("nhấn từ khoá", "tô từ khoá", "highlight")),
    ("bounce", ("nảy", "bounce")),
    ("classic", ("cổ điển", "đơn giản", "classic")),
]

MUSIC_KEYS = [
    ("sad", ("nhạc buồn", "sad music", "nhạc piano")),
    ("happy", ("nhạc vui", "upbeat", "nhạc sôi động")),
    ("tense", ("nhạc căng thẳng", "nhạc hồi hộp", "tense")),
    ("epic", ("nhạc hùng tráng", "epic")),
    ("romance", ("nhạc lãng mạn", "nhạc tình cảm")),
    ("comedy", ("nhạc hài", "nhạc vui nhộn")),
]


def choose_preset(text: str, genre: str) -> StyleDNA:
    for name, keys in PRESET_KEYS:
        if _has(text, *keys):
            return get_preset(name)
    return default_for_genre(genre)


def parse_style(text: str | None, genre: str = "unknown", base: StyleDNA | None = None) -> StyleDNA:
    text = (text or "").strip()
    style = base or choose_preset(text, genre)
    if not text:
        return style
    patch: dict = {}
    style.description = text

    # ---- duration / parts
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(phút|phut|min|minutes?|p)\b", _plain(text))
    secs = None
    if m:
        secs = float(m.group(1).replace(",", ".")) * 60
    m2 = re.search(r"(\d+(?:[.,]\d+)?)\s*(giây|giay|s|sec|seconds?)\b", _plain(text))
    if m2:
        secs = (secs or 0) + float(m2.group(1).replace(",", "."))
    if secs and 5 <= secs <= 3 * 3600:
        patch["target_duration"] = secs
    m = re.search(r"(\d+)\s*(phần|phan|part|parts|tập nhỏ)", _plain(text))
    if m and 1 < int(m.group(1)) <= 20:
        patch["parts"] = int(m.group(1))
        patch.setdefault("extras", {})["continue_card"] = True

    # ---- frames
    frames = frames_from_text(text)
    if frames:
        patch["frames"] = frames

    # ---- effect intensity
    if _has(text, "nhiều hiệu ứng", "mạnh tay", "thật nhiều", "bùng nổ", "lots of effects", "cực mạnh"):
        patch["budget"] = {"intensity": "high", "strong_combo_every_sec": 8.0, "small_effect_every_sec": 2.0, "cooldown_sec": 4.0}
    elif _has(text, "ít hiệu ứng", "nhẹ nhàng", "vừa phải", "subtle", "không lạm dụng"):
        patch["budget"] = {"intensity": "low", "strong_combo_every_sec": 25.0, "small_effect_every_sec": 7.0}
    if _has(text, "không hiệu ứng", "không có hiệu ứng", "no effects"):
        patch["budget"] = {"intensity": "minimal", "strong_combo_every_sec": 9999, "small_effect_every_sec": 9999}

    # ---- pacing
    if _has(text, "cắt nhanh", "nhịp nhanh", "dồn dập", "fast paced"):
        patch["pacing"] = {"avg_shot_sec": 1.5, "remove_silence_over": 0.22, "keep_pause": 0.06}
    elif _has(text, "nhịp chậm", "chậm rãi", "từ từ", "slow paced"):
        patch["pacing"] = {"avg_shot_sec": 4.0, "remove_silence_over": 0.9}
    if _has(text, "giữ nguyên thoại", "không cắt", "giữ nguyên nội dung", "không bỏ đoạn nào"):
        patch.setdefault("pacing", {}).update({"remove_silence_over": 3.0, "remove_fillers": False, "remove_retakes": False})
    if _has(text, "theo nhịp nhạc", "theo beat", "on beat"):
        patch.setdefault("pacing", {})["cut_on_beat"] = True

    # ---- hook
    if _has(text, "không hook", "no hook", "không cần hook"):
        patch["hook"] = {"enabled": False, "strategy": "none"}
    elif _has(text, "twist", "cú sốc", "cú tát", "cao trào", "mở bằng", "mở đầu bằng"):
        patch["hook"] = {"enabled": True, "strategy": "twist-first-then-rewind"}
    elif _has(text, "câu hỏi", "gợi tò mò"):
        patch["hook"] = {"enabled": True, "strategy": "question"}

    # ---- captions
    cap: dict = {}
    if _has(text, "không phụ đề", "bỏ phụ đề", "không sub", "no captions", "no subtitles"):
        cap["enabled"] = False
    if _has(text, "dù đã có sub", "dù có sub", "thêm phụ đề", "vẫn thêm phụ đề", "phụ đề đầy đủ"):
        cap["if_hardsub"] = "full"
    for preset, keys in CAPTION_KEYS:
        if _has(text, *[f"phụ đề {k}" for k in keys] + [f"sub {k}" for k in keys] + list(keys[:1])):
            cap["preset"] = preset
            break
    if _has(text, "phụ đề to", "chữ to", "sub to", "big captions") or re.search(r"(phụ đề|sub|chữ)[^,.;]{0,15}\bto\b", text.lower()):
        cap["size"] = 1.35
    if _has(text, "phụ đề nhỏ", "chữ nhỏ"):
        cap["size"] = 0.8
    if _has(text, "in hoa", "chữ hoa", "uppercase"):
        cap["uppercase"] = True
    if _has(text, "emoji", "biểu tượng cảm xúc"):
        cap["emoji"] = True
    for word, hexv in COLOR_WORDS.items():
        if _has(text, f"phụ đề {word}", f"chữ {word}", f"sub {word}", f"{word} captions"):
            cap["highlight" if cap.get("preset") in ("word_pop", "karaoke", "highlight_keyword") else "color"] = hexv
            break
    if _has(text, "màu theo nhân vật", "mỗi nhân vật một màu"):
        cap["color_by_character"] = True
        cap["preset"] = "color_by_character"
    if _has(text, "phụ đề ở trên", "sub ở trên", "phụ đề phía trên"):
        cap["position"] = "top"
    if _has(text, "phụ đề ở giữa", "sub ở giữa"):
        cap["position"] = "middle"
    if cap:
        patch["captions"] = cap

    # ---- color
    for lut, keys in LUT_KEYS:
        if _has(text, *keys):
            patch["color"] = {"lut": lut, "intensity": 0.75}
            break
    if _has(text, "giữ màu gốc", "không chỉnh màu", "màu gốc"):
        patch["color"] = {"lut": None, "auto_color": False}

    # ---- camera / framing
    if _has(text, "nền mờ", "giữ trọn khung", "không cắt khung"):
        patch["camera"] = {"reframe": "fit-blur"}
    elif _has(text, "chia đôi màn hình", "split screen"):
        patch["camera"] = {"reframe": "split"}
    elif _has(text, "bám theo nhân vật", "bám theo mặt", "follow"):
        patch["camera"] = {"reframe": "follow-character"}
    if _has(text, "không zoom", "no zoom"):
        patch.setdefault("camera", {}).update({"punch_in_on_emphasis": False, "punch_in_on": []})

    # ---- audio
    au: dict = {}
    for mood, keys in MUSIC_KEYS:
        if _has(text, *keys):
            au["music_mood"] = mood
            break
    if _has(text, "nhạc theo cảm xúc", "đổi nhạc theo cảnh"):
        au["bgm_by_emotion"] = True
    if _has(text, "không tiếng động", "không sfx", "no sfx"):
        au["sfx"] = False
    if _has(text, "bỏ nhạc gốc", "tắt nhạc gốc"):
        au["keep_original_bgm"] = False
    if au:
        patch["audio"] = au

    # ---- language of added text
    for code, keys in (("ko", ("chữ tiếng hàn", "chữ hàn", "ngôn ngữ hàn", "tiếng hàn", "korean text")),
                       ("vi", ("chữ tiếng việt", "chữ việt", "ngôn ngữ việt", "tiếng việt")),
                       ("en", ("chữ tiếng anh", "ngôn ngữ anh", "tiếng anh", "english text")),
                       ("ja", ("chữ tiếng nhật", "ngôn ngữ nhật", "tiếng nhật", "japanese text")),
                       ("zh", ("chữ tiếng trung", "ngôn ngữ trung", "tiếng trung", "chinese text"))):
        if _has(text, *keys):
            patch["text_language"] = code
            break

    # ---- extras
    ex: dict = {}
    if _has(text, "thanh tiến trình", "progress bar"):
        ex["progress_bar"] = True
    if _has(text, "đăng ký", "theo dõi", "subscribe", "follow kênh"):
        ex["cta"] = True
    if _has(text, "còn tiếp", "to be continued"):
        ex["continue_card"] = True
    m = re.search(r"tập\s*(\d+)", text.lower())
    if m:
        ex["episode_badge"] = f"Tập {m.group(1)}"
    m = re.search(r"(?:tiêu đề|tên video|title)\s*[:\"“]\s*([^\"”\n]+)", text, re.IGNORECASE)
    if m:
        ex["title"] = m.group(1).strip()
    if _has(text, "giới thiệu nhân vật", "thẻ nhân vật"):
        ex["character_cards"] = True
    if ex:
        patch["extras"] = ex

    return style.merged(patch) if patch else style
