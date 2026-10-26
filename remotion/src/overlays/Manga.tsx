import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {anchorAt} from '../lib/anchor';
import {backOut, clamp, envelope, noise, progress, rand} from '../lib/math';
import type {EditPlan, Effect} from '../types';

type A = {x: number; y: number; size: number};

const FocusLines: React.FC<{W: number; H: number; a: A; t: number; dark?: boolean; opacity: number}> = ({W, H, a, t, dark, opacity}) => {
  const n = 90;
  const R = Math.hypot(W, H);
  const inner = a.size * 0.9;
  const polys: string[] = [];
  for (let i = 0; i < n; i++) {
    const ang = (i / n) * Math.PI * 2 + rand(i + Math.floor(t * 12)) * 0.05;
    const w = 0.004 + 0.012 * rand(i * 7.3 + Math.floor(t * 12));
    const r0 = inner * (1 + 0.6 * rand(i * 3.7 + Math.floor(t * 12)));
    const p1 = [a.x + Math.cos(ang - w) * R, a.y + Math.sin(ang - w) * R];
    const p2 = [a.x + Math.cos(ang + w) * R, a.y + Math.sin(ang + w) * R];
    const p0 = [a.x + Math.cos(ang) * r0, a.y + Math.sin(ang) * r0];
    polys.push(`${p0[0]},${p0[1]} ${p1[0]},${p1[1]} ${p2[0]},${p2[1]}`);
  }
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity}}>
      {polys.map((pts, i) => (
        <polygon key={i} points={pts} fill={dark ? '#000' : '#fff'} opacity={0.85} />
      ))}
    </svg>
  );
};

const SpeedLines: React.FC<{W: number; H: number; t: number; opacity: number}> = ({W, H, t, opacity}) => (
  <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity}}>
    {Array.from({length: 40}).map((_, i) => {
      const y = rand(i * 1.3) * H;
      const len = (0.2 + 0.5 * rand(i * 2.1)) * W;
      const x = ((rand(i * 4.4) * W + t * W * 3) % (W + len)) - len;
      return <rect key={i} x={x} y={y} width={len} height={1 + 4 * rand(i)} fill="#fff" opacity={0.7} />;
    })}
  </svg>
);

const AngerVein: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <svg width={s} height={s} viewBox="0 0 100 100" style={{position: 'absolute', left: x - s / 2, top: y - s / 2}}>
    {[0, 90, 180, 270].map((r) => (
      <path key={r} d="M50 50 C 55 30, 70 25, 75 12" stroke="#e8101a" strokeWidth={13} fill="none" strokeLinecap="round" transform={`rotate(${r} 50 50) translate(6 -6)`} />
    ))}
  </svg>
);

const SweatDrop: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <svg width={s * 0.6} height={s} viewBox="0 0 60 100" style={{position: 'absolute', left: x, top: y}}>
    <path d="M30 4 C 30 4, 56 50, 56 66 A 26 26 0 1 1 4 66 C 4 50, 30 4, 30 4 Z" fill="#9fdcff" stroke="#2b7bb9" strokeWidth={5} />
    <ellipse cx={20} cy={64} rx={6} ry={10} fill="#fff" opacity={0.8} />
  </svg>
);

const Star: React.FC<{x: number; y: number; s: number; rot: number; color?: string}> = ({x, y, s, rot, color = '#fff6a8'}) => (
  <svg width={s} height={s} viewBox="-50 -50 100 100" style={{position: 'absolute', left: x - s / 2, top: y - s / 2, transform: `rotate(${rot}deg)`}}>
    <path d="M0 -48 L10 -10 L48 0 L10 10 L0 48 L-10 10 L-48 0 L-10 -10 Z" fill={color} style={{filter: 'drop-shadow(0 0 6px #fff)'}} />
  </svg>
);

const Heart: React.FC<{x: number; y: number; s: number; opacity: number}> = ({x, y, s, opacity}) => (
  <svg width={s} height={s} viewBox="0 0 100 100" style={{position: 'absolute', left: x - s / 2, top: y - s / 2, opacity}}>
    <path d="M50 88 C 20 65, 4 48, 4 30 A 22 22 0 0 1 50 22 A 22 22 0 0 1 96 30 C 96 48, 80 65, 50 88 Z" fill="#ff4f8b" stroke="#fff" strokeWidth={4} />
  </svg>
);

