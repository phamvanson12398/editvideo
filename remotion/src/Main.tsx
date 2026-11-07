import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {Captions} from './captions/Captions';
import {HeaderBandView} from './overlays/Header';
import {LayoutUI} from './overlays/LayoutUI';
import {MangaOverlays} from './overlays/Manga';
import {ParticleOverlays} from './overlays/Particles';
import {StylizeOverlays} from './overlays/Stylize';
import {TextOverlays} from './overlays/Text';
import {TxOverlays} from './overlays/TxOverlays';
import type {MainProps} from './types';
import {ClipLayer} from './video/ClipLayer';

const ChromaDefs: React.FC = () => (
  <svg width={0} height={0} style={{position: 'absolute'}}>
    <defs>
      <filter id="chroma" x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
        <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
        <feOffset in="r" dx="6" dy="0" result="r2" />
        <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
        <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
        <feOffset in="b" dx="-6" dy="0" result="b2" />
        <feBlend in="r2" in2="g" mode="screen" result="rg" />
        <feBlend in="rg" in2="b2" mode="screen" />
      </filter>
    </defs>
  </svg>
);

export const Main: React.FC<MainProps> = ({plan, outputId}) => {
  const {fps, width: W, height: H} = useVideoConfig();
  const out = plan.outputs.find((o) => o.id === outputId) ?? plan.outputs[0];
  const oid = out?.id ?? outputId;
  const overlaps = plan.effects.filter((e) => e.category === 'overlap');
  const content = (
    <>
      {plan.clips.map((clip, i) => {
        const from = Math.round((clip.start - clip.handle_pre) * fps);
        const dur = Math.max(1, Math.round((clip.duration + clip.handle_pre + clip.handle_post) * fps));
        const tin = overlaps.find((e) => e.clip === clip.id);
        const next = plan.clips[i + 1];
        const tout = next ? overlaps.find((e) => e.clip === next.id) : undefined;
        return (
          <Sequence key={clip.id} from={from} durationInFrames={dur} layout="none">
            <ClipLayer plan={plan} clip={clip} outputId={oid} tin={tin} tout={tout} />
          </Sequence>
        );
      })}
      <StylizeOverlays plan={plan} />
      <ParticleOverlays plan={plan} />
      <MangaOverlays plan={plan} outputId={oid} />
      <TxOverlays plan={plan} />
      <Captions plan={plan} outputId={oid} />
      <TextOverlays plan={plan} outputId={oid} />
    </>
  );
  const header = plan.header;
  if (header) {
    // Title band on top; everything else lives in the area below it (its own width/height for the layers inside).
    const bandH = Math.round(H * header.height);
    const areaH = H - bandH;
    return (
      <AbsoluteFill style={{background: '#000'}}>
        <ChromaDefs />
        <div style={{position: 'absolute', left: 0, top: bandH, width: W, height: areaH, overflow: 'hidden'}}>
          <Sequence width={W} height={areaH} layout="none">
            {content}
          </Sequence>
        </div>
        <HeaderBandView header={header} />
        <LayoutUI plan={plan} outputId={oid} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <ChromaDefs />
      {content}
      <LayoutUI plan={plan} outputId={oid} />
    </AbsoluteFill>
  );
};
