"""Sound-effect / music volume settings reach the soundtrack plan."""

from __future__ import annotations

from pathlib import Path

from director.agent.planner_rules import plan_rules
from director.plan.compiler import compile_plan
from director.plan.frames import parse_frames
from director.style.parse import parse_style

from .test_core import make_index


def _sfx_gains(style, tmp: Path):
    idx = make_index()
    plan = compile_plan(plan_rules(idx, style)[0], idx, style, parse_frames(["9:16"], 1280, 720), cache=tmp)
    return [s.gain_db for s in plan.audio.sfx]


def test_sfx_volume_percent(tmp_path):
    loud = parse_style("drama dọc 9:16, tiếng động 100%", "anime")
    quiet = parse_style("drama dọc 9:16, tiếng động 25%", "anime")
    g_loud, g_quiet = _sfx_gains(loud, tmp_path), _sfx_gains(quiet, tmp_path)
    assert g_loud and len(g_loud) == len(g_quiet)
    assert all(abs((a - b) - 12.04) < 0.1 for a, b in zip(g_loud, g_quiet))  # 25% = -12 dB vs 100%


def test_sfx_volume_zero_removes_sfx(tmp_path):
    st = parse_style("drama dọc 9:16", "anime")
    st.audio.sfx_volume = 0
    assert _sfx_gains(st, tmp_path) == []


def test_default_is_quieter_than_before(tmp_path):
    st = parse_style("drama dọc 9:16", "anime")
    assert st.audio.sfx_volume == 50
    assert all(g <= -8.9 for g in _sfx_gains(st, tmp_path))  # -3 dB base -6 dB (50%)