const Glyph: React.FC<{x: number; y: number; s: number; text: string; color: string; rot?: number}> = ({x, y, s, text, color, rot = 0}) => (
  <div style={{position: 'absolute', left: x - s / 2, top: y - s / 2, width: s, height: s, display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: s, fontWeight: 900, fontFamily: 'Arial Black, Impact, sans-serif', color, transform: `rotate(${rot}deg)`,
    WebkitTextStroke: `${s * 0.06}px #000`, textShadow: `0 ${s * 0.05}px 0 #000`}}>
    {text}
  </div>
);

const One: React.FC<{e: Effect; t: number; W: number; H: number; a: A}> = ({e, t, W, H, a}) => {
  const p = progress(t, e.start, e.end);
  const env = envelope(t, e.start, e.end, 0.12, 0.2);
  const pop = backOut(clamp((t - e.start) / 0.25));
  const s = a.size;
  switch (e.id) {
    case 'focus_lines':
      return <FocusLines W={W} H={H} a={a} t={t} opacity={env} />;
    case 'shock_lines':
      return (
        <AbsoluteFill style={{opacity: env}}>
          <AbsoluteFill style={{background: 'rgba(10,10,40,.55)'}} />
          <svg width={W} height={H} style={{position: 'absolute'}}>
            {Array.from({length: 26}).map((_, i) => (
              <rect key={i} x={(i / 26) * W + noise('sl', i, t * 4) * 6} y={0} width={W * 0.006} height={H * (0.4 + 0.3 * rand(i))} fill="#cfd8ff" opacity={0.6} />
            ))}
          </svg>
        </AbsoluteFill>
      );
    case 'speed_lines':
      return <SpeedLines W={W} H={H} t={t} opacity={env} />;
    case 'anger_vein':
      return <div style={{opacity: env, transform: `scale(${0.6 + 0.4 * pop + 0.08 * Math.sin(t * 20)})`, transformOrigin: `${a.x + s * 0.45}px ${a.y - s * 0.45}px`, position: 'absolute', inset: 0}}><AngerVein x={a.x + s * 0.45} y={a.y - s * 0.45} s={s * 0.42} /></div>;
    case 'sweat_drop':
      return <div style={{opacity: env, position: 'absolute', inset: 0, transform: `translateY(${p * s * 0.25}px)`}}><SweatDrop x={a.x + s * 0.4} y={a.y - s * 0.6} s={s * 0.45} /></div>;
    case 'blush':
      return (
        <AbsoluteFill style={{opacity: 0.75 * env}}>
          {[-1, 1].map((d) => (
            <div key={d} style={{position: 'absolute', left: a.x + d * s * 0.28 - s * 0.14, top: a.y + s * 0.08, width: s * 0.28, height: s * 0.12, borderRadius: '50%',
              background: 'radial-gradient(ellipse, rgba(255,90,130,.85), rgba(255,90,130,0) 70%)'}} />
          ))}
        </AbsoluteFill>
      );
    case 'sparkle':
      return (
        <AbsoluteFill style={{opacity: env}}>
          {Array.from({length: 7}).map((_, i) => {
            const ang = rand(i * 3) * Math.PI * 2;
            const r = s * (0.6 + 0.5 * rand(i * 5));
            const tw = 0.5 + 0.5 * Math.sin(t * 10 + i * 2);
            return <Star key={i} x={a.x + Math.cos(ang) * r} y={a.y + Math.sin(ang) * r} s={s * 0.22 * tw} rot={t * 90 + i * 20} />;
          })}
        </AbsoluteFill>
      );
    case 'hearts':
      return (
        <AbsoluteFill>
          {Array.from({length: 9}).map((_, i) => {
            const delay = rand(i * 2.7) * 0.6;
            const q = clamp((t - e.start - delay) / Math.max(0.5, e.end - e.start - delay));
            if (q <= 0) return null;
            const x = a.x + (rand(i * 9.1) - 0.5) * s * 2 + Math.sin(q * 6 + i) * s * 0.15;
            const y = a.y - q * s * 1.8 + s * 0.2;
            return <Heart key={i} x={x} y={y} s={s * (0.18 + 0.12 * rand(i))} opacity={1 - q} />;
          })}
        </AbsoluteFill>
      );
    case 'gloom':
      return (
        <AbsoluteFill style={{opacity: env}}>
          <AbsoluteFill style={{background: 'rgba(20,20,60,.35)'}} />
          {Array.from({length: 12}).map((_, i) => (
            <div key={i} style={{position: 'absolute', left: a.x - s * 0.6 + (i / 12) * s * 1.2, top: a.y - s * 1.1, width: s * 0.02, height: s * (0.5 + 0.3 * rand(i)), background: 'rgba(40,40,80,.8)'}} />
          ))}
          <div style={{position: 'absolute', left: a.x - s * 0.6, top: a.y - s * 1.35, width: s * 1.2, height: s * 0.35, borderRadius: s, background: '#3b3f55', boxShadow: `${s * 0.2}px ${s * 0.05}px 0 #2d3044, ${-s * 0.25}px ${s * 0.04}px 0 #2d3044`}} />
        </AbsoluteFill>
      );
    case 'aura':
    case 'dark_aura': {
      const col = e.id === 'dark_aura' ? 'rgba(60,0,90,' : `rgba(255,90,30,`;
      const pulse = 1 + 0.08 * Math.sin(t * 14);
      return (
        <AbsoluteFill style={{opacity: env, mixBlendMode: e.id === 'dark_aura' ? 'multiply' : 'screen'}}>
          <div style={{position: 'absolute', left: a.x - s * 1.4 * pulse, top: a.y - s * 1.6 * pulse, width: s * 2.8 * pulse, height: s * 3.6 * pulse, borderRadius: '50%',
            background: `radial-gradient(ellipse, ${col}0) 30%, ${col}.75) 55%, ${col}0) 72%)`, filter: `blur(${s * 0.05}px)`}} />
        </AbsoluteFill>
      );
    }
    case 'tears_overlay':
      return (
        <AbsoluteFill style={{opacity: env}}>
          {[-1, 1].map((d) => (
            <div key={d} style={{position: 'absolute', left: a.x + d * s * 0.2 - s * 0.05, top: a.y, width: s * 0.1, height: s * (0.4 + 0.6 * p),
              background: 'linear-gradient(rgba(140,210,255,.95), rgba(140,210,255,0))', borderRadius: s * 0.05}} />
          ))}
        </AbsoluteFill>
      );
    case 'question_marks':
      return <div style={{opacity: env, position: 'absolute', inset: 0}}><Glyph x={a.x + s * 0.5} y={a.y - s * 0.75} s={s * 0.5 * pop} text="?" color="#ffd400" rot={-12} /><Glyph x={a.x + s * 0.85} y={a.y - s * 0.55} s={s * 0.35 * pop} text="?" color="#ffd400" rot={14} /></div>;
    case 'exclamation':
      return <div style={{opacity: env, position: 'absolute', inset: 0}}><Glyph x={a.x + s * 0.55} y={a.y - s * 0.7} s={s * 0.6 * pop} text="!!" color="#ff3b30" rot={-8} /></div>;
    case 'chibi_pop': {
      const box = Math.min(W, H) * 0.42 * pop;
      return (
        <div style={{position: 'absolute', left: W * 0.06, top: H * 0.1, width: box, height: box, borderRadius: '24%', overflow: 'hidden', border: `${box * 0.04}px solid #fff`,
          boxShadow: '0 12px 40px rgba(0,0,0,.5)', opacity: env, background: 'radial-gradient(circle,#fff6,#0000), repeating-conic-gradient(#ffd400 0 10deg,#ff9f0a 10deg 20deg)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: box * 0.5}}>
          😳
        </div>
      );
    }
    default:
      return null;
  }
};

export const MangaOverlays: React.FC<{plan: EditPlan; outputId: string}> = ({plan, outputId}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const active = plan.effects.filter((e) => e.category === 'manga' && t >= e.start && t <= e.end && !['impact_frame', 'manga_freeze', 'comic_halftone', 'screen_crack'].includes(e.id));
  if (active.length === 0) return null;
  const an = anchorAt(plan, outputId, t, W, H);
  const a: A = an ? {x: an.post.x, y: an.post.y, size: Math.max(Math.min(W, H) * 0.12, an.size)} : {x: W / 2, y: H * 0.4, size: Math.min(W, H) * 0.3};
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {active.map((e, i) => (
        <One key={`${e.id}-${i}`} e={e} t={t} W={W} H={H} a={a} />
      ))}
    </AbsoluteFill>
  );
};

