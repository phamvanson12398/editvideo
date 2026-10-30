"""Fast unit tests (no video rendering)."""

from __future__ import annotations

from pathlib import Path

from director.agent.planner_rules import plan_rules
from director.effects.catalog import COMBOS, EFFECTS
from director.effects.rules import Candidate, apply_rules
from director.export.timeline import export_edl
from director.perception.schema import AudioInfo, FaceBox, FaceSample, Scene, Sentence, SourceInfo, VideoIndex, Word
from director.plan.compiler import compile_plan
from director.plan.frames import frames_from_text, parse_frames
from director.style.parse import parse_style
from director.style.presets import get_preset, list_presets


def make_index(hardsub: bool = False) -> VideoIndex:
    sents = []
    t = 0.5
    texts = ["Mẹ ơi con về rồi", "Con đi đâu cả ngày vậy hả", "Cái gì? Ai cho con đi làm!", "Con xin lỗi mẹ",
             "Thật ra con không phải con ruột của mẹ!", "Không thể nào! Trời ơi!"]
    for i, txt in enumerate(texts):
        words = []
        wt = t
        for w in txt.split():
            words.append(Word(t0=round(wt, 2), t1=round(wt + 0.3, 2), text=w, emphasis=0.9 if "!" in w else 0.3))
            wt += 0.35
        sents.append(Sentence(id=f"s{i}", t0=t, t1=round(wt, 2), text=txt, words=words, energy=i / 5,
                              emotion="shock" if "!" in txt else "neutral", character="C0" if i % 2 else "C1"))
        t = wt + 1.2
    D = t + 1
    faces = [FaceSample(t=k / 2, boxes=[FaceBox(x=0.4, y=0.2, w=0.2, h=0.35, character="C0")]) for k in range(int(D * 2) + 1)]
    idx = VideoIndex(
        source=SourceInfo(path="/tmp/none.mp4", duration=D, fps=24, width=1280, height=720),
        genre="anime", sentences=sents, scenes=[Scene(t0=0, t1=D / 2), Scene(t0=D / 2, t1=D)], faces=faces,
        audio=AudioInfo(silences=[(s.t1, s.t1 + 1.1) for s in sents], loud_events=[sents[2].t0 + 0.1, sents[4].t0 + 0.2]),
    )
    idx.hardsub.present = hardsub
    if hardsub:
        idx.hardsub.x, idx.hardsub.y, idx.hardsub.w, idx.hardsub.h = 0.1, 0.85, 0.8, 0.1
    from director.perception.semantics import find_highlights, rough_story

    idx.highlights = find_highlights(idx)
    idx.story = rough_story(idx)
    return idx


def test_frames_parsing():
    assert frames_from_text("dựng dọc 9:16 cho tiktok, đọc phụ đề ở 0:40")[0] == "9:16"
    outs = parse_frames(["9:16", "tiktok", "dọc"], 1920, 1080)
    assert len(outs) == 1 and (outs[0].width, outs[0].height) == (1080, 1920)
    assert [(o.width, o.height) for o in parse_frames(["khung instagram"], 1920, 1080)] == [(1080, 1350)]
    assert parse_frames(None, 1280, 720)[0].aspect == "source"
    assert frames_from_text("bỏ đoạn 1:20 đi") == []
    o = parse_frames(["1080x1350"], 1920, 1080)[0]
    assert (o.width, o.height) == (1080, 1350)


def test_style_parse():
    s = parse_style("drama dọc 9:16, hook bằng cú twist, 60 giây, phụ đề vàng to", "anime")
    assert s.name == "anime-drama" and s.target_duration == 60 and s.captions.size > 1 and s.hook.strategy == "twist-first-then-rewind"
    s2 = parse_style("thêm phụ đề to kiểu TikTok dù đã có sub", "anime")
    assert s2.captions.if_hardsub == "full"
    s3 = parse_style("tối giản thôi, 3 phần", "live")
    assert s3.parts == 3 and s3.budget.intensity == "minimal"
    assert set(list_presets()) >= {"anime-drama", "tiktok-nang-dong", "toi-gian"}


