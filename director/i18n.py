"""Language of the text the tool ADDS on screen (titles, cards, labels).

Captions always keep the video's own spoken language. Added text follows `StyleDNA.text_language`:
None/"auto" = the language spoken in the video (detected by Whisper), falling back to Vietnamese."""

from __future__ import annotations

LANG_NAMES = {
    "vi": "tiếng Việt", "ko": "tiếng Hàn (한국어)", "en": "tiếng Anh (English)", "ja": "tiếng Nhật (日本語)",
    "zh": "tiếng Trung (中文)", "th": "tiếng Thái", "id": "tiếng Indonesia", "es": "tiếng Tây Ban Nha",
}

# key -> language -> text
STRINGS: dict[str, dict[str, str]] = {
    "before": {"vi": "Trước đó...", "ko": "그 전에...", "en": "Earlier...", "ja": "少し前…", "zh": "在此之前…",
               "th": "ก่อนหน้านั้น...", "id": "Sebelumnya...", "es": "Antes..."},
    "later": {"vi": "Một lúc sau...", "ko": "잠시 후...", "en": "A little later...", "ja": "しばらくして…", "zh": "过了一会儿…",
              "th": "สักพักต่อมา...", "id": "Beberapa saat kemudian...", "es": "Un rato después..."},
    "continue": {"vi": "Còn tiếp...", "ko": "다음 편에 계속...", "en": "To be continued...", "ja": "つづく…", "zh": "未完待续…",
                 "th": "โปรดติดตามตอนต่อไป...", "id": "Bersambung...", "es": "Continuará..."},
    "cta": {"vi": "Theo dõi để xem tiếp!", "ko": "구독하고 다음 편 보기!", "en": "Follow for the next part!", "ja": "フォローして続きを見てね！",
            "zh": "关注看后续！", "th": "กดติดตามเพื่อดูตอนต่อไป!", "id": "Ikuti untuk lanjutannya!", "es": "¡Sígueme para la siguiente parte!"},
    "villain": {"vi": "PHẢN DIỆN", "ko": "악역", "en": "VILLAIN", "ja": "悪役", "zh": "反派", "th": "ตัวร้าย", "id": "PENJAHAT", "es": "VILLANO"},
    "boom": {"vi": "RẦM!", "ko": "쾅!", "en": "BOOM!", "ja": "ドーン！", "zh": "轰！", "th": "ตูม!", "id": "BUM!", "es": "¡BUM!"},
    "thanks": {"vi": "Cảm ơn đã xem!", "ko": "시청해 주셔서 감사합니다!", "en": "Thanks for watching!", "ja": "ご視聴ありがとう！",
               "zh": "感谢观看！", "th": "ขอบคุณที่รับชม!", "id": "Terima kasih sudah menonton!", "es": "¡Gracias por ver!"},
    "character": {"vi": "Nhân vật {n}", "ko": "인물 {n}", "en": "Character {n}", "ja": "キャラ{n}", "zh": "角色{n}",
                  "th": "ตัวละคร {n}", "id": "Tokoh {n}", "es": "Personaje {n}"},
    "episode": {"vi": "Tập {n}", "ko": "{n}화", "en": "Episode {n}", "ja": "第{n}話", "zh": "第{n}集",
                "th": "ตอนที่ {n}", "id": "Episode {n}", "es": "Episodio {n}"},
}

# Default param texts in the effect catalog / older plans -> string key (so they can be translated)
DEFAULT_TEXT_KEYS = {
    "Trước đó...": "before", "Một lúc sau...": "later", "Còn tiếp...": "continue", "Theo dõi để xem tiếp!": "cta",
    "PHẢN DIỆN": "villain", "RẦM!": "boom", "Cảm ơn đã xem!": "thanks",
}
EFFECT_TEXT_KEY = {"time_skip": "later", "continue_card": "continue", "cta": "cta", "warning_label": "villain",
                   "sfx_text": "boom", "end_screen": "thanks"}


def normalize(lang: str | None) -> str | None:
    if not lang or lang == "auto":
        return None
    lang = lang.lower().strip()
    aliases = {"viet": "vi", "vietnamese": "vi", "tiếng việt": "vi", "korean": "ko", "kr": "ko", "hàn": "ko", "tiếng hàn": "ko",
               "english": "en", "anh": "en", "tiếng anh": "en", "japanese": "ja", "jp": "ja", "nhật": "ja", "tiếng nhật": "ja",
               "chinese": "zh", "cn": "zh", "trung": "zh", "tiếng trung": "zh", "thai": "th", "thái": "th"}
    lang = aliases.get(lang, lang)
    return lang.split("-")[0][:2]


def resolve(text_language: str | None, spoken: str | None) -> str:
    lang = normalize(text_language) or normalize(spoken) or "vi"
    return lang if lang in STRINGS["before"] else "en"


def t(key: str, lang: str, **kw) -> str:
    table = STRINGS[key]
    s = table.get(lang) or table.get("en") or table["vi"]
    return s.format(**kw) if kw else s


def name(lang: str) -> str:
    return LANG_NAMES.get(lang, lang)
