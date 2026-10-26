import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {anchorAt} from '../lib/anchor';
import {useFontFamily} from '../lib/fonts';
import {backOut, clamp, easeOut, hexToRgba, noise} from '../lib/math';
import {clipAt, mapPoint} from '../lib/view';
import type {CaptionLine, CaptionTrack, EditPlan} from '../types';

type Props = {plan: EditPlan; outputId: string};

const strokeShadow = (px: number, color: string) => {
  const s: string[] = [];
  for (let a = 0; a < 16; a++) {
    const ang = (a / 16) * Math.PI * 2;
    s.push(`${(Math.cos(ang) * px).toFixed(1)}px ${(Math.sin(ang) * px).toFixed(1)}px 0 ${color}`);
  }
  s.push(`0 ${px * 1.5}px ${px * 2.5}px rgba(0,0,0,.5)`);
  return s.join(',');
};

const EMO: Record<string, {color?: string; italic?: boolean; shake?: number; scale?: number}> = {
  shock: {shake: 0.9, scale: 1.12},
  anger: {color: '#FF5A4F', shake: 0.6, scale: 1.08},
  sad: {color: '#9FD3FF', italic: true},
  fear: {color: '#D0C4FF', shake: 0.35},
  comedy: {scale: 1.05},
  romance: {color: '#FFB3CF'},
  villain: {color: '#C792EA'},
};

