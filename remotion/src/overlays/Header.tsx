import React from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';
import {useFontFamily} from '../lib/fonts';
import type {HeaderBand} from '../types';

// Outline in white + soft glow in the title color (2ch / スカッと shorts title band).
const outline = (px: number, color: string, glow: string) => {
  const s: string[] = [];
  for (let a = 0; a < 24; a++) {
    const ang = (a / 24) * Math.PI * 2;
    s.push(`${(Math.cos(ang) * px).toFixed(1)}px ${(Math.sin(ang) * px).toFixed(1)}px 0 ${color}`);
  }
  s.push(`0 0 ${px * 2.2}px ${glow}`, `0 0 ${px * 4}px ${glow}`);
  return s.join(',');
};

// Rough text width in em: full-width (kana/kanji) ~1, Latin ~0.62.
const emWidth = (s: string) => [...s].reduce((n, c) => n + (c.charCodeAt(0) > 0x2e80 ? 1 : 0.62), 0);

export const HeaderBandView: React.FC<{header: HeaderBand}> = ({header}) => {
  const {width: W, height: H} = useVideoConfig();
  const font = useFontFamily(header.font);
  const bandH = H * header.height;
  const lines = [header.series, header.title].filter((l) => l && l.trim());
  if (!lines.length) return <AbsoluteFill style={{height: bandH, background: header.bg}} />;
  const maxW = W * 0.94;
  const sizes = lines.map((l, i) => {
    const base = lines.length === 1 ? bandH * 0.5 : bandH * (i === 0 ? 0.4 : 0.36);
    return Math.min(base, maxW / Math.max(1, emWidth(l)));
  });
  return (
    <AbsoluteFill style={{height: bandH, background: header.bg, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
      {lines.map((l, i) => (
        <div key={i} style={{fontFamily: font, fontWeight: 900, fontSize: sizes[i], lineHeight: 1.12, color: header.color, whiteSpace: 'nowrap',
          textShadow: outline(Math.max(2, sizes[i] * 0.07), '#fff', header.color)}}>
          {l}
        </div>
      ))}
    </AbsoluteFill>
  );
};
