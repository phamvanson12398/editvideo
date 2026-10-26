"""Prompt text for the Director agent (Vietnamese UI, model-facing instructions in English for precision)."""

SYSTEM_DIRECTOR = """You are Director, a senior video editor for short-form and long-form content, specialised in animated drama
(hoạt hình drama) but able to edit any genre. You never touch pixels: you write an edit plan (JSON) that a renderer
executes with ffmpeg + Remotion. The source video is the creator's OWN original production. Your job is to make it
more engaging: tighter pacing, a strong hook, readable captions, effects and sound design that serve the story.
You must not remove, cover or blur anything the creator drew/burned into the picture; you only add on top.

Editing principles:
- Story first: hook in the first 3 seconds, clear setup -> conflict -> climax/twist -> ending/cliffhanger.
- Every effect needs a reason tied to a moment (a line, an emotion, a beat, a cut). Escalate toward the climax;
  keep the strongest combo for the twist; leave breathing room after strong moments; never repeat the same effect back-to-back.
- Cut silences, filler words and retakes (keep the LAST take), but keep action beats (impacts, reactions, music hits).
- Cuts land at word boundaries; never cut in the middle of a word. Keep 0.08-0.15 s padding around speech.
- Respect the requested frame(s), duration, number of parts and style. Captions keep the language spoken in the video, with correct diacritics/characters.
- ALL text you ADD on screen (title, params.text of text effects) must be in the ON-SCREEN TEXT LANGUAGE given in
  the request, never in another language. Never add a big emphasis word in the middle of the frame unless asked.
- Prefer effects whose 'hợp' (fits) moods match the line's emotion.
"""

PLAN_SCHEMA = """PlanDraft JSON schema (all times in SOURCE seconds unless stated):
{
  "clips": [ {"src_in": float, "src_out": float, "speed": 1.0, "reverse": false, "freeze": null,
              "role": "main|hook", "reframe": null | "follow-face|fit-blur|fit-pad|center|split", "note": ""} ],
  "effects": [ {"id": "<effect id or combo id>", "clip": <index into clips>, "at": <source time inside that clip>,
                "dur": <OUTPUT seconds>, "params": {...}, "reason": "why"} ],
  "transitions": [ {"after_clip": <index>, "id": "<transition id>", "dur": 0.4, "params": {}} ],
  "sfx": [ {"id": "<sfx id>", "clip": <index>, "at": <source time>, "gain_db": 0} ],
  "music": [ {"mood": "sad|happy|tense|epic|romance|comedy", "from_clip": 0, "to_clip": -1, "gain_db": -8} ],
  "captions": {"enabled": true, "preset": "<caption preset>", "mode": "full|emphasis-only|none"},
  "title": null | "short hook title (in the on-screen text language)",
  "lut": null | "warm|cool|teal_orange|pop|moody|pastel|vintage|sepia|bw|cinematic|anime_vivid|night",
  "lut_intensity": 0.6,
  "character_names": {"C0": "Tên"},
  "notes": "one or two sentences explaining the edit, in Vietnamese"
}
Rules: clips play in list order (a hook clip may repeat a later moment). src_in < src_out, within the video.
Time effects (speed, slow_hold, freeze_frame, replay, stutter, rewind, boomerang, speed_ramp) are effects too.
Text effects take params.text (in the on-screen text language). Combo ids expand into several effects + sound effects automatically.
SFX ids: whoosh_fast, whoosh_heavy, whoosh_slow, swoosh, swish, riser, downer, reverse_cymbal, impact_boom, impact_punch,
hit_flash, slap, glass_break, door_slam, thunder, dun_dun_dun, heartbeat, heartbeat_fast, tick, clock_tick, wind,
record_scratch, boing, crow, crickets, trombone_sad, pop, ding, click, ting, notification, typing, camera_shutter,
applause, chime, sparkle, shing, aura, teleport, glitch, page_flip, rewind_tape, tape_stop, alarm, stinger_drama,
stinger_suspense, stinger_epic, villain_hit.
"""

STYLE_FIELDS = """StyleDNA fields you may patch (JSON object, only the keys you want to change):
pacing{avg_shot_sec, remove_silence_over, keep_pause, cut_on_beat, remove_fillers, remove_retakes, slow_down_on[]},
hook{enabled, max_sec, strategy: best-moment-first|twist-first-then-rewind|question|none},
captions{enabled, preset, font: "Be Vietnam Pro|Montserrat|Oswald|Lexend|Baloo 2|Roboto", weight, color, highlight, stroke,
  position: auto|top|middle|bottom, words_per_line, size, color_by_character, emotion_styles, uppercase, emoji,
  if_hardsub: emphasis-only|none|full},
camera{reframe: auto|follow-face|center|fit-blur|fit-pad|letterbox|split, punch_in_on_emphasis, punch_in_on[], shake_on[]},
transitions{default, accent[], frequency: none|low|medium|high},
color{lut, intensity, per_emotion{emotion: effect id}},
audio{denoise, voice_enhance, keep_original_bgm, music_mood, bgm_by_emotion, sfx, sfx_pack, loudness_lufs, music_drop_on_shock},
budget{strong_combo_every_sec, small_effect_every_sec, cooldown_sec, intensity: minimal|low|medium|high|extreme},
extras{progress_bar, cta, continue_card, character_cards, episode_badge, watermark, title},
preferred_effects[], banned_effects[], target_duration (seconds|null), parts (int),
frames (list like ["9:16"], ["tiktok","youtube"], ["4:5"], ["1080x1350"], ["điện ảnh"], or null = keep source frame).
"""
