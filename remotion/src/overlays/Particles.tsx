import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {envelope, rand} from '../lib/math';
import type {EditPlan, Effect} from '../types';

type Cfg = {
  n: number;
  speed: [number, number]; // fraction of H per second (positive = falling)
  drift: number; // horizontal sway amplitude (fraction of W)
  size: [number, number]; // fraction of min(W,H)
  spin: number;
  render: (s: number, i: number, life: number) => React.ReactNode;
  rise?: boolean;
  blend?: React.CSSProperties['mixBlendMode'];
};

const CONFETTI = ['#ff3b30', '#ffd400', '#34c759', '#0a84ff', '#af52de', '#ff9500'];

const CFG: Record<string, Cfg> = {
  rain: {n: 140, speed: [1.6, 2.4], drift: 0.01, size: [0.03, 0.06], spin: 0,
    render: (s) => <div style={{width: Math.max(1, s * 0.05), height: s, background: 'linear-gradient(transparent, rgba(200,220,255,.75))', transform: 'rotate(12deg)'}} />},
  snow: {n: 90, speed: [0.08, 0.18], drift: 0.03, size: [0.006, 0.016], spin: 0,
    render: (s) => <div style={{width: s, height: s, borderRadius: '50%', background: '#fff', boxShadow: `0 0 ${s}px rgba(255,255,255,.8)`}} />},
  petals: {n: 40, speed: [0.12, 0.22], drift: 0.06, size: [0.02, 0.035], spin: 220,
    render: (s) => <div style={{width: s, height: s * 0.6, borderRadius: '70% 0 70% 0', background: 'linear-gradient(135deg,#ffd1dc,#ff8fab)'}} />},
  leaves: {n: 26, speed: [0.12, 0.2], drift: 0.08, size: [0.025, 0.04], spin: 160,
    render: (s, i) => <div style={{width: s, height: s * 0.55, borderRadius: '80% 0 80% 0', background: ['#d4791e', '#b5481c', '#e2a32b'][i % 3]}} />},
  dust: {n: 60, speed: [-0.02, 0.02], drift: 0.02, size: [0.002, 0.006], spin: 0, blend: 'screen',
    render: (s) => <div style={{width: s, height: s, borderRadius: '50%', background: 'rgba(255,240,200,.8)'}} />},
  fireflies: {n: 30, speed: [-0.04, 0.02], drift: 0.05, size: [0.006, 0.012], spin: 0, blend: 'screen',
    render: (s, i, life) => <div style={{width: s, height: s, borderRadius: '50%', background: '#fff59d', boxShadow: `0 0 ${s * 3}px ${s}px rgba(255,245,120,.7)`, opacity: 0.4 + 0.6 * Math.abs(Math.sin(life * 3 + i))}} />},
  confetti: {n: 110, speed: [0.35, 0.6], drift: 0.04, size: [0.008, 0.018], spin: 540,
    render: (s, i) => <div style={{width: s, height: s * 0.5, background: CONFETTI[i % CONFETTI.length]}} />},
  fire_embers: {n: 70, speed: [-0.35, -0.18], drift: 0.03, size: [0.003, 0.008], spin: 0, rise: true, blend: 'screen',
    render: (s) => <div style={{width: s, height: s, borderRadius: '50%', background: '#ffb347', boxShadow: `0 0 ${s * 2}px #ff5a1f`}} />},
  smoke: {n: 14, speed: [-0.06, -0.03], drift: 0.04, size: [0.25, 0.45], spin: 20, rise: true,
    render: (s) => <div style={{width: s, height: s, borderRadius: '50%', background: 'radial-gradient(circle, rgba(60,60,70,.45), transparent 70%)'}} />},
  bubbles: {n: 30, speed: [-0.2, -0.1], drift: 0.03, size: [0.015, 0.04], spin: 0, rise: true,
    render: (s) => <div style={{width: s, height: s, borderRadius: '50%', border: `${Math.max(1, s * 0.06)}px solid rgba(255,255,255,.8)`, background: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,.6), transparent 40%)'}} />},
  money_rain: {n: 36, speed: [0.25, 0.4], drift: 0.05, size: [0.05, 0.08], spin: 300,
    render: (s) => <div style={{width: s, height: s * 0.48, background: 'linear-gradient(135deg,#7bd389,#2e8b57)', border: '2px solid #1b5e20', borderRadius: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: s * 0.3, fontWeight: 900, color: '#0b3d17'}}>$</div>},
};

const One: React.FC<{e: Effect; t: number; W: number; H: number}> = ({e, t, W, H}) => {
  const cfg = CFG[e.id];
  if (!cfg) return null;
  const env = envelope(t, e.start, e.end, 0.4, 0.5);
  const density = e.params?.density ?? 1;
  const n = Math.round(cfg.n * density);
  const u = Math.min(W, H);
  const life = t - e.start;
  return (
    <AbsoluteFill style={{opacity: env, mixBlendMode: cfg.blend}}>
      {Array.from({length: n}).map((_, i) => {
        const r1 = rand(i * 1.37 + e.start);
        const r2 = rand(i * 2.71 + 3);
        const r3 = rand(i * 4.13 + 7);
        const sp = cfg.speed[0] + (cfg.speed[1] - cfg.speed[0]) * r2;
        const size = (cfg.size[0] + (cfg.size[1] - cfg.size[0]) * r3) * u;
        let y = (r1 * (H + size * 2) + sp * H * life) % (H + size * 2);
        if (y < 0) y += H + size * 2;
        y -= size;
        const x = rand(i * 9.7) * W + Math.sin(life * (0.8 + r2) + i) * cfg.drift * W;
        const rot = cfg.spin * life * (r3 - 0.5) * 2;
        return (
          <div key={i} style={{position: 'absolute', left: x, top: y, transform: `rotate(${rot}deg)`}}>
            {cfg.render(size, i, life)}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const ParticleOverlays: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const active = plan.effects.filter((e) => e.category === 'particles' && t >= e.start && t <= e.end);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {active.map((e, i) => (
        <One key={`${e.id}-${i}`} e={e} t={t} W={W} H={H} />
      ))}
    </AbsoluteFill>
  );
};
