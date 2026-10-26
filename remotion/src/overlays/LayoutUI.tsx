import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {TITLE_FONT, useFontFamily} from '../lib/fonts';
import type {EditPlan} from '../types';

export const LayoutUI: React.FC<{plan: EditPlan; outputId: string}> = ({plan, outputId}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const u = Math.min(W, H);
  const font = useFontFamily(TITLE_FONT);
  const safe = plan.safe_zones[outputId] ?? {top: 0.05, bottom: 0.08, left: 0.05, right: 0.05};
  const items = plan.effects.filter((e) => ['progress_bar', 'episode_badge', 'watermark'].includes(e.id) && t >= e.start && t <= e.end);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {items.map((e, i) => {
        if (e.id === 'progress_bar') {
          return (
            <div key={i} style={{position: 'absolute', left: 0, top: 0, height: u * 0.012, width: `${(t / plan.duration) * 100}%`, background: e.params.color || '#FFD400', boxShadow: '0 0 10px rgba(0,0,0,.4)'}} />
          );
        }
        if (e.id === 'episode_badge') {
          return (
            <div key={i} style={{position: 'absolute', left: W * safe.left + u * 0.02, top: H * safe.top + u * 0.02, fontFamily: font, fontWeight: 800, fontSize: u * 0.04,
              color: '#111', background: '#FFD400', padding: `${u * 0.008}px ${u * 0.02}px`, borderRadius: u * 0.012}}>
              {e.params.text}
            </div>
          );
        }
        return (
          <div key={i} style={{position: 'absolute', right: W * safe.right + u * 0.02, top: H * safe.top + u * 0.02, fontFamily: font, fontWeight: 700, fontSize: u * 0.032,
            color: 'rgba(255,255,255,.75)', textShadow: '0 1px 3px rgba(0,0,0,.6)'}}>
            {e.params.text}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
