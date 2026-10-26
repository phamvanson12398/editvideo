import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp, easeInOut, peak, progress, rand} from '../lib/math';
import type {EditPlan, Effect} from '../types';

export const Cracks: React.FC<{W: number; H: number; p: number; cx?: number; cy?: number}> = ({W, H, p, cx = 0.5, cy = 0.45}) => {
  const lines: string[] = [];
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI * 2 + rand(i) * 0.4;
    let x = cx * W;
    let y = cy * H;
    const pts = [`${x},${y}`];
    const len = (0.3 + 0.5 * rand(i * 3.1)) * Math.hypot(W, H) * clamp(p * 1.6);
    for (let k = 1; k <= 5; k++) {
      x += Math.cos(a + (rand(i * 10 + k) - 0.5) * 0.6) * (len / 5);
      y += Math.sin(a + (rand(i * 10 + k) - 0.5) * 0.6) * (len / 5);
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    lines.push(pts.join(' '));
  }
  const u = Math.min(W, H);
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      {lines.map((pts, i) => (
        <polyline key={i} points={pts} fill="none" stroke="rgba(255,255,255,.9)" strokeWidth={u * 0.004} style={{filter: 'drop-shadow(0 0 3px #000)'}} />
      ))}
      <circle cx={cx * W} cy={cy * H} r={u * 0.03 * clamp(p * 3)} fill="rgba(255,255,255,.6)" />
    </svg>
  );
};

const One: React.FC<{e: Effect; t: number; W: number; H: number}> = ({e, t, W, H}) => {
  const P = e.params || {};
  const p = progress(t, e.start, e.end);
  const k = peak(t, e.start, e.end);
  const u = Math.min(W, H);
  switch (e.id) {
    case 'flash_white':
      return <AbsoluteFill style={{background: '#fff', opacity: Math.pow(k, 0.6)}} />;
    case 'fade_black':
    case 'fade_white':
    case 'dip_color':
      return <AbsoluteFill style={{background: P.color ?? (e.id === 'fade_white' ? '#fff' : '#000'), opacity: easeInOut(k * 1.15)}} />;
    case 'film_burn':
      return (
        <AbsoluteFill style={{mixBlendMode: 'screen', opacity: k}}>
          <AbsoluteFill style={{background: `radial-gradient(circle at ${30 + 40 * p}% ${60 - 20 * p}%, rgba(255,170,40,1), rgba(255,60,0,.8) 25%, transparent 60%)`}} />
          <AbsoluteFill style={{background: `radial-gradient(circle at ${80 - 30 * p}% 30%, rgba(255,230,150,.9), transparent 40%)`}} />
        </AbsoluteFill>
      );
    case 'light_leak':
      return (
        <AbsoluteFill style={{mixBlendMode: 'screen', opacity: 0.9 * k,
          background: `linear-gradient(${110 + 60 * p}deg, rgba(255,120,60,.0) 10%, rgba(255,150,80,.9) 40%, rgba(255,220,150,.7) 55%, rgba(255,80,120,0) 85%)`}} />
      );
    case 'ink_bleed': {
      const r = Math.pow(k, 1.6) * Math.hypot(W, H) * 0.6;
      const blobs = [0, 1, 2, 3, 4, 5].map((i) => ({x: (0.2 + 0.6 * rand(i * 2.2)) * W, y: (0.2 + 0.6 * rand(i * 5.3)) * H, s: 0.6 + 0.5 * rand(i)}));
      return (
        <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
          <filter id="inkf"><feTurbulence baseFrequency="0.02" numOctaves={3} seed={3} /><feDisplacementMap in="SourceGraphic" scale={u * 0.08} /></filter>
          <g filter="url(#inkf)">
            {blobs.map((b, i) => (<circle key={i} cx={b.x} cy={b.y} r={r * b.s} fill="#0b0b0b" />))}
          </g>
        </svg>
      );
    }
    case 'shatter':
    case 'screen_crack':
      return (
        <AbsoluteFill>
          <Cracks W={W} H={H} p={e.id === 'shatter' ? p : Math.min(1, p * 4)} />
          {e.id === 'screen_crack' && p < 0.12 ? <AbsoluteFill style={{background: '#fff', opacity: 0.6}} /> : null}
        </AbsoluteFill>
      );
    case 'zoom_blur':
    case 'whip_pan':
      return <AbsoluteFill style={{background: 'radial-gradient(circle, transparent 40%, rgba(255,255,255,.18))', opacity: k}} />;
    default:
      return null;
  }
};

export const TxOverlays: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const active = plan.effects.filter((e) => (e.category === 'tx' || e.category === 'overlap' || e.id === 'screen_crack') && t >= e.start && t <= e.end);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {active.map((e, i) => (
        <One key={`${e.id}-${i}`} e={e} t={t} W={W} H={H} />
      ))}
    </AbsoluteFill>
  );
};
