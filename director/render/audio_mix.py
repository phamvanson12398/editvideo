"""Build the final soundtrack with one ffmpeg filter graph:
voice (cut like the video) + original BGM stem + music (ducked under voice) + SFX + volume automation + loudness."""

from __future__ import annotations

from pathlib import Path

from ..plan.schema import EditPlan
from ..utils.ffmpeg import filter_script_args, run
from ..utils.log import log
from .prep import _atempo_chain

SR = 48000
FMT = f"aformat=sample_rates={SR}:channel_layouts=stereo"
SILENT_ROLES = {"rewind", "freeze"}

CLIP_FX = {
    "echo": "aecho=0.8:0.7:250:0.4",
    "reverb": "aecho=0.8:0.6:60|120|190:0.4|0.3|0.2",
    "muffled": "lowpass=f=650,volume=0.85",
    "radio": "highpass=f=450,lowpass=f=3200,acompressor=threshold=0.1:ratio=6",
    "phone": "highpass=f=380,lowpass=f=3400",
    "pitch_up": f"asetrate={SR}*1.35,aresample={SR},atempo=0.7407",
    "pitch_down": f"asetrate={SR}*0.75,aresample={SR},atempo=1.3333",
    "bass_boost": "bass=g=8",
    "stereo_pan": "pan=stereo|c0=0.9*c0+0.3*c1|c1=0.25*c1",
}


def _volume_chain(plan: EditPlan, target: str) -> list[str]:
    out = []
    for v in plan.audio.volume:
        if v.target == target:
            out.append(f"volume={v.gain:.3f}:enable='between(t,{v.start:.3f},{v.end:.3f})'")
    return out


