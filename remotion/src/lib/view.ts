import type {Clip, EditPlan, Effect, FaceBoxT, ReframeKey} from '../types';
import {backOut, clamp, easeInOut, easeOut, envelope, lerp, noise, peak, progress} from './math';

export type Box = {x: number; y: number; w: number; h: number};

/** Crop of box aspect that fits the source (source-normalized units). */
export const cropSize = (sw: number, sh: number, boxW: number, boxH: number) => {
  const aSrc = sw / sh;
  const aBox = boxW / boxH;
  return aBox < aSrc ? {cw: aBox / aSrc, ch: 1} : {cw: 1, ch: aSrc / aBox};
};

export const interpKeys = (keys: ReframeKey[], t: number): {cx: number; cy: number; zoom: number} => {
  if (!keys || keys.length === 0) return {cx: 0.5, cy: 0.5, zoom: 1};
  if (t <= keys[0].t) return {cx: keys[0].cx, cy: keys[0].cy, zoom: keys[0].zoom ?? 1};
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (t >= a.t && t <= b.t) {
      const p = easeInOut(b.t === a.t ? 1 : (t - a.t) / (b.t - a.t));
      return {cx: lerp(a.cx, b.cx, p), cy: lerp(a.cy, b.cy, p), zoom: lerp(a.zoom ?? 1, b.zoom ?? 1, p)};
    }
  }
  const l = keys[keys.length - 1];
  return {cx: l.cx, cy: l.cy, zoom: l.zoom ?? 1};
};

/** How the source maps into a target box: k = px per source px, (cx, cy) source-normalized center. */
export type View = {k: number; cx: number; cy: number; box: Box; sw: number; sh: number; contain: boolean};

export const coverView = (sw: number, sh: number, box: Box, keys: ReframeKey[], tClip: number): View => {
  const {cw, ch} = cropSize(sw, sh, box.w, box.h);
  const {cx, cy, zoom} = interpKeys(keys, tClip);
  const z = Math.max(1, zoom);
  const cwe = cw / z;
  const che = ch / z;
  const k = box.w / (cwe * sw);
  return {
    k,
    cx: clamp(cx, cwe / 2, 1 - cwe / 2),
    cy: clamp(cy, che / 2, 1 - che / 2),
    box,
    sw,
    sh,
    contain: false,
  };
};

export const containView = (sw: number, sh: number, box: Box): View => ({
  k: Math.min(box.w / sw, box.h / sh),
  cx: 0.5,
  cy: 0.5,
  box,
  sw,
  sh,
  contain: true,
});

/** Source-normalized point -> output pixels (before camera transform). */
export const mapPoint = (v: View, px: number, py: number) => ({
  x: v.box.x + v.box.w / 2 + (px - v.cx) * v.sw * v.k,
  y: v.box.y + v.box.h / 2 + (py - v.cy) * v.sh * v.k,
});

/** CSS placement of the full source frame for a view. */
export const videoRect = (v: View) => {
  const w = v.sw * v.k;
  const h = v.sh * v.k;
  return {
    left: v.box.x + v.box.w / 2 - v.cx * w,
    top: v.box.y + v.box.h / 2 - v.cy * h,
    width: w,
    height: h,
  };
};

export const faceAt = (clip: Clip, tClip: number, prefer?: string | null): FaceBoxT | null => {
  const faces = clip.faces;
  if (!faces || faces.length === 0) return null;
  let best = faces[0];
  for (const f of faces) {
    if (Math.abs(f.t - tClip) < Math.abs(best.t - tClip)) best = f;
  }
  if (Math.abs(best.t - tClip) > 1.2 || best.boxes.length === 0) return null;
  if (prefer) {
    const m = best.boxes.find((b) => b.character === prefer);
    if (m) return m;
  }
  return best.boxes.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a));
};

export const activeAt = (plan: EditPlan, t: number, cats?: string[]) =>
  plan.effects.filter((e) => t >= e.start && t <= e.end && (!cats || cats.includes(e.category)));

export const clipAt = (plan: EditPlan, t: number): Clip | undefined => {
  for (const c of plan.clips) {
    if (t >= c.start && t < c.start + c.duration) return c;
  }
  return plan.clips[plan.clips.length - 1];
};

export type Camera = {scale: number; tx: number; ty: number; rot: number; blur: number; ox: number; oy: number};

const FPS_NOISE = 9;

/** Combined camera transform at timeline time t for a box of size W x H.
 * anchor: output-pixel focus point (e.g. the face) used as transform origin. */
