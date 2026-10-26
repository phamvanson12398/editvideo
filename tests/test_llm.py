"""LLM path tests with a fake Claude (no network): JSON repair loop, plan validation, revision, story."""

from __future__ import annotations

import json

import pytest

import director.agent.llm as llm
from director.agent.director import apply_story, plan_with_llm, revise_draft
from director.plan.compiler import compile_plan
from director.plan.frames import parse_frames
from director.style.parse import parse_style

from .test_core import make_index


class FakeClaude:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, system, messages, effort, max_tokens):
        self.calls.append(messages)
        return self.replies.pop(0)


@pytest.fixture()
def idx():
    return make_index()


def good_draft(idx):
    s = idx.sentences
    return {
        "clips": [
            {"src_in": s[4].t0, "src_out": s[4].t1, "role": "hook"},
            {"src_in": s[0].t0, "src_out": s[2].t1},
            {"src_in": s[3].t0, "src_out": s[5].t1},
        ],
        "effects": [
            {"id": "combo.shock", "clip": 2, "at": s[4].t0 + 0.2, "dur": 1.0, "reason": "twist"},
            {"id": "title_slam", "clip": 0, "at": s[4].t0, "dur": 1.5, "params": {"text": "BÍ MẬT"}},
        ],
        "transitions": [{"after_clip": 0, "id": "glitch_cut", "dur": 0.4}],
        "sfx": [{"id": "whoosh_fast", "clip": 1, "at": s[0].t0}],
        "captions": {"enabled": True, "preset": "word_pop", "mode": "full"},
        "title": "BÍ MẬT",
        "notes": "test",
    }


def test_plan_with_llm_repairs_invalid_json(monkeypatch, idx):
    bad = {"parts": [{**good_draft(idx), "effects": [{"id": "not_an_effect", "clip": 0, "at": 1.0}]}]}
    fake = FakeClaude([json.dumps(bad), "```json\n" + json.dumps({"parts": [good_draft(idx)]}) + "\n```"])
    monkeypatch.setattr(llm, "_call", fake)
    monkeypatch.setattr("director.agent.director.keyframe_blocks", lambda *a, **k: [])
    style = parse_style("drama dọc 9:16", idx.genre)
    drafts = plan_with_llm(idx, style, "drama dọc 9:16")
    assert len(drafts) == 1 and len(drafts[0].clips) == 3
    assert len(fake.calls) == 2
    # the error was shown back to the model
    assert "not_an_effect" in fake.calls[1][-1]["content"]
    plan = compile_plan(drafts[0], idx, style, parse_frames(["9:16"], 1280, 720))
    assert any(e.id == "glitch_cut" for e in plan.effects)
    assert any(e.id == "focus_lines" for e in plan.effects)  # combo expanded


def test_revise_with_llm(monkeypatch, idx):
    style = parse_style("drama dọc 9:16", idx.genre)
    from director.agent.planner_rules import plan_rules

    d = plan_rules(idx, style)[0]
    plan = compile_plan(d, idx, style, parse_frames(["9:16"], 1280, 720))
    new = good_draft(idx)
    fake = FakeClaude([json.dumps({"style_patch": {"captions": {"preset": "karaoke"}}, "draft": new, "explain": "ok"})])
    monkeypatch.setattr(llm, "_call", fake)
    draft, st = revise_draft(plan, idx, style, "phụ đề karaoke", use_llm=True)
    assert st.captions.preset == "karaoke" and len(draft.clips) == 3


def test_revise_offline_drop_timestamp(idx):
    style = parse_style("drama dọc 9:16", idx.genre)
    from director.agent.planner_rules import plan_rules

    d = plan_rules(idx, style)[0]
    plan = compile_plan(d, idx, style, parse_frames(["9:16"], 1280, 720))
    t = plan.clips[2].start + 0.1
    mm, ss = divmod(int(t), 60)
    draft, _ = revise_draft(plan, idx, style, f"bỏ đoạn {mm}:{ss:02d}", use_llm=False)
    assert len(draft.clips) == len(d.clips) - 1


def test_apply_story(idx):
    apply_story(idx, {"summary": "Mai phát hiện bí mật", "characters": {"C0": {"name": "Mai"}},
                      "sentences": {"s0": {"emotion": "sad"}}, "beats": [{"t0": 1, "t1": 3, "type": "twist", "intensity": 0.9}]})
    assert idx.story_summary.startswith("Mai")
    assert idx.sentences[0].emotion == "sad"
    assert idx.story[0].type == "twist"
