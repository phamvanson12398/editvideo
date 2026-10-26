"""Soundtrack mixing with real ffmpeg: stays in sync, survives bad clip effects and graph failures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import director.render.audio_mix as AM
from director.plan.schema import AudioClipFx, AudioPlan, Clip, EditPlan, MusicCue, OutputSpec, SfxCue, VolumeEvent
from director.render.sfx_synth import sfx_file
from director.utils.ffmpeg import probe, run

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def _plan(tmp: Path) -> EditPlan:
    src = tmp / "src.wav"
    run(["-f", "lavfi", "-t", "12", "-i", "sine=f=220:sample_rate=44100", "-ac", "2", str(src)])
    music = tmp / "music.wav"
    run(["-f", "lavfi", "-t", "3", "-i", "sine=f=440:sample_rate=22050", str(music)])
    clips, t = [], 0.0
    specs = [(0.5, 2.0, 1.0, False, None, "main"), (3.0, 4.0, 0.5, False, None, "main"), (4.0, 5.5, 1.0, True, None, "reverse"),
             (6.0, 6.0, 1.0, False, 6.0, "freeze"), (7.0, 9.0, 2.0, False, None, "main"), (11.5, 13.0, 1.0, False, None, "main")]
    for i, (a, b, sp, rev, fr, role) in enumerate(specs):
        d = 0.8 if fr is not None else (b - a) / sp
        clips.append(Clip(id=f"c{i}", file="", start=t, duration=d, src_in=a, src_out=b, speed=sp, reverse=rev, freeze=fr, role=role))
        t += d
    sfx = [SfxCue(id=k, file=str(sfx_file(k, Path("/nonexistent"), tmp / "sfx")), start=s) for k, s in (("pop", 0.5), ("pop", 2.0), ("slap", 3.0))]
    audio = AudioPlan(
        voice_source="original",
        clip_fx=[AudioClipFx(id="pitch_up", clip="c0"), AudioClipFx(id="echo", clip="c1"), AudioClipFx(id="tape_stop", clip="c4")],
        music=[MusicCue(file=str(music), start=0.0, end=t, gain_db=-10)],
        sfx=sfx,
        volume=[VolumeEvent(target="music", start=1.0, end=2.0, gain=0.1), VolumeEvent(target="all", start=4.0, end=4.3, gain=0.0)],
    )
    return EditPlan(source=str(src), source_size=(1280, 720), source_fps=30, duration=round(t, 3),
                    outputs=[OutputSpec(id="o", aspect="9:16", width=1080, height=1920)], clips=clips, audio=audio)


def _dur(p: Path) -> float:
    return float(probe(p)["format"]["duration"])


def test_soundtrack_in_sync(tmp_path):
    plan = _plan(tmp_path)
    out = AM.build_soundtrack(plan, tmp_path, tmp_path / "mix.wav")
    assert abs(_dur(out) - plan.duration) < 0.05


def test_bad_clip_effect_is_dropped(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    monkeypatch.setitem(AM.CLIP_FX, "echo", "thisfilterdoesnotexist=1")
    out = AM.build_soundtrack(plan, tmp_path, tmp_path / "mix.wav")
    assert abs(_dur(out) - plan.duration) < 0.05


def test_mix_falls_back_to_simpler_graph(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    real = AM._mix
    levels = []

    def flaky(*a, **k):
        level = a[-1]
        levels.append(level)
        if level == 0:
            raise AM.FFmpegError("simulated: Error while filtering: Invalid argument")
        return real(*a, **k)

    monkeypatch.setattr(AM, "_mix", flaky)
    out = AM.build_soundtrack(plan, tmp_path, tmp_path / "mix.wav")
    assert levels == [0, 1] and abs(_dur(out) - plan.duration) < 0.05
