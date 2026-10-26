import type {EditPlan} from '../types';
import {envelope, noise, rand} from './math';

/** CSS filter for the video layer from active color/stylize effects. */
export const videoFilter = (plan: EditPlan, t: number, extraBlur = 0): string => {
  const parts: string[] = [];
  let blur = extraBlur;
  for (const e of plan.effects) {
    if (t < e.start || t > e.end) continue;
    const P = e.params || {};
    const env = envelope(t, e.start, e.end, Math.min(0.25, (e.end - e.start) / 4), Math.min(0.3, (e.end - e.start) / 4));
    switch (e.id) {
      case 'desaturate':
        parts.push(`saturate(${1 - (P.amount ?? 0.6) * env})`);
        break;
      case 'black_white':
        parts.push(`grayscale(${env}) contrast(${1 + 0.15 * env})`);
        break;
      case 'sepia':
        parts.push(`sepia(${0.85 * env})`);
        break;
      case 'day_to_night':
        parts.push(`brightness(${1 - 0.4 * env}) saturate(${1 - 0.4 * env}) hue-rotate(${-15 * env}deg)`);
        break;
      case 'glow':
        parts.push(`brightness(${1 + 0.08 * env}) saturate(${1 + 0.1 * env}) contrast(${1 - 0.06 * env})`);
        break;
      case 'dream':
        parts.push(`brightness(${1 + 0.1 * env}) saturate(${1 - 0.15 * env})`);
        blur += 0.8 * env;
        break;
      case 'invert':
      case 'impact_frame': {
        const frame = Math.floor((t - e.start) * 30);
        parts.push(frame % 2 === 0 ? 'invert(1) grayscale(1) contrast(3)' : 'grayscale(1) contrast(4) brightness(1.2)');
        break;
      }
      case 'manga_freeze':
        parts.push('grayscale(1) contrast(1.9) brightness(1.1)');
        break;
      case 'blur':
        blur += (P.amount ?? 8) * env;
        break;
      case 'radial_blur':
        blur += 5 * env;
        break;
      case 'chromatic':
      case 'glitch':
      case 'glitch_cut':
        parts.push('url(#chroma)');
        break;
      case 'vhs':
        parts.push(`saturate(1.35) contrast(1.1) url(#chroma)`);
        blur += 0.6;
        break;
      case 'old_film':
        parts.push(`sepia(0.6) contrast(1.15) brightness(${0.95 + 0.08 * noise('of', t * 12, 0)})`);
        break;
      case 'cctv':
        parts.push('grayscale(0.9) contrast(1.3) brightness(0.95)');
        blur += 0.4;
        break;
      case 'flicker': {
        const f = rand(Math.floor(t * 18) + 3.1);
        parts.push(`brightness(${f > 0.75 ? 0.35 : 0.85 + 0.2 * f})`);
        break;
      }
      case 'lightning': {
        const ph = (t - e.start) / (e.end - e.start);
        const flash = ph < 0.08 || (ph > 0.18 && ph < 0.24) ? 1 : 0;
        parts.push(`brightness(${1 + 1.5 * flash}) contrast(${1 + 0.4 * flash})`);
        break;
      }
      case 'comic_halftone':
        parts.push('contrast(1.25) saturate(1.3)');
        break;
      default:
        break;
    }
  }
  if (blur > 0.05) parts.push(`blur(${blur.toFixed(2)}px)`);
  return parts.join(' ');
};