def build_soundtrack(plan: EditPlan, job_dir: Path, out_wav: Path, *, source_has_audio: bool = True) -> Path:
    total = plan.duration
    inputs: list[list[str]] = []
    graph: list[str] = []
    mix: list[str] = []

    def add_input(args: list[str]) -> int:
        inputs.append(args)
        return len(inputs) - 1

    clips = plan.clips
    n = len(clips)

    def segment_track(src_index: int, label: str, apply_fx: bool, gain_db: float = 0.0) -> str:
        """Cut an input exactly like the video timeline and concat."""
        graph.append(f"[{src_index}:a]{FMT},asplit={n}" + "".join(f"[{label}s{i}]" for i in range(n)))
        segs = []
        for i, c in enumerate(clips):
            d = c.duration
            chain = [f"[{label}s{i}]"]
            if c.role in SILENT_ROLES or c.freeze is not None:
                chain.append(f"atrim=0:{max(d, 0.01):.4f},volume=0")
            else:
                chain.append(f"atrim={c.src_in:.4f}:{c.src_out:.4f},asetpts=PTS-STARTPTS")
                if c.reverse:
                    chain.append(",areverse")
                if abs(c.speed - 1.0) > 1e-3:
                    chain.append("," + _atempo_chain(c.speed))
                if apply_fx:
                    for fx in plan.audio.clip_fx:
                        if fx.clip == c.id and fx.id in CLIP_FX:
                            chain.append("," + CLIP_FX[fx.id])
                        if fx.clip == c.id and fx.id == "tape_stop":
                            chain.append(f",afade=t=out:st={max(0, d - 0.6):.3f}:d=0.6")
                fade = min(0.012, d / 4)
                chain.append(f",afade=t=in:d={fade:.4f},afade=t=out:st={max(0, d - fade):.4f}:d={fade:.4f}")
            chain.append(f",apad=whole_dur={d:.4f},atrim=0:{d:.4f}[{label}c{i}]")
            graph.append("".join(chain))
            segs.append(f"[{label}c{i}]")
        out = f"{label}cat"
        graph.append("".join(segs) + f"concat=n={n}:v=0:a=1[{out}]")
        if gain_db:
            graph.append(f"[{out}]volume={gain_db:.1f}dB[{out}g]")
            out += "g"
        return out

    au = plan.audio
    voice_label = None
    if source_has_audio and n:
        voice_src = au.voice_source
        stems_dir = job_dir
        if voice_src == "vocals" and (stems_dir / "vocals.wav").exists():
            vi = add_input(["-i", str(stems_dir / "vocals.wav")])
            separated = True
        else:
            vi = add_input(["-i", plan.source])
            separated = False
        v = segment_track(vi, "v", apply_fx=True)
        proc = ["highpass=f=70"]
        if au.denoise and separated:
            proc.append("afftdn=nf=-25")
        if au.voice_enhance:
            proc += ["equalizer=f=3000:t=q:w=1.2:g=2.5", "acompressor=threshold=0.125:ratio=3:attack=8:release=120:makeup=1.5"]
        proc += _volume_chain(plan, "voice")
        graph.append(f"[{v}]{','.join(proc)},asplit=2[voice][voicesc]")
        voice_label = "voice"
        mix.append("[voice]")
        if au.bgm_source and Path(au.bgm_source).exists():
            bi = add_input(["-i", au.bgm_source])
            b = segment_track(bi, "b", apply_fx=False, gain_db=au.bgm_gain_db)
            chain = _volume_chain(plan, "bgm")
            if chain:
                graph.append(f"[{b}]{','.join(chain)}[bgm]")
                mix.append("[bgm]")
            else:
                mix.append(f"[{b}]")

    # ---- music
    music_labels = []
    for k, m in enumerate(au.music):
        mi = add_input(["-stream_loop", "-1", "-i", m.file])
        d = max(0.1, m.end - m.start)
        chain = [
            f"[{mi}:a]{FMT}", f"atrim=0:{d:.3f}", "asetpts=PTS-STARTPTS",
            f"afade=t=in:d={min(m.fade_in, d / 3):.2f}", f"afade=t=out:st={max(0, d - m.fade_out):.2f}:d={min(m.fade_out, d / 3):.2f}",
            f"volume={m.gain_db:.1f}dB", f"adelay={int(m.start * 1000)}|{int(m.start * 1000)}",
        ]
        graph.append(",".join(chain) + f"[m{k}]")
        music_labels.append(f"[m{k}]")
    if music_labels:
        if len(music_labels) > 1:
            graph.append("".join(music_labels) + f"amix=inputs={len(music_labels)}:normalize=0[musicraw]")
        else:
            graph.append(f"{music_labels[0]}anull[musicraw]")
        chain = _volume_chain(plan, "music")
        src = "musicraw"
        if chain:
            graph.append(f"[musicraw]{','.join(chain)}[musicv]")
            src = "musicv"
        if voice_label:
            ratio = max(2.0, min(20.0, abs(au.duck_db) / 1.5))
            graph.append(f"[{src}][voicesc]sidechaincompress=threshold=0.04:ratio={ratio:.1f}:attack=25:release=450[music]")
        else:
            graph.append(f"[{src}]anull[music]")
        mix.append("[music]")
    elif voice_label:
        graph.append("[voicesc]anullsink")

    # ---- sfx
    for k, s in enumerate(au.sfx):
        si = add_input(["-i", s.file])
        graph.append(f"[{si}:a]{FMT},volume={s.gain_db:.1f}dB,adelay={int(s.start * 1000)}|{int(s.start * 1000)}[x{k}]")
        mix.append(f"[x{k}]")

    if not mix:
        base = add_input(["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"])
        mix.append(f"[{base}:a]")

    # silence base guarantees full length
    base = add_input(["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"])
    mix.append(f"[{base}:a]")
    post = [f"amix=inputs={len(mix)}:normalize=0:duration=longest"]
    post += _volume_chain(plan, "all")
    post += [f"atrim=0:{total:.3f}", "alimiter=limit=0.95",
             f"loudnorm=I={au.loudness_lufs:.1f}:TP=-1.5:LRA=11", f"aresample={SR}"]
    graph.append("".join(mix) + ",".join(post) + "[out]")

    args: list[str] = []
    for i in inputs:
        args += i
    script = job_dir / "audio_graph.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    args += filter_script_args(script) + ["-map", "[out]", "-c:a", "pcm_s16le", str(out_wav)]
    log(f"Trộn âm thanh: giọng + {len(au.music)} nhạc + {len(au.sfx)} tiếng động...")
    run(args)
    return out_wav
