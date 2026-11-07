// Japanese line breaking for 2ch-style captions: balanced lines that break after particles / punctuation,
// never start a line with punctuation or small kana ("女子更衣室で / 着替えてると", not "女子更衣室で着替えてる / と").
const NO_START = new Set([...'、。，．,.！？!?…・ーっゃゅょぁぃぅぇぉッャュョァィゥェォ」』）)〜～ｗw']);
const GOOD_AFTER = new Set([...'、。！？!?…はがをにでともへの']);
const GOOD_AFTER2 = ['たら', 'から', 'けど', 'ので', 'って', 'のに', 'ても', 'でも', 'なら', 'して', 'まで', 'より'];

const kind = (c: string) => (/[一-鿿々]/.test(c) ? 'k' : /[぀-ゟ]/.test(c) ? 'h' : /[゠-ヿ]/.test(c) ? 't' : 'o');

export const breakJapanese = (text: string, maxChars: number): string[] => {
  const n = [...text].length;
  if (n <= maxChars) return [text];
  // more lines until every line fits
  for (let count = Math.ceil(n / maxChars); count < n; count++) {
    const lines = split(text, maxChars, count);
    if (lines.every((l) => [...l].length <= maxChars)) return lines;
  }
  return [text];
};

const split = (text: string, maxChars: number, count: number): string[] => {
  const chars = [...text];
  const n = chars.length;
  const lines: string[] = [];
  let start = 0;
  for (let i = 1; i < count; i++) {
    const ideal = start + Math.round((n - start) / (count - i + 1));
    let best = -1;
    let bestScore = -Infinity;
    for (let p = Math.max(start + 2, ideal - 4); p <= Math.min(n - 2, ideal + 3, start + maxChars); p++) {
      if (NO_START.has(chars[p])) continue;
      let score = -Math.abs(p - ideal);
      if (GOOD_AFTER.has(chars[p - 1])) score += 3;
      if (p >= 2 && GOOD_AFTER2.includes(chars[p - 2] + chars[p - 1])) score += 3.5;
      if (kind(chars[p - 1]) !== kind(chars[p])) score += 1.5;
      if (kind(chars[p - 1]) === 'k' && kind(chars[p]) === 'k') score -= 3; // don't split a kanji word
      if (kind(chars[p - 1]) === 't' && kind(chars[p]) === 't') score -= 3; // ... or a katakana word
      if (score > bestScore) {
        bestScore = score;
        best = p;
      }
    }
    if (best < 0) best = Math.min(n - 1, start + maxChars);
    lines.push(chars.slice(start, best).join(''));
    start = best;
  }
  lines.push(chars.slice(start).join(''));
  return lines;
};
