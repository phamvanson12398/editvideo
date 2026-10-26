import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {easeInOut, envelope, peak, progress, rand} from '../lib/math';
import type {EditPlan, Effect} from '../types';

const Grain: React.FC<{opacity: number; seed: number}> = ({opacity, seed}) => (
  <svg width="100%" height="100%" style={{position: 'absolute', inset: 0, opacity, mixBlendMode: 'overlay'}}>
    <filter id={`grain${seed}`}>
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={seed} stitchTiles="stitch" />
      <feColorMatrix type="saturate" values="0" />
    </filter>
    <rect width="100%" height="100%" filter={`url(#grain${seed})`} />
  </svg>
);

const Scanlines: React.FC<{opacity: number; offset: number}> = ({opacity, offset}) => (
  <AbsoluteFill
    style={{
      opacity,
      backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,.35) 0px, rgba(0,0,0,.35) 2px, transparent 2px, transparent 5px)',
      backgroundPosition: `0 ${offset}px`,
    }}
  />
);

const pad2 = (n: number) => String(n).padStart(2, '0');

const One: React.FC<{e: Effect; t: number; W: number; H: number; frame: number}> = ({e, t, W, H, frame}) => {
  const P = e.params || {};
  const env = envelope(t, e.start, e.end, Math.min(0.25, (e.end - e.start) / 4), Math.min(0.3, (e.end - e.start) / 4));
  const p = progress(t, e.start, e.end);
  const u = Math.min(W, H);
  switch (e.id) {
    case 'vignette':
      return <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,${(P.amount ?? 0.5) * env}) 100%)`}} />;
    case 'tint':
      return <AbsoluteFill style={{background: P.color ?? '#ff0000', opacity: (P.amount ?? 0.25) * env, mixBlendMode: 'color'}} />;
    case 'day_to_night':
      return <AbsoluteFill style={{background: '#0a1a4a', opacity: 0.35 * env, mixBlendMode: 'multiply'}} />;
    case 'glow':
      return <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 40%, rgba(255,240,220,.45), transparent 70%)', opacity: env, mixBlendMode: 'screen'}} />;
    case 'dream':
      return <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 40%, rgba(255,255,255,.55) 100%)', opacity: env}} />;
    case 'light_rays': {
      const rot = (t - e.start) * 12;
      return (
        <AbsoluteFill style={{opacity: 0.55 * env, mixBlendMode: 'screen', overflow: 'hidden'}}>
          <div style={{position: 'absolute', left: '-50%', top: '-80%', width: '200%', height: '200%', transform: `rotate(${rot}deg)`, transformOrigin: '50% 0%',
            background: 'repeating-conic-gradient(from 0deg at 50% 0%, rgba(255,236,180,.55) 0deg 4deg, transparent 4deg 14deg)',
            maskImage: 'linear-gradient(to bottom, black 20%, transparent 90%)', WebkitMaskImage: 'linear-gradient(to bottom, black 20%, transparent 90%)'}} />
        </AbsoluteFill>
      );
    }
    case 'flicker':
      return <AbsoluteFill style={{background: '#000', opacity: rand(Math.floor(t * 18)) > 0.8 ? 0.45 * env : 0.08 * env}} />;
    case 'lightning': {
      const ph = p;
      const flash = ph < 0.08 || (ph > 0.18 && ph < 0.24) ? 1 : 0;
      return (
        <AbsoluteFill style={{background: `rgba(200,220,255,${0.55 * flash})`}}>
          {flash ? (
            <svg width={W} height={H} style={{position: 'absolute'}}>
              <polyline points={`${W * 0.62},0 ${W * 0.55},${H * 0.22} ${W * 0.63},${H * 0.24} ${W * 0.5},${H * 0.5}`} stroke="#fff" strokeWidth={u * 0.01} fill="none" style={{filter: 'drop-shadow(0 0 20px #9cf)'}} />
            </svg>
          ) : null}
        </AbsoluteFill>
      );
    }
    case 'film_grain':
      return <Grain opacity={0.22 * env} seed={frame % 9} />;
    case 'vhs': {
      const now = new Date(2026, 0, 1, 0, 0, Math.floor(t));
      return (
        <AbsoluteFill>
          <Scanlines opacity={0.35 * env} offset={frame * 2} />
          <Grain opacity={0.25 * env} seed={frame % 7} />
          <AbsoluteFill style={{background: 'linear-gradient(transparent 0%, rgba(255,255,255,.08) 50%, transparent 52%)', backgroundSize: `100% ${H * 0.25}px`, backgroundPosition: `0 ${(frame * 9) % H}px`}} />
          <div style={{position: 'absolute', left: u * 0.05, top: u * 0.05, color: '#fff', fontFamily: 'monospace', fontSize: u * 0.045, textShadow: '2px 2px 0 #000', opacity: env}}>
            {P.rewind ? '◀◀ REW' : '▶ PLAY'}
          </div>
          <div style={{position: 'absolute', left: u * 0.05, bottom: u * 0.06, color: '#fff', fontFamily: 'monospace', fontSize: u * 0.04, textShadow: '2px 2px 0 #000', opacity: env}}>
            {`${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`}
          </div>
        </AbsoluteFill>
      );
    }
    case 'old_film': {
      const lines = [0, 1, 2].map((i) => rand(Math.floor(t * 8) + i * 7.7));
      return (
        <AbsoluteFill>
          <Grain opacity={0.3 * env} seed={frame % 11} />
          {lines.map((r, i) => (r > 0.5 ? <div key={i} style={{position: 'absolute', left: r * W, top: 0, width: 2, height: H, background: 'rgba(255,255,255,.35)'}} /> : null))}
          <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 50%, rgba(40,20,0,.6) 100%)', opacity: env}} />
        </AbsoluteFill>
      );
    }
    case 'cctv': {
      const blink = Math.floor(t * 2) % 2 === 0;
      return (
        <AbsoluteFill>
          <Scanlines opacity={0.3 * env} offset={frame} />
          <AbsoluteFill style={{background: 'rgba(30,255,120,.08)', mixBlendMode: 'screen'}} />
          <div style={{position: 'absolute', left: u * 0.05, top: u * 0.05, color: '#fff', fontFamily: 'monospace', fontSize: u * 0.045, display: 'flex', alignItems: 'center', gap: u * 0.015}}>
            <span style={{width: u * 0.035, height: u * 0.035, borderRadius: '50%', background: blink ? '#f33' : 'transparent', display: 'inline-block'}} /> REC  CAM 02
          </div>
          <div style={{position: 'absolute', right: u * 0.05, bottom: u * 0.06, color: '#fff', fontFamily: 'monospace', fontSize: u * 0.04}}>{`2026-10-26 23:${pad2(Math.floor(t / 60) % 60)}:${pad2(Math.floor(t) % 60)}`}</div>
          <AbsoluteFill style={{border: `${u * 0.004}px solid rgba(255,255,255,.5)`, margin: u * 0.03}} />
        </AbsoluteFill>
      );
    }
    case 'security_red':
      return <AbsoluteFill style={{boxShadow: `inset 0 0 ${u * 0.12}px ${u * 0.03}px rgba(255,0,0,${(0.5 + 0.5 * Math.sin(t * 10)) * env})`}} />;
    case 'letterbox': {
      const ratio = P.ratio ?? 2.39;
      const bar = Math.max(0, (H - W / ratio) / 2) * easeInOut(env);
      return (
        <AbsoluteFill>
          <div style={{position: 'absolute', left: 0, top: 0, width: W, height: bar, background: '#000'}} />
          <div style={{position: 'absolute', left: 0, bottom: 0, width: W, height: bar, background: '#000'}} />
        </AbsoluteFill>
      );
    }
    case 'glitch':
    case 'glitch_cut': {
      const k = e.id === 'glitch_cut' ? peak(t, e.start, e.end) : env;
      const slices = [0, 1, 2, 3, 4].map((i) => ({y: rand(Math.floor(t * 30) + i * 3.3), h: 0.02 + 0.06 * rand(i * 9.1 + Math.floor(t * 30)), dx: (rand(i * 1.7 + Math.floor(t * 30)) - 0.5) * 0.2}));
      return (
        <AbsoluteFill style={{opacity: k}}>
          {slices.map((s, i) => (
            <div key={i} style={{position: 'absolute', left: s.dx * W, top: s.y * H, width: W, height: s.h * H, background: i % 2 ? 'rgba(0,255,255,.35)' : 'rgba(255,0,80,.35)', mixBlendMode: 'screen'}} />
          ))}
        </AbsoluteFill>
      );
    }
    case 'chromatic':
      return null;
    case 'radial_blur':
      return <AbsoluteFill style={{background: 'radial-gradient(circle, transparent 30%, rgba(255,255,255,.15) 100%)', opacity: env}} />;
    case 'comic_halftone':
      return (
        <AbsoluteFill style={{opacity: 0.35 * env, mixBlendMode: 'multiply',
          backgroundImage: 'radial-gradient(circle, #000 1.2px, transparent 1.6px)', backgroundSize: `${u * 0.012}px ${u * 0.012}px`}} />
      );
    case 'manga_freeze':
      return (
        <AbsoluteFill>
          <AbsoluteFill style={{opacity: 0.4, mixBlendMode: 'multiply', backgroundImage: 'radial-gradient(circle, #000 1.3px, transparent 1.7px)', backgroundSize: `${u * 0.011}px ${u * 0.011}px`}} />
          <AbsoluteFill style={{border: `${u * 0.02}px solid #111`, outline: `${u * 0.006}px solid #fff`, outlineOffset: -u * 0.03}} />
        </AbsoluteFill>
      );
    case 'impact_frame':
      return <AbsoluteFill style={{background: Math.floor((t - e.start) * 30) % 2 ? 'rgba(255,255,255,.35)' : 'transparent'}} />;
    default:
      return null;
  }
};

export const StylizeOverlays: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const active = plan.effects.filter((e) => (e.category === 'stylize' || e.category === 'color' || e.id === 'manga_freeze' || e.id === 'impact_frame' || e.id === 'glitch_cut' || e.id === 'comic_halftone') && t >= e.start && t <= e.end);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {active.map((e, i) => (
        <One key={`${e.id}-${i}`} e={e} t={t} W={W} H={H} frame={frame} />
      ))}
    </AbsoluteFill>
  );
};

