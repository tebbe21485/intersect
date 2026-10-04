/** Fit readable labels inside the fixed SVG piece center, without changing geometry. */
export function formatPuzzleLabel(label) {
  const words = String(label).trim().split(/\s+/u);
  const width = (text, size) => Array.from(text).reduce((sum, char) => sum +
    (/[MW@%]/u.test(char) ? 1 : /[ilI.,'!|]/u.test(char) ? 0.32 : /[^\x00-\x7F]/u.test(char) ? 1 : /[A-Z]/u.test(char) ? 0.72 : 0.64) * size, 0);
  const canKeepWords = words.every(word => width(word, 8) <= 72);
  for (let fontSize = 14; fontSize >= 8; fontSize--) {
    if (canKeepWords && words.some(word => width(word, fontSize) > 72)) continue;
    const lines = [];
    let line = '';
    for (const word of words) {
      if (width(word, fontSize) > 72) {
        if (line) { lines.push(line); line = ''; }
        for (const char of Array.from(word)) {
          if (line && width(line + char, fontSize) > 72) { lines.push(line); line = ''; }
          line += char;
        }
      } else if (line && width(`${line} ${word}`, fontSize) > 72) {
        lines.push(line); line = word;
      } else line += (line ? ' ' : '') + word;
    }
    if (line) lines.push(line);
    const lineHeight = fontSize * 1.2;
    if (lines.length <= 3 && lines.length * lineHeight <= 54) return {lines, fontSize, lineHeight};
  }
  return {lines: [String(label)], fontSize: 8, lineHeight: 10};
}
