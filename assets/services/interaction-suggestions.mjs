import {INTERACTION_PROMPTS} from '../data/interaction-prompts.mjs';

const tokens = value => new Set(String(value).toLowerCase().match(/[a-z]{3,}/g) || []);
export function keywordSimilarity(context, activity) {
  const words = tokens(context);
  const candidates = tokens([...activity.tags, activity.prompt].join(' '));
  let overlap = 0;
  for (const word of words) if (candidates.has(word)) overlap++;
  return overlap / Math.max(1, Math.sqrt(words.size * candidates.size));
}
/** Inject a similarity scorer here later; floor selection never depends on scoring. */
export function suggestInteractions({floor, recentMessages = [], context = '', allowSensitivePrompts = false}, scorer = keywordSimilarity) {
  const text = [context, ...recentMessages.slice(-6).map(message => message.text)].join(' ');
  const ranked = INTERACTION_PROMPTS.filter(activity => activity.floor === floor &&
    (activity.sensitivity !== 'sensitive' || (floor === 4 && allowSensitivePrompts)))
    .map(activity => ({...activity, score: scorer(text, activity)}))
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  const close = ranked.slice(0, 2);
  const remaining = ranked.slice(2);
  const target = (close[0]?.score || 0) * 0.35;
  const differentTypes = remaining.filter(item => !close.some(other => other.type === item.type));
  const different = (differentTypes.length ? differentTypes : remaining)
    .sort((a, b) => Math.abs(a.score - target) - Math.abs(b.score - target) || a.id.localeCompare(b.id))[0];
  return [...close.map(item => ({...item, direction: 'Related'})), ...(different ? [{...different, direction: 'A new direction'}] : [])];
}