def test_rules_budget():
    style = get_preset("anime-drama")
    cands = [Candidate("combo.shock", t, 0.9) for t in (20, 22, 40)] + [Candidate("punch_in", t, 0.3) for t in (5, 5.5, 12)]
    kept = apply_rules(cands, style, 60)
    shocks = [c for c in kept if c.id == "combo.shock"]
    assert len(shocks) == 2  # 22 dropped (too close to 20)
    assert [c.t for c in kept if c.id == "punch_in"] == [5, 12]  # 5.5 too soon, same-id cooldown


def test_catalog_consistency():
    for cid, combo in COMBOS.items():
        for step, *_ in combo["steps"]:
            assert step.startswith("sfx:") or step in EFFECTS, (cid, step)
    assert len(EFFECTS) > 150


def test_plan_and_compile(tmp_path: Path):
    idx = make_index(hardsub=True)
    style = parse_style("drama dọc 9:16, hook bằng cú twist", idx.genre)
    drafts = plan_rules(idx, style)
    assert drafts and drafts[0].clips
    d = drafts[0]
    assert d.clips[0].role == "hook"
    outs = parse_frames(style.frames, 1280, 720)
    plan = compile_plan(d, idx, style, outs, cache=tmp_path)
    assert plan.duration > 3
    # timeline is contiguous
    for a, b in zip(plan.clips, plan.clips[1:]):
        assert abs(a.start + a.duration - b.start) < 1e-3
    # burned-in subtitles + vertical crop -> dialogue clips keep the full frame
    assert any(c.reframe[outs[0].id].mode == "fit-blur" for c in plan.clips)
    # the video already has subtitles: no extra captions (the "big yellow word in the middle" is off by default)
    assert plan.captions.mode == "none" and not plan.captions.enabled
    assert any(e.id == "vhs" for e in plan.effects)  # hook rewind
    assert all(Path(s.file).exists() for s in plan.audio.sfx)
    edl = export_edl(plan, tmp_path / "x.edl")
    assert "FCM: NON-DROP FRAME" in edl.read_text(encoding="utf-8")


def test_compile_follow_without_hardsub(tmp_path: Path):
    idx = make_index(hardsub=False)
    style = parse_style("tiktok 9:16 nhiều hiệu ứng", idx.genre)
    d = plan_rules(idx, style)[0]
    plan = compile_plan(d, idx, style, parse_frames(["9:16"], 1280, 720), cache=tmp_path)
    modes = {c.reframe[plan.outputs[0].id].mode for c in plan.clips}
    assert "follow" in modes
    assert plan.captions.enabled and plan.captions.lines


def test_parts_and_target(tmp_path: Path):
    idx = make_index()
    style = parse_style("2 phần", idx.genre)
    drafts = plan_rules(idx, style)
    assert len(drafts) == 2
    assert any(e.id == "combo.cliffhanger" for e in drafts[0].effects)


def test_whisper_gpu_failure_falls_back_to_cpu(monkeypatch, tmp_path):
    """Missing cublas64_12.dll on Windows must not kill the job: retry on CPU."""
    import sys
    import types

    import director.perception.speech as SP

    calls = []

    class Seg:
        start, end, text = 0.0, 1.0, "xin chào"
        words = [types.SimpleNamespace(word="xin", start=0.0, end=0.4), types.SimpleNamespace(word="chào", start=0.5, end=1.0)]

    class FakeModel:
        def __init__(self, size, device, compute_type):
            calls.append((size, device, compute_type))
            self.device = device

        def transcribe(self, *a, **k):
            if self.device == "cuda":
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            return iter([Seg()]), types.SimpleNamespace(language="vi")

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(SP, "gpu_available", lambda: True)
    sents, lang = SP.transcribe(tmp_path / "a.wav")
    assert [c[1] for c in calls] == ["cuda", "cpu"]
    assert lang == "vi" and sents[0].text == "xin chào"


