import {continueRender, delayRender, staticFile} from 'remotion';

// Fonts are bundled (assets/fonts, SIL OFL) and copied into the render's public dir as fonts/*.
// No network needed at render time. All of them include Vietnamese glyphs.
type Face = {file: string; weight: string};
const FAMILIES: Record<string, Face[]> = {
  'Be Vietnam Pro': [
    {file: 'BeVietnamPro-Medium.ttf', weight: '500'},
    {file: 'BeVietnamPro-Bold.ttf', weight: '700'},
    {file: 'BeVietnamPro-ExtraBold.ttf', weight: '800'},
    {file: 'BeVietnamPro-Black.ttf', weight: '900'},
  ],
  Montserrat: [{file: 'Montserrat-Variable.ttf', weight: '100 900'}],
  Oswald: [{file: 'Oswald-Variable.ttf', weight: '200 700'}],
  Lexend: [{file: 'Lexend-Variable.ttf', weight: '100 900'}],
  'Baloo 2': [{file: 'Baloo2-Variable.ttf', weight: '400 800'}],
  Roboto: [{file: 'Roboto-Variable.ttf', weight: '100 900'}],
};

const loaded = new Set<string>();

const load = (family: string) => {
  if (loaded.has(family) || typeof FontFace === 'undefined') return;
  loaded.add(family);
  const faces = FAMILIES[family];
  if (!faces) return;
  const handle = delayRender(`font ${family}`, {timeoutInMilliseconds: 30000});
  Promise.all(
    faces.map((f) => {
      const ff = new FontFace(`D-${family}`, `url('${staticFile(`fonts/${f.file}`)}')`, {weight: f.weight});
      return ff.load().then((x) => {
        (document.fonts as unknown as {add: (f: FontFace) => void}).add(x);
      });
    }),
  )
    .catch((err) => console.warn('font load failed', family, err))
    .finally(() => continueRender(handle));
};

export const useFontFamily = (name: string): string => {
  const family = FAMILIES[name] ? name : 'Be Vietnam Pro';
  load(family);
  // Korean / Japanese / Chinese fall back to the system's CJK fonts
  return `'D-${family}', 'Be Vietnam Pro', 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans CJK KR', 'Noto Sans KR', 'Yu Gothic', 'Microsoft YaHei', 'Noto Sans', 'DejaVu Sans', Arial, sans-serif`;
};

export const TITLE_FONT = 'Be Vietnam Pro';
