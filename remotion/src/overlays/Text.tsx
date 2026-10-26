import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {anchorAt} from '../lib/anchor';
import {TITLE_FONT, useFontFamily} from '../lib/fonts';
import {backOut, clamp, easeInOut, easeOut, envelope, noise} from '../lib/math';
import type {EditPlan, Effect, SafeZone} from '../types';

type Ctx = {W: number; H: number; u: number; font: string; t: number; safe: SafeZone; plan: EditPlan; outputId: string};

const stroke = (px: number, color = '#000') => ({
  WebkitTextStroke: `${px}px ${color}`,
  paintOrder: 'stroke fill' as const,
  textShadow: `0 ${px}px ${px * 2}px rgba(0,0,0,.45)`,
});

const Title: React.FC<{e: Effect; c: Ctx}> = ({e, c}) => {
  const {W, H, u, font, t} = c;
  const P = e.params || {};
  const text: string = P.text || '';
  if (!text) return null;
  const local = t - e.start;
  const env = envelope(t, e.start, e.end, 0.08, 0.25);
  const size = Math.min(u * 0.13, (W * 0.88) / Math.max(4, text.length * 0.55));
  const top = c.safe.top * H + H * 0.06;
  let transform = '';
  let extra: React.CSSProperties = {};
  if (e.id === 'title_slam') {
    const s = local < 0.18 ? 2.6 - 1.6 * easeOut(local / 0.18) : 1 + 0.02 * Math.sin(local * 6);
    const shake = local < 0.45 ? noise('ts', local * 40, 0) * u * 0.012 * (1 - local / 0.45) : 0;
    transform = `translate(${shake}px, 0) scale(${s}) rotate(-3deg)`;
  } else if (e.id === 'title_reveal') {
    const p = easeInOut(clamp(local / 0.8));
    extra = {clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`};
  } else if (e.id === 'title_split') {
    const p = 1 - easeOut(clamp(local / 0.5));
    extra = {letterSpacing: `${p * 0.5}em`};
  } else if (e.id === 'kinetic_type') {
    const words = text.split(/\s+/);
    return (
      <div style={{position: 'absolute', left: W * 0.06, right: W * 0.06, top: H * 0.3, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: u * 0.02, opacity: env}}>
        {words.map((w, i) => {
          const wt = clamp((local - i * 0.18) / 0.22);
          return (
            <span key={i} style={{fontFamily: font, fontWeight: 900, fontSize: size * (i % 3 === 1 ? 1.25 : 0.9), color: i % 3 === 1 ? '#FFD400' : '#fff', transform: `translateY(${(1 - backOut(wt)) * u * 0.08}px) scale(${0.6 + 0.4 * backOut(wt)})`, opacity: wt, display: 'inline-block', ...stroke(size * 0.06)}}>
              {w}
            </span>
          );
        })}
      </div>
    );
  }
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center', opacity: env}}>
      <div style={{fontFamily: font, fontWeight: 900, fontSize: size, color: P.color || '#FFFFFF', textAlign: 'center', lineHeight: 1.05, maxWidth: W * 0.9, transform, textTransform: 'uppercase', ...stroke(size * 0.07), ...extra}}>
        {text}
      </div>
    </div>
  );
};

const Card: React.FC<{e: Effect; c: Ctx}> = ({e, c}) => {
  const {W, H, u, font, t} = c;
  const P = e.params || {};
  const local = t - e.start;
  const env = envelope(t, e.start, e.end, 0.25, 0.3);
  const slide = 1 - easeOut(clamp(local / 0.35));
  const color = P.color || '#FFD400';
  switch (e.id) {
    case 'lower_third':
    case 'character_card':
    case 'freeze_intro': {
      const big = e.id !== 'lower_third';
      const y = big ? H * 0.58 : H * (1 - c.safe.bottom) - u * 0.26;
      return (
        <div style={{position: 'absolute', left: W * 0.06, top: y, opacity: env, transform: `translateX(${-slide * W * 0.6}px)`}}>
          <div style={{background: color, height: u * 0.012, width: u * (big ? 0.5 : 0.3), marginBottom: u * 0.012}} />
          <div style={{fontFamily: font, fontWeight: 900, fontSize: u * (big ? 0.11 : 0.07), color: '#fff', ...stroke(u * 0.006)}}>{P.text}</div>
          {P.subtitle ? <div style={{fontFamily: font, fontWeight: 700, fontSize: u * (big ? 0.05 : 0.04), color, ...stroke(u * 0.004)}}>{P.subtitle}</div> : null}
        </div>
      );
    }
    case 'chapter_card':
    case 'time_skip': {
      const isSkip = e.id === 'time_skip';
      return (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: env, background: isSkip ? 'transparent' : 'rgba(0,0,0,.55)'}}>
          <div style={{fontFamily: font, fontWeight: isSkip ? 700 : 900, fontStyle: isSkip ? 'italic' : 'normal', fontSize: u * (isSkip ? 0.075 : 0.1), color: '#fff',
            letterSpacing: `${0.02 + slide * 0.2}em`, padding: `${u * 0.02}px ${u * 0.05}px`, background: isSkip ? 'rgba(0,0,0,.55)' : 'transparent', borderRadius: u * 0.02, ...stroke(u * 0.004)}}>
            {P.text || ''}
          </div>
        </AbsoluteFill>
      );
    }
    case 'question_hook':
      return (
        <div style={{position: 'absolute', left: W * 0.06, right: W * 0.06, top: c.safe.top * H + H * 0.05, display: 'flex', justifyContent: 'center', opacity: env}}>
          <div style={{fontFamily: font, fontWeight: 900, fontSize: u * 0.075, color: '#111', background: '#FFD400', padding: `${u * 0.02}px ${u * 0.035}px`, borderRadius: u * 0.025,
            transform: `scale(${0.7 + 0.3 * backOut(clamp(local / 0.3))}) rotate(-2deg)`, textAlign: 'center', boxShadow: '0 10px 30px rgba(0,0,0,.4)'}}>
            {P.text}
          </div>
        </div>
      );
    case 'countdown': {
      const from = P.from ?? 3;
      const n = Math.max(1, from - Math.floor(local / ((e.end - e.start) / from)));
      const k = (local % ((e.end - e.start) / from)) / ((e.end - e.start) / from);
      return (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: font, fontWeight: 900, fontSize: u * 0.35, color: '#fff', transform: `scale(${1.6 - 0.6 * easeOut(k)})`, opacity: 1 - k * 0.6, ...stroke(u * 0.012)}}>{n}</div>
        </AbsoluteFill>
      );
    }
    case 'warning_label':
      return (
        <div style={{position: 'absolute', left: 0, right: 0, top: H * 0.16, display: 'flex', justifyContent: 'center', opacity: env}}>
          <div style={{fontFamily: font, fontWeight: 900, fontSize: u * 0.07, color: '#fff', background: '#d70015', padding: `${u * 0.015}px ${u * 0.04}px`, border: `${u * 0.008}px solid #fff`,
            transform: `scale(${1 + 0.05 * Math.sin(local * 12)}) rotate(-4deg)`, boxShadow: '0 0 40px rgba(255,0,0,.6)', letterSpacing: '0.08em'}}>
            ⚠ {P.text || ''}
          </div>
        </div>
      );
    case 'continue_card':
    case 'end_screen':
    case 'cta': {
      if (e.id === 'cta') {
        return (
          <div style={{position: 'absolute', left: 0, right: 0, bottom: H * (c.safe.bottom + 0.06), display: 'flex', justifyContent: 'center', opacity: env}}>
            <div style={{display: 'flex', alignItems: 'center', gap: u * 0.025, background: '#ff0033', color: '#fff', fontFamily: font, fontWeight: 800, fontSize: u * 0.055,
              padding: `${u * 0.022}px ${u * 0.045}px`, borderRadius: u * 0.06, transform: `scale(${0.8 + 0.2 * backOut(clamp(local / 0.35))})`, boxShadow: '0 10px 30px rgba(0,0,0,.4)'}}>
              <span>🔔</span> {P.text || ''}
            </div>
          </div>
        );
      }
      return (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', background: `rgba(0,0,0,${0.55 * env})`}}>
          <div style={{fontFamily: font, fontWeight: 900, fontStyle: 'italic', fontSize: u * 0.11, color: '#fff', opacity: env, transform: `translateY(${slide * u * 0.1}px)`, ...stroke(u * 0.006)}}>
            {P.text || ''}
          </div>
        </AbsoluteFill>
      );
    }
    case 'fake_chat': {
      const msgs: {from?: string; text: string; me?: boolean}[] = P.messages?.length ? P.messages : [{text: P.text || '...'}];
      return (
        <div style={{position: 'absolute', left: W * 0.08, right: W * 0.08, top: H * 0.2, display: 'flex', flexDirection: 'column', gap: u * 0.02, opacity: env}}>
          {msgs.map((m, i) => {
            const appear = clamp((local - i * 0.6) / 0.25);
            return (
              <div key={i} style={{alignSelf: m.me ? 'flex-end' : 'flex-start', maxWidth: '80%', background: m.me ? '#0a84ff' : '#e9e9eb', color: m.me ? '#fff' : '#111',
                fontFamily: font, fontWeight: 600, fontSize: u * 0.045, padding: `${u * 0.018}px ${u * 0.03}px`, borderRadius: u * 0.04, transform: `scale(${appear})`, opacity: appear}}>
                {m.text}
              </div>
            );
          })}
        </div>
      );
    }
    default:
      return null;
  }
};

