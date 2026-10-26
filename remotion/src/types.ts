// Mirrors director/plan/schema.py (EditPlan). Keep in sync.

export type OutputSpec = {
  id: string;
  aspect: string;
  width: number;
  height: number;
  fps: number;
  platform?: string | null;
  letterbox?: boolean;
};

export type ReframeKey = {t: number; cx: number; cy: number; zoom?: number};

export type ClipReframe = {
  mode: 'center' | 'follow' | 'fit-blur' | 'fit-pad' | 'letterbox' | 'split';
  keys: ReframeKey[];
  split_keys?: ReframeKey[][];
};

export type FaceBoxT = {x: number; y: number; w: number; h: number; character?: string | null; score?: number};

export type Clip = {
  id: string;
  file: string;
  start: number;
  duration: number;
  src_in: number;
  src_out: number;
  speed: number;
  reverse: boolean;
  freeze?: number | null;
  handle_pre: number;
  handle_post: number;
  role: string;
  reframe: Record<string, ClipReframe>;
  faces: {t: number; boxes: FaceBoxT[]}[];
};

export type Effect = {
  id: string;
  category: string;
  start: number;
  end: number;
  params: Record<string, any>;
  clip?: string | null;
  reason?: string;
};

export type CaptionWord = {t0: number; t1: number; text: string; emphasis: boolean; emoji?: string | null};
export type CaptionLine = {
  t0: number;
  t1: number;
  words: CaptionWord[];
  speaker?: string | null;
  color?: string | null;
  emotion?: string | null;
  inner_voice?: boolean;
};

export type CaptionTrack = {
  enabled: boolean;
  preset: string;
  mode: string;
  font: string;
  weight: number;
  color: string;
  highlight: string;
  stroke: string;
  size: number;
  uppercase: boolean;
  position: string;
  emotion_styles: boolean;
  lines: CaptionLine[];
};

export type SafeZone = {top: number; bottom: number; left: number; right: number};

export type EditPlan = {
  version: number;
  source: string;
  source_size: [number, number];
  source_fps: number;
  duration: number;
  outputs: OutputSpec[];
  safe_zones: Record<string, SafeZone>;
  clips: Clip[];
  effects: Effect[];
  captions: CaptionTrack;
  hardsub?: {x: number; y: number; w: number; h: number} | null;
  characters: Record<string, {name: string; color?: string | null}>;
  genre: string;
  style_name: string;
};

export type MainProps = {
  plan: EditPlan;
  outputId: string;
};
