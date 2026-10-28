"""Render every visual effect one after another on a sample video (smoke test for the Remotion layer).

usage: python tests/showcase.py SAMPLE.mp4 OUT_DIR [--only cat1,cat2] [--frame 9:16]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from director.effects.catalog import EFFECTS
from director.perception.analyze import analyze
from director.plan.compiler import compile_plan
from director.plan.frames import parse_frames
from director.plan.schema import DraftClip, DraftEffect, DraftTransition, PlanDraft
from director.render.audio_mix import build_soundtrack
from director.render.prep import prepare_clips
from director.render.remotion import render_output
from director.style.presets import get_preset
from director.utils.ffmpeg import run

VISUAL = {"overlap", "tx", "camera", "color", "stylize", "manga", "particles", "text", "layout"}
SKIP = {"lut", "auto_color", "match_color", "sharpen", "upscale", "progress_bar", "episode_badge", "watermark",
        "fit_blur", "fit_pad", "stacked_title", "color_pop"}
TEXT_DEFAULTS = {
    "title_slam": "BÍ MẬT ĐỘNG TRỜI", "title_reveal": "Tập 12", "title_split": "PHẦN 2", "kinetic_type": "Con không phải con ruột",
    "lower_third": "Tiểu Mai", "character_card": "Mẹ chồng", "chapter_card": "Chương 3", "question_hook": "Vì sao cô ấy bỏ đi?",
    "warning_label": "PHẢN DIỆN", "arrow_callout": "Manh mối", "continue_card": "Còn tiếp...", "cta": "Theo dõi để xem tiếp!",
    "end_screen": "Cảm ơn đã xem!", "sfx_text": "RẦM!", "time_skip": "3 ngày sau...",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--only")
    ap.add_argument("--frame", default="9:16")
    ap.add_argument("--seg", type=float, default=1.6)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    idx = analyze(a.video, out / "job", separate=False)
    cats = set(a.only.split(",")) if a.only else VISUAL
    ids = [e.id for e in EFFECTS.values() if e.category in cats and e.id not in SKIP]
    D = idx.source.duration
    seg = a.seg
    clips, effects, transitions = [], [], []
    t = 0.5
    for i, eid in enumerate(ids):
        if t + seg > D - 0.5:
            t = 0.5
        clips.append(DraftClip(src_in=round(t, 3), src_out=round(t + seg, 3)))
        e = EFFECTS[eid]
        params = {}
        if eid in TEXT_DEFAULTS:
            params["text"] = TEXT_DEFAULTS[eid]
        if eid == "relationship_map":
            params = {"nodes": [{"id": "a", "label": "Mai"}, {"id": "b", "label": "Mẹ"}, {"id": "c", "label": "Bố"}],
                      "edges": [{"a": "a", "b": "b", "label": "mẹ con"}, {"a": "b", "b": "c", "label": "vợ chồng"}]}
        if eid == "fake_chat":
            params = {"messages": [{"text": "Con đang ở đâu?"}, {"text": "Con về ngay đây", "me": True}]}
        if e.category in ("overlap", "tx") and i > 0:
            transitions.append(DraftTransition(after_clip=i - 1, id=eid, dur=min(0.8, e.dur or 0.5)))
            effects.append(DraftEffect(id="title_reveal", clip=i, at=t + 0.05, dur=seg - 0.1, params={"text": eid}))
        else:
            effects.append(DraftEffect(id=eid, clip=i, at=t + 0.05, dur=seg - 0.1, params=params))
            if e.category != "text":
                effects.append(DraftEffect(id="lower_third", clip=i, at=t + 0.05, dur=seg - 0.1, params={"text": eid, "subtitle": e.name}))
        t += seg
    draft = PlanDraft(clips=clips, effects=effects, transitions=transitions)
    style = get_preset("anime-drama")
    style.audio.sfx = False
    outputs = parse_frames([a.frame], idx.source.width, idx.source.height)
    for o in outputs:
        o.width //= 2
        o.height //= 2
    plan = compile_plan(draft, idx, style, outputs)
    (out / "showcase.plan.json").write_text(plan.model_dump_json(indent=1), encoding="utf-8")
    index = [{"t": round(c.start, 2), "effect": ids[i]} for i, c in enumerate(plan.clips) if i < len(ids)]
    (out / "showcase_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = out / "job" / "render"
    prepare_clips(plan, pub, draft=True)
    vid = render_output(plan, outputs[0].id, pub, out / "showcase_video.mp4", draft=False)
    mix = build_soundtrack(plan, out / "job", out / "mix.wav")
    run(["-i", str(vid), "-i", str(mix), "-c:v", "copy", "-c:a", "aac", "-shortest", str(out / "showcase.mp4")])
    print(out / "showcase.mp4", len(ids), "effects")


if __name__ == "__main__":
    main()