export const Captions: React.FC<Props> = ({plan, outputId}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const track: CaptionTrack = plan.captions;
  const font = useFontFamily(track.font || 'Be Vietnam Pro');
  if (!track.enabled || !track.lines.length) return null;
  const t = frame / fps;
  const line = track.lines.find((l) => t >= l.t0 && t < l.t1);
  if (!line) return null;

  const u = Math.min(W, H);
  const vertical = H > W * 1.2;
  const safe = plan.safe_zones[outputId] ?? {top: 0.05, bottom: 0.1, left: 0.05, right: 0.05};
  const emphasisOnly = track.mode === 'emphasis-only';
  let fontSize = u * (vertical ? 0.075 : 0.058) * (track.size || 1);
  if (emphasisOnly) fontSize *= 1.6;

  // ---- vertical placement: avoid burned-in text and faces
  let y = vertical ? H * 0.70 : H * (1 - safe.bottom) - fontSize * 1.2;
  if (track.position === 'top') y = H * safe.top + fontSize * 1.8;
  if (track.position === 'middle' || emphasisOnly) y = H * 0.5;
  const clip = clipAt(plan, t);
  const an = anchorAt(plan, outputId, t, W, H, line.speaker);
  if (track.position === 'auto' && clip) {
    if (plan.hardsub && an) {
      const top = mapPoint(an.view, 0.5, plan.hardsub.y).y;
      const bottom = mapPoint(an.view, 0.5, plan.hardsub.y + plan.hardsub.h).y;
      if (y + fontSize > top && y - fontSize < bottom && top > 0 && top < H) {
        y = Math.max(H * safe.top + fontSize * 1.5, top - fontSize * 1.3);
      }
    }
    if (an?.found && !emphasisOnly) {
      const faceBottom = an.post.y + an.size * 0.6;
      const faceTop = an.post.y - an.size * 0.6;
      if (y + fontSize > faceTop && y - fontSize < faceBottom) {
        y = faceBottom + fontSize * 1.4 < H * (1 - safe.bottom) ? faceBottom + fontSize * 1.4 : Math.max(H * safe.top + fontSize * 1.5, faceTop - fontSize * 1.6);
      }
    }
  }

  const preset = track.preset;
  const emo = track.emotion_styles || preset === 'emotion_style' ? EMO[line.emotion || ''] : undefined;
  const baseColor = (preset === 'color_by_character' && line.color) || emo?.color || track.color || '#fff';
  const hi = track.highlight || '#FFD400';
  const local = t - line.t0;
  const lineIn = clamp(local / 0.12);
  const shake = emo?.shake ? noise('cap' + line.t0, t * 18, 0) * u * 0.006 * emo.shake : 0;
  const strokePx = Math.max(2, fontSize * 0.075);

  const wordStyle = (i: number, w: CaptionLine['words'][number]): React.CSSProperties => {
    const spoken = t >= w.t0;
    const active = t >= w.t0 && t < w.t1;
    const appear = clamp((t - w.t0) / 0.12);
    const s: React.CSSProperties = {display: 'inline-block', margin: `0 ${fontSize * 0.14}px`, whiteSpace: 'pre'};
    switch (preset) {
      case 'word_pop':
        if (!spoken) return {...s, opacity: 0};
        return {...s, color: active ? hi : baseColor, transform: `scale(${active ? 1 + 0.25 * (1 - easeOut(appear)) + 0.06 : 1})`};
      case 'karaoke':
        return {...s, color: spoken ? hi : baseColor};
      case 'highlight_keyword':
        return {...s, color: w.emphasis ? hi : baseColor, fontSize: w.emphasis ? fontSize * 1.18 : fontSize, transform: w.emphasis && active ? 'scale(1.08)' : undefined};
      case 'bounce':
        if (!spoken) return {...s, opacity: 0};
        return {...s, transform: `translateY(${(1 - backOut(appear)) * fontSize * 0.6}px)`};
      case 'typewriter':
        return s;
      case 'glitch_text':
        return {...s, textShadow: `${noise('gx', t * 30, i) * 4}px 0 #0ff, ${-noise('gy', t * 30, i) * 4}px 0 #f0a, ${strokeShadow(strokePx, track.stroke)}`};
      default:
        return {...s, color: w.emphasis && preset !== 'classic' ? hi : undefined};
    }
  };

  let textStyle: React.CSSProperties = {
    fontFamily: font,
    fontWeight: track.weight || 800,
    fontSize,
    lineHeight: 1.15,
    color: baseColor,
    textAlign: 'center',
    textTransform: track.uppercase ? 'uppercase' : undefined,
    textShadow: strokeShadow(strokePx, track.stroke || '#000'),
    fontStyle: emo?.italic || line.inner_voice || preset === 'inner_voice' ? 'italic' : undefined,
    maxWidth: W * (1 - safe.left - safe.right) * 0.96,
  };
  if (preset === 'box') {
    textStyle = {...textStyle, background: hexToRgba('#000000', 0.62), padding: `${fontSize * 0.18}px ${fontSize * 0.4}px`, borderRadius: fontSize * 0.25, textShadow: 'none'};
  } else if (preset === 'neon') {
    textStyle = {...textStyle, color: '#fff', textShadow: `0 0 ${fontSize * 0.15}px ${hi}, 0 0 ${fontSize * 0.4}px ${hi}, 0 0 ${fontSize * 0.8}px ${hi}`};
  } else if (preset === 'gradient') {
    textStyle = {...textStyle, backgroundImage: `linear-gradient(90deg, ${hi}, #ff4f8b, #4fc3f7)`, WebkitBackgroundClip: 'text', color: 'transparent', textShadow: 'none',
      filter: `drop-shadow(0 ${strokePx}px 0 #000)`};
  } else if (line.inner_voice || preset === 'inner_voice') {
    textStyle = {...textStyle, opacity: 0.85, fontWeight: 600};
  }

  const scale = (emo?.scale ?? 1) * (0.85 + 0.15 * easeOut(lineIn));
  const words = line.words;
  let content: React.ReactNode;
  if (preset === 'typewriter') {
    const full = words.map((w) => w.text).join(' ');
    const total = Math.max(0.2, (line.t1 - line.t0) * 0.7);
    const n = Math.ceil(full.length * clamp(local / total));
    content = <span>{full.slice(0, n)}<span style={{opacity: Math.floor(t * 4) % 2 ? 1 : 0}}>▌</span></span>;
  } else if (preset === 'handwritten') {
    const p = clamp(local / Math.max(0.3, (line.t1 - line.t0) * 0.6));
    content = <span style={{clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`, display: 'inline-block'}}>{words.map((w) => w.text).join(' ')}</span>;
  } else {
    content = words.map((w, i) => (
      <span key={i} style={wordStyle(i, w)}>
        {w.text}
        {w.emoji && t >= w.t0 ? <span style={{marginLeft: fontSize * 0.15}}>{w.emoji}</span> : null}
      </span>
    ));
  }

  if (preset === 'speech_bubble' && an?.found) {
    const bx = clamp(an.post.x - W * 0.3, W * 0.04, W * 0.36);
    const by = clamp(an.post.y - an.size * 1.6 - fontSize * 2, H * safe.top, H * 0.7);
    return (
      <AbsoluteFill style={{pointerEvents: 'none'}}>
        <div style={{position: 'absolute', left: bx, top: by, width: W * 0.6, background: '#fff', color: '#111', borderRadius: fontSize * 0.8, padding: `${fontSize * 0.35}px ${fontSize * 0.55}px`,
          fontFamily: font, fontWeight: 800, fontSize: fontSize * 0.8, textAlign: 'center', border: `${fontSize * 0.08}px solid #111`, transform: `scale(${backOut(lineIn)})`, transformOrigin: '50% 100%'}}>
          {words.map((w) => w.text).join(' ')}
          <div style={{position: 'absolute', left: clamp(an.post.x - bx, fontSize, W * 0.6 - fontSize), bottom: -fontSize * 0.55, width: fontSize * 0.7, height: fontSize * 0.7, background: '#fff',
            borderRight: `${fontSize * 0.08}px solid #111`, borderBottom: `${fontSize * 0.08}px solid #111`, transform: 'rotate(45deg)'}} />
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: 0, right: 0, top: y - fontSize * 0.6, display: 'flex', justifyContent: 'center', transform: `translateX(${shake}px)`}}>
        <div style={{...textStyle, transform: `scale(${scale})`, opacity: lineIn}}>{content}</div>
      </div>
    </AbsoluteFill>
  );
};
