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
    import math

    c = next(c for c in plan.clips if c.role == "main" and math.ceil(c.start) < c.start + c.duration)
    mm, ss = divmod(math.ceil(c.start), 60)
    draft, _ = revise_draft(plan, idx, style, f"bỏ đoạn {mm}:{ss:02d}", use_llm=False)
    assert len(draft.clips) == len(d.clips) - 1


def test_apply_story(idx):
    apply_story(idx, {"summary": "Mai phát hiện bí mật", "characters": {"C0": {"name": "Mai"}},
                      "sentences": {"s0": {"emotion": "sad"}}, "beats": [{"t0": 1, "t1": 3, "type": "twist", "intensity": 0.9}]})
    assert idx.story_summary.startswith("Mai")
    assert idx.sentences[0].emotion == "sad"
    assert idx.story[0].type == "twist"


def test_provider_selection(monkeypatch, tmp_path):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "DIRECTOR_LLM", "DIRECTOR_NO_LLM", "AGY_BIN", "LOCALAPPDATA"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert llm.provider() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.provider() is None  # API providers only when chosen explicitly
    fake = tmp_path / "agy"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    assert llm.provider() == "antigravity"
    monkeypatch.setenv("DIRECTOR_LLM", "claude")
    assert llm.provider() == "claude"


@pytest.mark.skipif(__import__("sys").platform == "win32", reason="fake agy is a shell script")
def test_antigravity_cli_roundtrip(monkeypatch, tmp_path):
    """Fake `agy`: checks the request folder and answers with the documented JSON envelope."""
    import base64
    import sys

    script = tmp_path / "fake_agy.py"
    script.write_text(
        "import json, os, sys\n"
        "req = open('REQUEST.md', encoding='utf-8').read()\n"
        "ok = '-p' in sys.argv and '--output-format' in sys.argv and os.path.exists('img_000.jpg') and 'xin chào' in req\n"
        "print(json.dumps({'conversation_id': 'c1', 'status': 'SUCCESS', 'response': json.dumps({'ok': ok})}))\n",
        encoding="utf-8")
    runner = tmp_path / "agy"
    runner.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    runner.chmod(0o755)
    monkeypatch.setenv("AGY_BIN", str(runner))
    monkeypatch.setenv("DIRECTOR_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DIRECTOR_LLM", raising=False)
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b"\xff\xd8jpg").decode()}}
    out = llm.ask_json("sys", [{"type": "text", "text": "xin chào"}, img])
    assert out == {"ok": True}
    assert not any((tmp_path / "home" / "ai_tmp").iterdir())  # temp request folder cleaned up


def test_gemini_adapter(monkeypatch):
    """Neutral content blocks -> Gemini contents; JSON repair turns use role 'model'."""
    import base64

    seen = {}

    class Resp:
        def __init__(self, text):
            self.text = text
            self.candidates = []

    class Models:
        def __init__(self):
            self.n = 0

        def generate_content(self, model, contents, config):
            seen.setdefault("calls", []).append((model, contents, config))
            self.n += 1
            return Resp("not json" if self.n == 1 else '{"ok": true}')

    class FakeClient:
        models = Models()

    monkeypatch.setenv("GEMINI_API_KEY", "y")
    monkeypatch.setenv("DIRECTOR_LLM", "gemini")
    monkeypatch.setattr(llm, "_gclient", FakeClient())
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b"\xff\xd8jpg").decode()}}
    out = llm.ask_json("sys", [{"type": "text", "text": "xin chào"}, img])
    assert out == {"ok": True}
    model, contents, config = seen["calls"][1]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[0].parts[1].inline_data.mime_type == "image/jpeg"
    assert config.response_mime_type == "application/json" and config.system_instruction == "sys"


def test_one_call_plans_and_understands_story(monkeypatch, idx):
    """Planning and story understanding happen in a single AI call (faster)."""
    reply = {"story": {"summary": "Mẹ phát hiện bí mật", "characters": {"C0": {"name": "Ji Eun"}}},
             "parts": [good_draft(idx)]}
    fake = FakeClaude([json.dumps(reply)])
    monkeypatch.setattr(llm, "_call", fake)
    monkeypatch.setattr("director.agent.director.keyframe_blocks", lambda *a, **k: [])
    from director.perception.schema import Character

    idx.characters = [Character(id="C0")]
    idx.story_summary = ""
    style = parse_style("drama dọc 9:16", idx.genre)
    drafts = plan_with_llm(idx, style, "drama dọc 9:16")
    assert len(fake.calls) == 1 and len(drafts) == 1
    assert idx.story_summary == "Mẹ phát hiện bí mật" and idx.characters[0].name == "Ji Eun"
