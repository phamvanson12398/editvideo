import type {Clip, EditPlan} from '../types';
import {applyCamera, Box, Camera, cameraAt, clipAt, containView, coverView, faceAt, mapPoint, View} from './view';

export const LETTERBOX_RATIO = 2.39;

/** In fit modes with burned-in text, the zoom is limited so the text never leaves the frame. */
export const protectHardsub = (plan: EditPlan, mode: string | undefined, cam: Camera, W: number): Camera => {
  if (!plan.hardsub || (mode !== 'fit-blur' && mode !== 'fit-pad')) return cam;
  const maxScale = Math.max(1, 0.98 / Math.max(0.2, plan.hardsub.w));
  return {...cam, scale: Math.min(cam.scale, maxScale), ox: W / 2, tx: Math.max(-W * 0.02, Math.min(W * 0.02, cam.tx))};
};

/** The main video box for a clip in an output (where the picture lands). */
export const viewForClip = (plan: EditPlan, clip: Clip, outputId: string, W: number, H: number, tClip: number): View => {
  const [sw, sh] = plan.source_size;
  const rf = clip.reframe[outputId] ?? {mode: 'center', keys: []};
  const full: Box = {x: 0, y: 0, w: W, h: H};
  switch (rf.mode) {
    case 'fit-blur':
    case 'fit-pad':
      return containView(sw, sh, full);
    case 'letterbox': {
      const bh = Math.min(H, W / LETTERBOX_RATIO);
      return coverView(sw, sh, {x: 0, y: (H - bh) / 2, w: W, h: bh}, rf.keys, tClip);
    }
    case 'split':
      return coverView(sw, sh, {x: 0, y: 0, w: W, h: H / 2}, rf.split_keys?.[0] ?? rf.keys, tClip);
    default:
      return coverView(sw, sh, full, rf.keys, tClip);
  }
};

/** Face anchor of the clip on screen at timeline time t: pre-camera point (for the camera origin)
 * and post-camera point (for overlays) plus face size in output pixels. */
export const anchorAt = (plan: EditPlan, outputId: string, t: number, W: number, H: number, prefer?: string | null) => {
  const clip = clipAt(plan, t);
  if (!clip) return null;
  const tClip = t - clip.start;
  const v = viewForClip(plan, clip, outputId, W, H, tClip);
  const f = faceAt(clip, tClip, prefer);
  if (!f) {
    return {pre: {x: v.box.x + v.box.w / 2, y: v.box.y + v.box.h * 0.42}, post: {x: W / 2, y: H * 0.42}, size: Math.min(W, H) * 0.3, found: false, view: v};
  }
  const pre = mapPoint(v, f.x + f.w / 2, f.y + f.h / 2);
  const size = f.w * plan.source_size[0] * v.k;
  const cam = protectHardsub(plan, clip.reframe[outputId]?.mode, cameraAt(plan, t, W, H, pre), W);
  const post = applyCamera(cam, pre.x, pre.y);
  return {pre, post, size: size * cam.scale, found: true, view: v};
};
