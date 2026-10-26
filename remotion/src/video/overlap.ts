import type React from 'react';
import {clamp, easeInOut, easeOut} from '../lib/math';

const heartPolygon = (cx: number, cy: number, s: number) => {
  const pts: string[] = [];
  for (let i = 0; i < 48; i++) {
    const a = (i / 48) * Math.PI * 2;
    const x = 16 * Math.pow(Math.sin(a), 3);
    const y = -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a));
    pts.push(`${(cx + (x / 17) * s).toFixed(1)}px ${(cy + (y / 17) * s).toFixed(1)}px`);
  }
  return `polygon(${pts.join(',')})`;
};

const starPolygon = (cx: number, cy: number, s: number) => {
  const pts: string[] = [];
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
    const r = i % 2 === 0 ? s : s * 0.45;
    pts.push(`${(cx + Math.cos(a) * r).toFixed(1)}px ${(cy + Math.sin(a) * r).toFixed(1)}px`);
  }
  return `polygon(${pts.join(',')})`;
};

/** Style for a clip taking part in an overlap transition. p in [0,1]. */
export const overlapStyle = (
  id: string,
  p: number,
  role: 'in' | 'out',
  W: number,
  H: number,
  params: Record<string, any>,
): React.CSSProperties => {
  const dir = params.direction === 'right' ? -1 : params.direction === 'up' ? 2 : params.direction === 'down' ? -2 : 1;
  const e = easeOut(p);
  const horizontal = Math.abs(dir) === 1;
  const sign = Math.sign(dir);
  switch (id) {
    case 'crossfade':
      return role === 'in' ? {opacity: easeInOut(p)} : {};
    case 'slide':
      if (role === 'out') return {};
      return {transform: horizontal ? `translateX(${(1 - e) * W * sign}px)` : `translateY(${(1 - e) * H * sign}px)`};
    case 'push':
      if (role === 'in') return {transform: horizontal ? `translateX(${(1 - e) * W * sign}px)` : `translateY(${(1 - e) * H * sign}px)`};
      return {transform: horizontal ? `translateX(${-e * W * sign}px)` : `translateY(${-e * H * sign}px)`};
    case 'wipe':
    case 'freeze_wipe': {
      if (role === 'out') return {};
      if (params.shape === 'circle') return {clipPath: `circle(${(e * Math.hypot(W, H)) / 2}px at 50% 50%)`};
      const x = (1 - easeInOut(p)) * 100;
      return {clipPath: sign > 0 ? `inset(0 0 0 ${x}%)` : `inset(0 ${x}% 0 0)`};
    }
    case 'iris':
      if (role === 'out') return {};
      return {clipPath: `circle(${(easeInOut(p) * Math.hypot(W, H)) / 2}px at 50% 50%)`};
    case 'shape_mask': {
      if (role === 'out') return {};
      const s = Math.pow(easeInOut(p), 1.6) * Math.hypot(W, H) * 1.1;
      return {clipPath: params.shape === 'star' ? starPolygon(W / 2, H / 2, s) : heartPolygon(W / 2, H / 2, s)};
    }
    case 'page_turn':
      if (role === 'in') return {};
      return {
        transform: `perspective(${W * 1.5}px) rotateY(${-easeInOut(p) * 100}deg)`,
        transformOrigin: '0% 50%',
        zIndex: 5,
        boxShadow: `0 0 ${60 * p}px rgba(0,0,0,${0.6 * p})`,
        opacity: p > 0.9 ? 1 - (p - 0.9) * 10 : 1,
      };
    case 'manga_panel': {
      if (role === 'out') return {};
      const steps = 3;
      const k = Math.min(steps, Math.floor(p * steps * 1.15) + 1) / steps;
      const x = k * (W + 0.3 * H);
      return {clipPath: `polygon(0px 0px, ${x}px 0px, ${x - 0.3 * H}px ${H}px, 0px ${H}px)`};
    }
    case 'shatter':
      if (role === 'in') return {};
      return {
        transform: `translateY(${easeOut(p) * H * 0.25}px) rotate(${p * 6}deg) scale(${1 + 0.08 * p})`,
        opacity: clamp(1 - p * 1.3),
        zIndex: 5,
      };
    default:
      return role === 'in' ? {opacity: p} : {};
  }
};