const Anchored: React.FC<{e: Effect; c: Ctx}> = ({e, c}) => {
  const {W, H, u, font, t} = c;
  const P = e.params || {};
  const local = t - e.start;
  const env = envelope(t, e.start, e.end, 0.05, 0.2);
  const an = anchorAt(c.plan, c.outputId, t, W, H);
  const ax = an ? an.post.x : W / 2;
  const ay = an ? an.post.y : H * 0.4;
  const fs = an ? Math.max(u * 0.1, an.size * 0.5) : u * 0.15;
  switch (e.id) {
    case 'sfx_text': {
      const s = backOut(clamp(local / 0.2));
      return (
        <div style={{position: 'absolute', left: clamp(ax + fs * 0.6, fs, W - fs * 2), top: clamp(ay - fs * 1.4, H * 0.08, H * 0.8), opacity: env,
          transform: `scale(${s}) rotate(-10deg)`, fontFamily: font, fontWeight: 900, fontSize: fs, color: '#FFD400', ...stroke(fs * 0.08, '#d70015')}}>
          {P.text || ''}
        </div>
      );
    }
    case 'emoji_pop': {
      const s = backOut(clamp(local / 0.25));
      return (
        <div style={{position: 'absolute', left: clamp(ax + fs * 0.5, 0, W - fs), top: clamp(ay - fs * 1.3, 0, H - fs), fontSize: fs * 0.9, opacity: env,
          transform: `scale(${s}) translateY(${-local * u * 0.03}px)`}}>
          {P.emoji || '😱'}
        </div>
      );
    }
    case 'circle_highlight': {
      const r = an ? an.size * 0.9 : (P.r ?? 0.12) * u;
      const cx = an ? ax : (P.x ?? 0.5) * W;
      const cy = an ? ay : (P.y ?? 0.5) * H;
      const p = easeInOut(clamp(local / 0.6));
      const circ = 2 * Math.PI * r;
      return (
        <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity: env}}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="#ff3b30" strokeWidth={u * 0.01} strokeDasharray={circ} strokeDashoffset={circ * (1 - p)} strokeLinecap="round" transform={`rotate(-90 ${cx} ${cy})`} />
        </svg>
      );
    }
    case 'arrow_callout': {
      const x = (P.x ?? 0.6) * W;
      const y = (P.y ?? 0.4) * H;
      const p = easeOut(clamp(local / 0.4));
      return (
        <div style={{position: 'absolute', inset: 0, opacity: env}}>
          <svg width={W} height={H} style={{position: 'absolute'}}>
            <line x1={x + u * 0.25} y1={y - u * 0.2} x2={x + u * 0.25 * (1 - p) + u * 0.03} y2={y - u * 0.2 * (1 - p) - u * 0.02} stroke="#FFD400" strokeWidth={u * 0.012} strokeLinecap="round" />
          </svg>
          {P.text ? <div style={{position: 'absolute', left: x + u * 0.26, top: y - u * 0.28, fontFamily: font, fontWeight: 800, fontSize: u * 0.05, color: '#FFD400', ...stroke(u * 0.004)}}>{P.text}</div> : null}
        </div>
      );
    }
    default:
      return null;
  }
};

