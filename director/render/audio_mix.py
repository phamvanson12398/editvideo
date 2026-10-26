"""Build the final soundtrack, robustly, in three steps:

1. Cut the voice (and original BGM stem) exactly like the video timeline: one small ffmpeg run per clip
   (cached), so a problem in one clip can never break the whole mix. A failing clip is retried without
   its audio effects, then replaced by silence of the same length (timeline stays in sync).
2. Join the clip pieces with the concat demuxer.
3. Mix voice + BGM + music (ducked under voice) + SFX + volume automation + loudness. If this graph fails,
   it is retried in simpler forms (no automation/ducking, then voice + SFX only).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..plan.schema import Clip, EditPlan
from ..utils.ffmpeg import FFmpegError, filter_script_args, run
from ..utils.log import log, pool_map, warn
from .prep import _atempo_chain

SR = 48000
FMT = f"aformat=sample_fmts=fltp:sample_rates={SR}:channel_layouts=stereo"
SILENT_ROLES = {"rewind", "freeze"}

CLIP_FX = {
    "echo": "aecho=0.8:0.7:250:0.4",
    "reverb": "aecho=0.8:0.6:60|120|190:0.4|0.3|0.2",
    "muffled": "lowpass=f=650,volume=0.85",
    "radio": "highpass=f=450,lowpass=f=3200,acompressor=threshold=0.1:ratio=6",
    "phone": "highpass=f=380,lowpass=f=3400",
    "pitch_up": f"asetrate={int(SR * 1.35)},aresample={SR},atempo=0.7407",
    "pitch_down": f"asetrate={int(SR * 0.75)},aresample={SR},atempo=1.3333",
    "bass_boost": "bass=g=8",
    "stereo_pan": "pan=stereo|c0=0.9*c0+0.3*c1|c1=0.25*c1",
}


def _volume_chain(plan: EditPlan, target: str) -> list[str]:
    out = []
    for v in plan.audio.volume:
        if v.target == target and v.end > v.start:
            out.append(f"volume={max(0.0, v.gain):.3f}:enable='between(t,{v.start:.3f},{v.end:.3f})'")
    return out


def _source_duration(path: str) -> float:
    from ..utils.ffmpeg import probe

    try:
        return float(probe(path)["format"].get("duration") or 0)
    except Exception:
        return 0.0


# ---------------------------------------------------------------- step 1-2: cut like the video


def _silence(d: float, dst: Path) -> None:
    run(["-f", "lavfi", "-t", f"{max(d, 0.01):.4f}", "-i", f"anullsrc=r={SR}:cl=stereo", "-c:a", "pcm_s16le", str(dst)])


def _clip_audio(src: str, src_len: float, clip: Clip, fx: list[str], dst: Path) -> None:
    d = clip.duration
    if clip.role in SILENT_ROLES or clip.freeze is not None:
        _silence(d, dst)
        return
    start = max(0.0, min(clip.src_in, max(0.0, src_len - 0.05))) if src_len else clip.src_in
    length = max(0.01, clip.src_out - clip.src_in)
    chain = [FMT]
    if clip.reverse:
        chain.append("areverse")
    if abs(clip.speed - 1.0) > 1e-3:
        chain.append(_atempo_chain(clip.speed))
    chain += fx
    fade = min(0.012, d / 4)
    chain += [f"afade=t=in:d={fade:.4f}", f"afade=t=out:st={max(0.0, d - fade):.4f}:d={fade:.4f}",
              f"apad=whole_dur={d:.4f}", f"atrim=0:{d:.4f}", FMT]
    run(["-ss", f"{start:.4f}", "-t", f"{length:.4f}", "-i", src, "-vn", "-af", ",".join(chain),
         "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)])


def cut_track(plan: EditPlan, src: str, work: Path, label: str, apply_fx: bool) -> Path:
    """Cut `src` like the video timeline into work/<label>.wav (pieces cached in work/<label>_parts)."""
    parts = work / f"{label}_parts"
    parts.mkdir(parents=True, exist_ok=True)
    src_len = _source_duration(src)

    def fx_for(c: Clip) -> list[str]:
        if not apply_fx:
            return []
        out = []
        for f in plan.audio.clip_fx:
            if f.clip != c.id:
                continue
            if f.id in CLIP_FX:
                out.append(CLIP_FX[f.id])
            elif f.id == "tape_stop":
                out.append(f"afade=t=out:st={max(0.0, c.duration - 0.6):.3f}:d=0.6")
        return out

    def work_one(item: tuple[int, Clip]) -> Path:
        i, c = item
        fx = fx_for(c)
        key = hashlib.sha1(json.dumps([src, c.src_in, c.src_out, c.speed, c.reverse, c.freeze, c.role, c.duration, fx]).encode()).hexdigest()[:16]
        dst = parts / f"{i:05d}_{key}.wav"
        if dst.exists() and dst.stat().st_size > 44:
            return dst
        try:
            _clip_audio(src, src_len, c, fx, dst)
        except FFmpegError as e:
            if fx:
                warn(f"Âm thanh đoạn {c.id}: hiệu ứng lỗi, bỏ hiệu ứng ({str(e).splitlines()[-1][:120]})")
                try:
                    _clip_audio(src, src_len, c, [], dst)
                    return dst
                except FFmpegError:
                    pass
            warn(f"Âm thanh đoạn {c.id} lỗi, thay bằng khoảng lặng để giữ khớp hình.")
            _silence(c.duration, dst)
        return dst

    pieces = pool_map(work_one, list(enumerate(plan.clips)), 4)
    listing = work / f"{label}_list.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in pieces), encoding="utf-8")
    out = work / f"{label}.wav"
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "pcm_s16le", str(out)])
    return out


# ---------------------------------------------------------------- step 3: mix


def _mix(plan: EditPlan, work: Path, out_wav: Path, voice: Path | None, bgm: Path | None, separated: bool, level: int) -> None:
    """level 0 = full, 1 = no automation/ducking/denoise, 2 = voice + sfx + loudnorm only."""
    au = plan.audio
    total = plan.duration
    inputs: list[list[str]] = []
    graph: list[str] = []
    mix: list[str] = []

    def add_input(args: list[str]) -> int:
        inputs.append(args)
        return len(inputs) - 1

    if voice is not None:
        vi = add_input(["-i", str(voice)])
        proc = [FMT, "highpass=f=70"]
        if level == 0 and au.denoise and separated:
            proc.append("afftdn=nf=-25")
        if level < 2 and au.voice_enhance:
            proc += ["equalizer=f=3000:t=q:w=1.2:g=2.5", "acompressor=threshold=0.125:ratio=3:attack=8:release=120:makeup=1.5"]
        if level == 0:
            proc += _volume_chain(plan, "voice")
        want_sc = level == 0 and bool(au.music)
        graph.append(f"[{vi}:a]{','.join(proc)}" + (",asplit=2[voice][voicesc]" if want_sc else "[voice]"))
        mix.append("[voice]")
        if bgm is not None and level < 2:
            bi = add_input(["-i", str(bgm)])
            chain = [FMT] + ([f"volume={au.bgm_gain_db:.1f}dB"] if au.bgm_gain_db else []) + (_volume_chain(plan, "bgm") if level == 0 else [])
            graph.append(f"[{bi}:a]{','.join(chain)}[bgm]")
            mix.append("[bgm]")
    else:
        want_sc = False

    if au.music and level < 2:
        labels = []
        for k, m in enumerate(au.music):
            mi = add_input(["-stream_loop", "-1", "-i", m.file])
            d = max(0.1, m.end - m.start)
            delay = int(m.start * 1000)
            graph.append(",".join([
                f"[{mi}:a]{FMT}", f"atrim=0:{d:.3f}", "asetpts=PTS-STARTPTS",
                f"afade=t=in:d={min(m.fade_in, d / 3):.2f}", f"afade=t=out:st={max(0, d - m.fade_out):.2f}:d={min(m.fade_out, d / 3):.2f}",
                f"volume={m.gain_db:.1f}dB", f"adelay={delay}|{delay}",
            ]) + f"[m{k}]")
            labels.append(f"[m{k}]")
        graph.append("".join(labels) + (f"amix=inputs={len(labels)}:normalize=0[musicraw]" if len(labels) > 1 else "anull[musicraw]"))
        src = "musicraw"
        chain = _volume_chain(plan, "music") if level == 0 else []
        if chain:
            graph.append(f"[musicraw]{','.join(chain)}[musicv]")
            src = "musicv"
        if want_sc:
            ratio = max(2.0, min(20.0, abs(au.duck_db) / 1.5))
            graph.append(f"[{src}][voicesc]sidechaincompress=threshold=0.04:ratio={ratio:.1f}:attack=25:release=450[music]")
        else:
            graph.append(f"[{src}]volume=-6dB[music]")
        mix.append("[music]")

    # SFX: one input per distinct file, split to every cue (keeps the input count small)
    by_file: dict[str, list] = {}
    for s in au.sfx:
        if Path(s.file).exists():
            by_file.setdefault(s.file, []).append(s)
    for fi, (f, cues) in enumerate(by_file.items()):
        si = add_input(["-i", f])
        n = len(cues)
        if n == 1:
            graph.append(f"[{si}:a]{FMT}[xs{fi}_0]")
        else:
            graph.append(f"[{si}:a]{FMT},asplit={n}" + "".join(f"[xs{fi}_{k}]" for k in range(n)))
        for k, s in enumerate(cues):
            delay = int(max(0.0, s.start) * 1000)
            graph.append(f"[xs{fi}_{k}]volume={s.gain_db:.1f}dB,adelay={delay}|{delay}[x{fi}_{k}]")
            mix.append(f"[x{fi}_{k}]")

    base = add_input(["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"])
    graph.append(f"[{base}:a]{FMT}[base]")
    mix.append("[base]")
    post = [f"amix=inputs={len(mix)}:normalize=0:duration=longest"]
    if level == 0:
        post += _volume_chain(plan, "all")
    post += [f"atrim=0:{total:.3f}", "alimiter=limit=0.95", f"loudnorm=I={au.loudness_lufs:.1f}:TP=-1.5:LRA=11", f"aresample={SR}"]
    graph.append("".join(mix) + ",".join(post) + "[out]")

    script = work / f"audio_graph_l{level}.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    args: list[str] = []
    for i in inputs:
        args += i
    args += filter_script_args(script) + ["-map", "[out]", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(out_wav)]
    run(args)


def build_soundtrack(plan: EditPlan, job_dir: Path, out_wav: Path, *, source_has_audio: bool = True) -> Path:
    au = plan.audio
    work = job_dir / "audio"
    work.mkdir(parents=True, exist_ok=True)
    voice = bgm = None
    separated = False
    log(f"Trộn âm thanh: giọng + {len(au.music)} nhạc + {len(au.sfx)} tiếng động...")
    if source_has_audio and plan.clips:
        vocals = job_dir / "vocals.wav"
        separated = au.voice_source == "vocals" and vocals.exists()
        voice = cut_track(plan, str(vocals) if separated else plan.source, work, "voice", apply_fx=True)
        if au.bgm_source and Path(au.bgm_source).exists():
            try:
                bgm = cut_track(plan, au.bgm_source, work, "bgm", apply_fx=False)
            except FFmpegError as e:
                warn(f"Không cắt được nhạc nền gốc, bỏ qua: {str(e).splitlines()[-1][:160]}")
    last: Exception | None = None
    for level in (0, 1, 2):
        try:
            _mix(plan, work, out_wav, voice, bgm, separated, level)
            if level:
                warn(f"Đã trộn âm thanh ở chế độ đơn giản (mức {level}) do bản đầy đủ lỗi.")
            return out_wav
        except FFmpegError as e:
            last = e
            warn(f"Trộn âm thanh mức {level} lỗi: {str(e).splitlines()[-1][:200]}")
    raise FFmpegError(f"Không trộn được âm thanh: {last}")
