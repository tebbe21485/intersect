/** UI preferences only. Domain records and identities never enter this store. */
export const UI_STORAGE_KEY = 'intersect-ui-v1';
const defaults = () => ({activeId: undefined, activity: 'daily', dismissed: {}, community: 'Campus community', notice: ''});
function select(value) {
  const state = defaults();
  if (!value || typeof value !== 'object') return state;
  if (typeof value.activeId === 'string' || value.activeId === null) state.activeId = value.activeId;
  if (['daily', 'poll', 'challenge'].includes(value.activity)) state.activity = value.activity;
  if (typeof value.community === 'string') state.community = value.community;
  if (typeof value.notice === 'string') state.notice = value.notice;
  if (value.dismissed && typeof value.dismissed === 'object') {
    state.dismissed = Object.fromEntries(Object.entries(value.dismissed)
      .filter(([, prompts]) => Array.isArray(prompts))
      .map(([id, prompts]) => [id, prompts.filter(prompt => typeof prompt === 'string')]));
  }
  return state;
}
export function loadUiState() {
  try { return select(JSON.parse(sessionStorage.getItem(UI_STORAGE_KEY) || sessionStorage.getItem('intersect-demo-v1'))); }
  catch { return defaults(); }
}
export function saveUiState(state) {
  try { sessionStorage.setItem(UI_STORAGE_KEY, JSON.stringify(select(state))); } catch { /* UI still works in memory. */ }
}