def test_added_text_follows_video_language(tmp_path: Path):
    idx = make_index(hardsub=False)
    idx.language = "ko"
    style = parse_style("drama dọc 9:16, hook bằng cú twist, còn tiếp", idx.genre)
    plan = compile_plan(plan_rules(idx, style)[0], idx, style, parse_frames(["9:16"], 1280, 720), cache=tmp_path)
    texts = [e.params.get("text") for e in plan.effects if e.category == "text"]
    assert "그 전에..." in texts and "다음 편에 계속..." in texts
    assert not any(t and ("Trước" in t or "Còn tiếp" in t) for t in texts)
    # explicit choice wins over the spoken language
    style.text_language = "en"
    plan = compile_plan(plan_rules(idx, style)[0], idx, style, parse_frames(["9:16"], 1280, 720), cache=tmp_path)
    assert "Earlier..." in [e.params.get("text") for e in plan.effects]


def test_text_cards_do_not_overlap():
    """AI character card + automatic name bar for the same person must not stack (bug seen with '도연')."""
    from director.plan.compiler import declutter_text
    from director.plan.schema import Effect

    ai_card = Effect(id="character_card", category="text", start=10.0, end=12.5, params={"text": "도연", "subtitle": "남편"})
    auto_bar = Effect(id="lower_third", category="text", start=10.2, end=12.8, params={"text": "도연"}, reason="auto")
    later_same = Effect(id="lower_third", category="text", start=20.0, end=22.0, params={"text": "도연"}, reason="auto")
    other_slot = Effect(id="title_slam", category="text", start=10.5, end=12.0, params={"text": "충격"})
    shake = Effect(id="shake", category="camera", start=10.0, end=11.0)
    kept = declutter_text([auto_bar, ai_card, later_same, other_slot, shake])
    ids = [(e.id, e.start) for e in kept]
    assert ("character_card", 10.0) in ids and ("lower_third", 10.2) not in ids
    assert ("lower_third", 20.0) not in ids  # same name again within 30 s
    assert ("title_slam", 10.5) in ids and ("shake", 10.0) in ids


def test_hook_length_and_quiet_jump(tmp_path: Path):
    idx = make_index()
    style = parse_style("drama dọc 9:16, hook bằng cú twist", idx.genre)
    d = plan_rules(idx, style)[0]
    d.clips[0].src_out = d.clips[0].src_in + 1.0  # too short (AI plans can do this too)
    plan = compile_plan(d, idx, style, parse_frames(["9:16"], 1280, 720), cache=tmp_path)
    hook = plan.clips[0]
    assert hook.role == "hook" and 3.0 <= hook.duration <= 5.0
    word_ends = [w.t1 for s in idx.sentences for w in s.words] + [s.t1 for s in idx.sentences]
    assert any(abs(hook.src_out - 0.15 - t) < 1e-3 for t in word_ends)  # ends after a word, not mid-word
    jump = hook.start + hook.duration
    assert not [s for s in plan.audio.sfx if jump - 0.4 <= s.start <= jump + 2.5]
    assert any(e.id == "vhs" for e in plan.effects)  # the rewind picture is kept, only its sound is gone

    loud = parse_style("drama dọc 9:16, hook bằng cú twist, giữ tiếng động sau hook", idx.genre)
    assert loud.audio.sfx_after_hook and loud.audio.sfx
    plan2 = compile_plan(plan_rules(idx, loud)[0], idx, loud, parse_frames(["9:16"], 1280, 720), cache=tmp_path)
    assert any(s.id == "rewind_tape" for s in plan2.audio.sfx)


def test_hook_length_from_command():
    st = parse_style("drama, hook 4-6 giây, không tiếng động sau hook")
    assert (st.hook.min_sec, st.hook.max_sec) == (4.0, 6.0)
    assert st.audio.sfx and not st.audio.sfx_after_hook


def test_outputs_are_always_2k():
    from director.plan.frames import to_2k

    outs = to_2k(parse_frames(["9:16", "16:9", "4:5", "1080x1350"], 1280, 720))
    assert [(o.width, o.height) for o in outs][:3] == [(1440, 2560), (2560, 1440), (1440, 1800)]
    assert all(min(o.width, o.height) == 1440 and o.width % 2 == 0 and o.height % 2 == 0 for o in outs)
    assert to_2k(parse_frames(["9:16 4k"], 1280, 720))[0].width == 2160  # 4K asked explicitly stays 4K
    src = to_2k(parse_frames(None, 1280, 720))[0]  # source frame too
    assert (src.width, src.height) == (2560, 1440)
