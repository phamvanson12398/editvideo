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
    assert "FCM: NON-DROP FRAME" in edl.read_text()


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