const RelationshipMap: React.FC<{e: Effect; c: Ctx}> = ({e, c}) => {
  const {W, H, u, font, t} = c;
  const P = e.params || {};
  const nodes: {id: string; label: string; color?: string}[] = P.nodes || [];
  const edges: {a: string; b: string; label?: string}[] = P.edges || [];
  if (!nodes.length) return null;
  const env = envelope(t, e.start, e.end, 0.3, 0.3);
  const R = Math.min(W, H) * 0.3;
  const pos: Record<string, {x: number; y: number}> = {};
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    pos[n.id] = {x: W / 2 + Math.cos(a) * R, y: H / 2 + Math.sin(a) * R};
  });
  return (
    <AbsoluteFill style={{background: `rgba(0,0,0,${0.6 * env})`, opacity: env}}>
      <svg width={W} height={H} style={{position: 'absolute'}}>
        {edges.map((ed, i) => pos[ed.a] && pos[ed.b] ? (
          <g key={i}>
            <line x1={pos[ed.a].x} y1={pos[ed.a].y} x2={pos[ed.b].x} y2={pos[ed.b].y} stroke="#fff" strokeWidth={u * 0.006} strokeDasharray={`${u * 0.02} ${u * 0.012}`} />
            {ed.label ? <text x={(pos[ed.a].x + pos[ed.b].x) / 2} y={(pos[ed.a].y + pos[ed.b].y) / 2} fill="#FFD400" fontSize={u * 0.035} fontFamily={font} fontWeight={800} textAnchor="middle">{ed.label}</text> : null}
          </g>
        ) : null)}
      </svg>
      {nodes.map((n) => (
        <div key={n.id} style={{position: 'absolute', left: pos[n.id].x - u * 0.13, top: pos[n.id].y - u * 0.05, width: u * 0.26, textAlign: 'center', fontFamily: font, fontWeight: 900,
          fontSize: u * 0.045, color: '#111', background: n.color || '#fff', borderRadius: u * 0.03, padding: `${u * 0.012}px 0`}}>{n.label}</div>
      ))}
    </AbsoluteFill>
  );
};

export const TextOverlays: React.FC<{plan: EditPlan; outputId: string}> = ({plan, outputId}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const font = useFontFamily(TITLE_FONT);
  const safe = plan.safe_zones[outputId] ?? {top: 0.05, bottom: 0.08, left: 0.05, right: 0.05};
  const c: Ctx = {W, H, u: Math.min(W, H), font, t, safe, plan, outputId};
  const active = plan.effects.filter((e) => (e.category === 'text' || e.id === 'freeze_intro') && t >= e.start && t <= e.end);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {active.map((e, i) => {
        const key = `${e.id}-${i}`;
        if (['title_slam', 'title_reveal', 'title_split', 'kinetic_type'].includes(e.id)) return <Title key={key} e={e} c={c} />;
        if (['sfx_text', 'emoji_pop', 'circle_highlight', 'arrow_callout'].includes(e.id)) return <Anchored key={key} e={e} c={c} />;
        if (e.id === 'relationship_map') return <RelationshipMap key={key} e={e} c={c} />;
        return <Card key={key} e={e} c={c} />;
      })}
    </AbsoluteFill>
  );
};

