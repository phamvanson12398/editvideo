import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {Main} from './Main';
import samplePlan from './sample-plan.json';
import type {EditPlan, MainProps} from './types';

const calculateMetadata: CalculateMetadataFunction<MainProps> = ({props}) => {
  const out = props.plan.outputs.find((o) => o.id === props.outputId) ?? props.plan.outputs[0];
  const fps = out?.fps ?? 30;
  return {
    width: out?.width ?? 1080,
    height: out?.height ?? 1920,
    fps,
    durationInFrames: Math.max(1, Math.round(props.plan.duration * fps)),
  };
};

export const Root: React.FC = () => (
  <Composition
    id="Main"
    component={Main}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={{plan: samplePlan as unknown as EditPlan, outputId: (samplePlan as unknown as EditPlan).outputs[0].id}}
    calculateMetadata={calculateMetadata}
  />
);