export const cameraAt = (plan: EditPlan, t: number, W: number, H: number, anchor?: {x: number; y: number}): Camera => {
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let rot = 0;
  let blur = 0;
  const ox = anchor?.x ?? W / 2;
  const oy = anchor?.y ?? H / 2;
  for (const e of plan.effects) {
    if (t < e.start - 0.001 || t > e.end + 0.001) continue;
    const p = progress(t, e.start, e.end);
    const P = e.params || {};
    const d = e.end - e.start;
    switch (e.id) {
      case 'punch_in':
      case 'reaction_zoom': {
        const s = P.scale ?? (e.id === 'reaction_zoom' ? 1.4 : 1.25);
        const a = Math.min(0.12, d / 3);
        const env = envelope(t, e.start, e.end, a, Math.min(0.18, d / 3));
        scale *= 1 + (s - 1) * (P.hold ? 1 : env);
        break;
      }
      case 'zoom_hold':
        scale *= P.scale ?? 1.08;
        break;
      case 'snap_zoom': {
        const steps = P.steps ?? 3;
        const s = P.scale ?? 1.5;
        const k = Math.min(steps, Math.floor(p * steps * 1.6) + 1);
        const rel = envelope(t, e.start, e.end, 0, 0.12);
        scale *= 1 + ((s - 1) * k * rel) / steps;
        break;
      }
      case 'slow_push':
        scale *= 1 + ((P.scale ?? 1.15) - 1) * easeInOut(p);
        break;
      case 'slow_pull':
        scale *= 1 + ((P.scale ?? 1.15) - 1) * (1 - easeInOut(p));
        break;
      case 'ken_burns': {
        const s = P.scale ?? 1.12;
        scale *= 1 + (s - 1) * p;
        const dir = ((Math.floor(e.start * 7) % 4) + 4) % 4;
        const amt = 0.03 * p;
        tx += [1, -1, 0, 0][dir] * amt * W;
        ty += [0, 0, 1, -1][dir] * amt * H;
        break;
      }
      case 'parallax_3d':
        scale *= 1 + ((P.scale ?? 1.1) - 1) * p;
        tx += (p - 0.5) * 0.04 * W;
        break;
      case 'pan': {
        const amt = (P.amount ?? 0.15) * (p - 0.5);
        const dir = P.direction ?? 'right';
        if (dir === 'right') tx -= amt * W;
        else if (dir === 'left') tx += amt * W;
        else if (dir === 'down') ty -= amt * H;
        else ty += amt * H;
        scale *= 1 + (P.amount ?? 0.15);
        break;
      }
      case 'dolly_zoom':
        scale *= 1 + 0.3 * easeInOut(p);
        blur += 0.6 * peak(t, e.start, e.end);
        break;
      case 'shake': {
        const intensity = (P.intensity ?? 0.5) * (1 - p * 0.7);
        const n1 = noise('sx' + e.start, t * FPS_NOISE * 2, 0);
        const n2 = noise('sy' + e.start, 0, t * FPS_NOISE * 2);
        tx += n1 * intensity * 0.04 * W;
        ty += n2 * intensity * 0.04 * H;
        rot += noise('sr' + e.start, t * FPS_NOISE, t) * intensity * 2.2;
        scale *= 1 + 0.06 * intensity;
        break;
      }
      case 'handheld': {
        const intensity = P.intensity ?? 0.15;
        tx += noise('hx', t * 0.8, 0) * intensity * 0.03 * W;
        ty += noise('hy', 0, t * 0.8) * intensity * 0.03 * H;
        rot += noise('hr', t * 0.5, 1) * intensity * 1.5;
        scale *= 1 + 0.04 * intensity + 0.02;
        break;
      }
      case 'impact_bump':
        scale *= 1 + ((P.scale ?? 1.06) - 1) * Math.sin(Math.PI * p);
        break;
      case 'dutch_angle':
      case 'tilt': {
        const ang = P.angle ?? (e.id === 'tilt' ? 4 : 8);
        rot += ang * envelope(t, e.start, e.end, 0.3, 0.3);
        scale *= 1 + Math.abs(ang) * 0.012;
        break;
      }
      case 'rotate_wobble':
        rot += (P.angle ?? 5) * Math.sin(2 * Math.PI * p * 3) * envelope(t, e.start, e.end, 0.2, 0.2);
        scale *= 1.06;
        break;
      case 'split_focus':
        scale *= 1.25;
        tx += (easeInOut(p) - 0.5) * 0.2 * W;
        break;
      // ---- transitions done with transforms around a cut
      case 'whip_pan': {
        const dir = P.direction === 'right' ? -1 : 1;
        const half = p < 0.5;
        const k = half ? easeIn(p * 2) : 1 - easeOut((p - 0.5) * 2);
        tx += (half ? -1 : 1) * dir * k * W * 0.6;
        blur += 18 * k;
        break;
      }
      case 'zoom_blur': {
        const k = peak(t, e.start, e.end);
        scale *= p < 0.5 ? 1 + 0.8 * easeIn(p * 2) : 1 + 0.8 * (1 - easeOut((p - 0.5) * 2));
        blur += 14 * k;
        break;
      }
      case 'zoom_in_out': {
        scale *= p < 0.5 ? 1 + 0.5 * easeIn(p * 2) : 1.5 - 0.5 * easeOut((p - 0.5) * 2);
        blur += 6 * peak(t, e.start, e.end);
        break;
      }
      case 'spin':
        rot += 360 * easeInOut(p);
        scale *= 1 + 0.4 * peak(t, e.start, e.end);
        blur += 6 * peak(t, e.start, e.end);
        break;
      case 'glitch_cut':
      case 'glitch':
        if (Math.floor(t * 30) % 3 === 0) tx += (noise('g', t * 50, 0) * 0.04) * W;
        break;
      default:
        break;
    }
  }
  return {scale, tx, ty, rot, blur, ox, oy};
};

const easeIn = (t: number) => Math.pow(clamp(t), 2);
export {backOut};

export const cameraCss = (c: Camera) => ({
  transform: `translate(${c.tx}px, ${c.ty}px) rotate(${c.rot}deg) scale(${c.scale})`,
  transformOrigin: `${c.ox}px ${c.oy}px`,
});

/** Output-pixel position of a source-normalized point after the camera transform. */
export const applyCamera = (c: Camera, x: number, y: number) => {
  const rad = (c.rot * Math.PI) / 180;
  const dx = (x - c.ox) * c.scale;
  const dy = (y - c.oy) * c.scale;
  return {
    x: c.ox + dx * Math.cos(rad) - dy * Math.sin(rad) + c.tx,
    y: c.oy + dx * Math.sin(rad) + dy * Math.cos(rad) + c.ty,
  };
};

export const effectsOf = (plan: EditPlan, ids: string[]) => plan.effects.filter((e: Effect) => ids.includes(e.id));
