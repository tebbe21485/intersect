/** Hand-authored SVG paths. Never generate puzzle geometry at runtime. */
const paths = {
  topLeft: 'M0 0H100V35C100 40 114 35 114 50S100 60 100 65V100H65C60 100 65 86 50 86S40 100 35 100H0Z',
  topRight: 'M0 0H100V100H65C60 100 65 114 50 114S40 100 35 100H0V65C0 60 14 65 14 50S0 40 0 35Z',
  middleLeft: 'M0 0H35C40 0 35 -14 50 -14S60 0 65 0H100V35C100 40 86 35 86 50S100 60 100 65V100H65C60 100 65 114 50 114S40 100 35 100H0Z',
  middleRight: 'M0 0H35C40 0 35 14 50 14S60 0 65 0H100V100H65C60 100 65 86 50 86S40 100 35 100H0V65C0 60 -14 65 -14 50S0 40 0 35Z',
  lowerLeft: 'M0 0H35C40 0 35 14 50 14S60 0 65 0H100V35C100 40 114 35 114 50S100 60 100 65V100H65C60 100 65 86 50 86S40 100 35 100H0Z',
  lowerRight: 'M0 0H35C40 0 35 -14 50 -14S60 0 65 0H100V100H65C60 100 65 114 50 114S40 100 35 100H0V65C0 60 14 65 14 50S0 40 0 35Z',
  bottomLeftIn: 'M0 0H35C40 0 35 -14 50 -14S60 0 65 0H100V35C100 40 86 35 86 50S100 60 100 65V100H0Z',
  bottomRightOut: 'M0 0H35C40 0 35 14 50 14S60 0 65 0H100V100H0V65C0 60 -14 65 -14 50S0 40 0 35Z',
  bottomLeftOut: 'M0 0H35C40 0 35 14 50 14S60 0 65 0H100V35C100 40 114 35 114 50S100 60 100 65V100H0Z',
  bottomRightIn: 'M0 0H35C40 0 35 -14 50 -14S60 0 65 0H100V100H0V65C0 60 14 65 14 50S0 40 0 35Z',
};
const tile = (path, x, y) => Object.freeze({path: paths[path], x, y});
export const PUZZLE_LAYOUTS = Object.freeze({
  4: Object.freeze([tile('topLeft', 0, 0), tile('topRight', 100, 0),
    tile('bottomLeftIn', 0, 100), tile('bottomRightOut', 100, 100)]),
  6: Object.freeze([tile('topLeft', 0, 0), tile('topRight', 100, 0),
    tile('middleLeft', 0, 100), tile('middleRight', 100, 100),
    tile('bottomLeftOut', 0, 200), tile('bottomRightIn', 100, 200)]),
  8: Object.freeze([tile('topLeft', 0, 0), tile('topRight', 100, 0),
    tile('middleLeft', 0, 100), tile('middleRight', 100, 100),
    tile('lowerLeft', 0, 200), tile('lowerRight', 100, 200),
    tile('bottomLeftIn', 0, 300), tile('bottomRightOut', 100, 300)]),
});
export function layoutSize(count) {
  if (!Number.isInteger(count) || count < 4 || count > 8) throw new RangeError('Create 4 to 8 pieces.');
  return count <= 4 ? 4 : count <= 6 ? 6 : 8;
}

/** Shuffle piece assignments, never SVG geometry; stable for both viewers and reloads. */
export function mixedPuzzleSlots(owners, connectionId) {
  const sorted = [...owners].sort((a, b) => a.id.localeCompare(b.id));
  const slots = sorted.flatMap((owner, bank) => PUZZLE_LAYOUTS[layoutSize(owner.pieces.length)]
    .map(slot => ({...slot, x: slot.x + bank * 200})));
  const entries = sorted.flatMap(owner => PUZZLE_LAYOUTS[layoutSize(owner.pieces.length)]
    .map((_, index) => ({piece: owner.pieces[index] || null, owner})));
  let seed = 2166136261;
  for (const char of connectionId) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619);
  const random = () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let value = Math.imul(seed ^ (seed >>> 15), seed | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
  const boundary = layoutSize(sorted[0].pieces.length);
  // Both colors belong on both sides. Avoid accidentally shuffling into two owner banks.
  for (let attempt = 0; attempt < 100; attempt++) {
    for (let index = entries.length - 1; index > 0; index--) {
      const other = Math.floor(random() * (index + 1));
      [entries[index], entries[other]] = [entries[other], entries[index]];
    }
    if ([entries.slice(0, boundary), entries.slice(boundary)].every(side =>
      sorted.every(owner => side.some(entry => entry.piece?.ownerId === owner.id)))) break;
  }
  return slots.map((slot, index) => ({slot, ...entries[index]}));
}
