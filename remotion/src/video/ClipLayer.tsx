import React from 'react';
import {AbsoluteFill, Freeze, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {anchorAt, LETTERBOX_RATIO, protectHardsub, viewForClip} from '../lib/anchor';
import {videoFilter} from '../lib/filters';
import {progress} from '../lib/math';
import {Box, cameraAt, cameraCss, containView, coverView, faceAt, videoRect, View} from '../lib/view';
import type {Clip, EditPlan, Effect} from '../types';
import {overlapStyle} from './overlap';

type Props = {
  plan: EditPlan;
  clip: Clip;
  outputId: string;
  tin?: Effect; // incoming overlap transition (this clip appears)
  tout?: Effect; // outgoing overlap transition (this clip leaves)
};

const LAYOUT_IDS = [
  'phone_frame', 'tv_frame', 'split_vertical', 'split_horizontal', 'pip', 'reaction_split',
  'before_after', 'grid', 'panel_split', 'mirror', 'kaleidoscope', 'pixelate',
];

export const ClipLayer: React.FC<Props> = ({plan, clip, outputId, tin, tout}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const seqStart = clip.start - clip.handle_pre;
  const t = seqStart + frame / fps; // timeline time
  const tClip = t - clip.start;
  const end = clip.start + clip.duration;

  let style: React.CSSProperties = {};
  if (t < clip.start) {
    if (!tin || t < tin.start) return null;
    style = overlapStyle(tin.id, progress(t, tin.start, tin.end), 'in', W, H, tin.params);
  } else if (t >= end) {
    if (!tout || t > tout.end) return null;
    style = overlapStyle(tout.id, progress(t, tout.start, tout.end), 'out', W, H, tout.params);
  } else if (tin && t <= tin.end) {
    style = overlapStyle(tin.id, progress(t, tin.start, tin.end), 'in', W, H, tin.params);
  } else if (tout && t >= tout.start) {
    style = overlapStyle(tout.id, progress(t, tout.start, tout.end), 'out', W, H, tout.params);
  }

  const [sw, sh] = plan.source_size;
  const rf = clip.reframe[outputId] ?? {mode: 'center', keys: []};
  const mainView = viewForClip(plan, clip, outputId, W, H, tClip);
  const anchor = anchorAt(plan, outputId, Math.min(Math.max(t, clip.start), end - 1e-3), W, H);
  const cam = cameraAt(plan, t, W, H, anchor?.pre);
  const filter = videoFilter(plan, t, cam.blur);
  const layouts = plan.effects.filter((e) => LAYOUT_IDS.includes(e.id) && t >= e.start && t <= e.end);

  // Freeze for manga_freeze / freeze_wipe (outgoing)
  const freezeFx = plan.effects.find((e) => e.id === 'manga_freeze' && t >= e.start && t <= e.end);
  let freezeAt: number | null = null;
  if (freezeFx) freezeAt = Math.round((freezeFx.start - seqStart) * fps);
  if (tout && tout.id === 'freeze_wipe' && t >= tout.start) freezeAt = Math.round((tout.start - seqStart) * fps);

  const src = staticFile(clip.file);
  const video = (v: View, key: string, extra: React.CSSProperties = {}) => {
    const r = videoRect(v);
    const el = (
      <OffthreadVideo
        src={src}
        muted
        style={{position: 'absolute', left: r.left, top: r.top, width: r.width, height: r.height, ...extra}}
      />
    );
    return (
      <React.Fragment key={key}>
        {freezeAt !== null ? <Freeze frame={Math.max(0, freezeAt)}>{el}</Freeze> : el}
      </React.Fragment>
    );
  };

  const box = (x: number, y: number, w: number, h: number): Box => ({x, y, w, h});
  const keys = rf.keys;
  const face = faceAt(clip, tClip);
  const faceKeys = face ? [{t: 0, cx: face.x + face.w / 2, cy: face.y + face.h / 2, zoom: 1}] : keys;

  let content: React.ReactNode;
  const layout = layouts[0];
  if (layout) {
    switch (layout.id) {
      case 'split_vertical':
      case 'split_horizontal': {
        const vert = layout.id === 'split_vertical';
        const b1 = vert ? box(0, 0, W, H / 2) : box(0, 0, W / 2, H);
        const b2 = vert ? box(0, H / 2, W, H / 2) : box(W / 2, 0, W / 2, H);
        const faces = clip.faces.find((f) => Math.abs(f.t - tClip) < 1)?.boxes ?? [];
        const k1 = faces[0] ? [{t: 0, cx: faces[0].x + faces[0].w / 2, cy: faces[0].y + faces[0].h / 2, zoom: 1.2}] : keys;
        const k2 = faces[1] ? [{t: 0, cx: faces[1].x + faces[1].w / 2, cy: faces[1].y + faces[1].h / 2, zoom: 1.2}] : [{t: 0, cx: 0.5, cy: 0.5, zoom: 1.4}];
        content = (
          <>
            <div style={{position: 'absolute', ...b1, left: b1.x, top: b1.y, overflow: 'hidden'}}>{video(coverView(sw, sh, {...b1, x: 0, y: 0}, k1, tClip), 'a')}</div>
            <div style={{position: 'absolute', left: b2.x, top: b2.y, width: b2.w, height: b2.h, overflow: 'hidden'}}>{video(coverView(sw, sh, {...b2, x: 0, y: 0}, k2, tClip), 'b')}</div>
            <div style={{position: 'absolute', left: vert ? 0 : W / 2 - 3, top: vert ? H / 2 - 3 : 0, width: vert ? W : 6, height: vert ? 6 : H, background: '#fff'}} />
          </>
        );
        break;
      }
      case 'pip':
      case 'reaction_split': {
        const pip = layout.id === 'pip';
        const pw = pip ? W * 0.34 : W;
        const ph = pip ? pw : H * 0.3;
        const px = pip ? W - pw - W * 0.05 : 0;
        const py = pip ? H * 0.12 : H - ph;
        content = (
          <>
            {video(mainView, 'main')}
            <div style={{position: 'absolute', left: px, top: py, width: pw, height: ph, overflow: 'hidden', borderRadius: pip ? '50%' : 0, border: `${Math.round(W * 0.008)}px solid #fff`, boxShadow: '0 10px 40px rgba(0,0,0,.5)'}}>
              {video(coverView(sw, sh, box(0, 0, pw, ph), faceKeys.map((k) => ({...k, zoom: 1.6})), tClip), 'pip')}
            </div>
          </>
        );
        break;
      }
      case 'before_after': {
        const p = progress(t, layout.start, layout.end);
        const x = W * (0.15 + 0.7 * p);
        content = (
          <>
            {video(mainView, 'after')}
            <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${W - x}px 0 0)`, filter: 'grayscale(1) brightness(.85)'}}>{video(mainView, 'before')}</div>
            <div style={{position: 'absolute', left: x - 3, top: 0, width: 6, height: H, background: '#fff', boxShadow: '0 0 20px #000'}} />
          </>
        );
        break;
      }
      case 'grid': {
        const cells = [0, 1, 2, 3];
        content = (
          <>
            {cells.map((i) => {
              const b = box((i % 2) * (W / 2), Math.floor(i / 2) * (H / 2), W / 2, H / 2);
              return (
                <div key={i} style={{position: 'absolute', left: b.x, top: b.y, width: b.w, height: b.h, overflow: 'hidden', outline: '3px solid #fff'}}>
                  {video(coverView(sw, sh, {...b, x: 0, y: 0}, [{t: 0, cx: 0.3 + 0.4 * (i % 2), cy: 0.35 + 0.3 * Math.floor(i / 2), zoom: 1 + 0.15 * i}], tClip), `g${i}`)}
                </div>
              );
            })}
          </>
        );
        break;
      }
      case 'panel_split': {
        const panels = [box(0, 0, W * 0.6, H * 0.5), box(W * 0.6, 0, W * 0.4, H * 0.5), box(0, H * 0.5, W, H * 0.5)];
        content = (
          <AbsoluteFill style={{background: '#fff'}}>
            {panels.map((b, i) => (
              <div key={i} style={{position: 'absolute', left: b.x + 8, top: b.y + 8, width: b.w - 16, height: b.h - 16, overflow: 'hidden', border: '6px solid #111'}}>
                {video(coverView(sw, sh, {...b, x: 0, y: 0, w: b.w - 16, h: b.h - 16}, [{t: 0, cx: [0.35, 0.65, 0.5][i], cy: 0.45, zoom: [1.3, 1.6, 1][i]}], tClip), `p${i}`)}
              </div>
            ))}
          </AbsoluteFill>
        );
        break;
      }
      case 'mirror': {
        content = (
          <>
            <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${W / 2}px 0 0)`}}>{video(mainView, 'l')}</div>
            <div style={{position: 'absolute', inset: 0, transform: 'scaleX(-1)', clipPath: `inset(0 ${W / 2}px 0 0)`}}>{video(mainView, 'r')}</div>
          </>
        );
        break;
      }
      case 'kaleidoscope': {
        const q = [
          {t: '', c: `inset(0 ${W / 2}px ${H / 2}px 0)`},
          {t: 'scaleX(-1)', c: `inset(0 ${W / 2}px ${H / 2}px 0)`},
          {t: 'scaleY(-1)', c: `inset(0 ${W / 2}px ${H / 2}px 0)`},
          {t: 'scale(-1,-1)', c: `inset(0 ${W / 2}px ${H / 2}px 0)`},
        ];
        content = (
          <>
            {q.map((s, i) => (
              <div key={i} style={{position: 'absolute', inset: 0, transform: s.t, clipPath: s.c}}>{video(mainView, `k${i}`)}</div>
            ))}
          </>
        );
        break;
      }
      case 'pixelate': {
        const f = 18;
        const small = viewForClip(plan, clip, outputId, W / f, H / f, tClip);
        content = (
          <div style={{position: 'absolute', left: 0, top: 0, width: W / f, height: H / f, transform: `scale(${f})`, transformOrigin: '0 0', imageRendering: 'pixelated', overflow: 'hidden'}}>
            {video(small, 'px', {imageRendering: 'pixelated'})}
          </div>
        );
        break;
      }
      case 'phone_frame':
      case 'tv_frame': {
        const phone = layout.id === 'phone_frame';
        const fw = phone ? Math.min(W * 0.78, H * 0.46) : W * 0.86;
        const fh = phone ? fw * 2.05 : fw * 0.72;
        const fx = (W - fw) / 2;
        const fy = (H - fh) / 2;
        const inner = phone ? box(fx + fw * 0.05, fy + fh * 0.04, fw * 0.9, fh * 0.92) : box(fx + fw * 0.06, fy + fh * 0.08, fw * 0.72, fh * 0.84);
        content = (
          <AbsoluteFill style={{background: phone ? 'linear-gradient(160deg,#1d2b64,#f8cdda)' : '#2b1d0e'}}>
            <div style={{position: 'absolute', left: fx, top: fy, width: fw, height: fh, borderRadius: phone ? fw * 0.12 : fw * 0.04, background: phone ? '#0b0b0b' : '#6b4a2b', boxShadow: '0 30px 80px rgba(0,0,0,.6)'}} />
            <div style={{position: 'absolute', left: inner.x, top: inner.y, width: inner.w, height: inner.h, overflow: 'hidden', borderRadius: phone ? fw * 0.08 : fw * 0.05}}>
              {video(coverView(sw, sh, {...inner, x: 0, y: 0}, keys, tClip), 'scr')}
            </div>
            {!phone && <div style={{position: 'absolute', left: fx + fw * 0.82, top: fy + fh * 0.2, width: fw * 0.1, height: fw * 0.1, borderRadius: '50%', background: '#c9a26b'}} />}
          </AbsoluteFill>
        );
        break;
      }
      default:
        content = video(mainView, 'main');
    }
  } else if (rf.mode === 'fit-blur' || rf.mode === 'fit-pad') {
    const bg = coverView(sw, sh, box(0, 0, W, H), [{t: 0, cx: 0.5, cy: 0.5}], tClip);
    // Keep burned-in text fully visible: limit zoom and keep it centred horizontally.
    const fgCam = protectHardsub(plan, rf.mode, cam, W);
    const bgRect = videoRect(bg);
    content = (
      <>
        {rf.mode === 'fit-blur' ? (
          <OffthreadVideo src={staticFile(clip.file.replace(/\.mp4$/, '_bg.mp4'))} muted
            style={{position: 'absolute', left: bgRect.left, top: bgRect.top, width: bgRect.width, height: bgRect.height, transform: 'scale(1.08)'}} />
        ) : (
          <AbsoluteFill style={{background: '#111'}} />
        )}
        <div style={{position: 'absolute', inset: 0, ...cameraCss(fgCam), filter}}>{video(containView(sw, sh, box(0, 0, W, H)), 'fg')}</div>
      </>
    );
    return <AbsoluteFill style={{overflow: 'hidden', ...style}}>{content}</AbsoluteFill>;
  } else if (rf.mode === 'split') {
    const tracks = rf.split_keys ?? [keys, keys];
    content = (
      <>
        {[0, 1].map((i) => (
          <div key={i} style={{position: 'absolute', left: 0, top: (i * H) / 2, width: W, height: H / 2, overflow: 'hidden'}}>
            {video(coverView(sw, sh, box(0, 0, W, H / 2), tracks[i] ?? keys, tClip), `s${i}`)}
          </div>
        ))}
        <div style={{position: 'absolute', left: 0, top: H / 2 - 3, width: W, height: 6, background: '#fff'}} />
      </>
    );
  } else if (rf.mode === 'letterbox') {
    const bh = Math.min(H, W / LETTERBOX_RATIO);
    content = (
      <>
        <AbsoluteFill style={{background: '#000'}} />
        <div style={{position: 'absolute', left: 0, top: (H - bh) / 2, width: W, height: bh, overflow: 'hidden'}}>
          {video(coverView(sw, sh, box(0, 0, W, bh), keys, tClip), 'lb')}
        </div>
      </>
    );
  } else {
    content = video(mainView, 'main');
  }

  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#000', ...style}}>
      <div style={{position: 'absolute', inset: 0, ...cameraCss(cam), filter}}>{content}</div>
    </AbsoluteFill>
  );
};


