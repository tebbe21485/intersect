/** Browser-only puzzle demo. No puzzle API or database writes. */
export const PUZZLE_STORAGE_KEY = 'intersect-puzzles-v1';
export const DEMO_SESSION_KEY = 'intersect-puzzle-demo-account-v1';
export const DEMO_ACCOUNTS = [
  {id: 'demo-juniper', alias: 'Juniper', color: '#2d6791', email: 'juniper@example.com', pieces: [
    ['Robotics', 'I love building and programming robots.'],
    ['Hiking', 'A quiet trail and a morning outside are my favorite way to recharge.'],
    ['Baking', 'I am learning to bake sourdough and love sharing a fresh loaf.'],
    ['Sci-fi', 'I enjoy stories about space, technology, and possible futures.'],
  ]},
  {id: 'demo-maple', alias: 'Maple', color: '#ad4c32', email: 'maple@example.com', pieces: [
    ['Gardening', 'I grow herbs on my windowsill and volunteer at the campus garden.'],
    ['Birds', 'I like noticing the birds on my morning walks.'],
    ['Watercolors', 'I paint small watercolor landscapes in my sketchbook.'],
    ['Tea', 'I collect loose-leaf teas and make a cup before studying.'],
    ['Volunteering', 'I help with community planting days whenever I can.'],
  ]},
  {id: 'demo-river', alias: 'River', color: '#6c4b94', email: 'river@example.com', pieces: [
    ['Coffee', 'I enjoy trying small coffee shops and talking with friends over a latte.'],
    ['Guitar', 'I play acoustic guitar and am learning to write my own songs.'],
    ['Photography', 'I shoot film photographs of everyday places around campus.'],
    ['Cooking', 'I like cooking meals that friends can share around one table.'],
    ['Cycling', 'I ride my bike to explore neighborhoods I have not visited before.'],
    ['Jazz', 'I love a live jazz set in a small room.'],
    ['Languages', 'I am practicing Spanish so I can chat with more people.'],
  ]},
  {id: 'demo-sage', alias: 'Sage', color: '#26735b', email: 'sage@example.com', pieces: [
    ['Books', 'I read novels on the library second floor by the windows.'],
    ['Community', 'I like helping new students find familiar faces on campus.'],
    ['Chess', 'I enjoy casual chess games and learning from each match.'],
    ['Pottery', 'I am trying pottery because making things with my hands feels calming.'],
    ['Running', 'I run short distances before class to clear my head.'],
    ['History', 'I love hearing the stories behind old buildings and places.'],
    ['Games', 'Cooperative board games are my favorite way to spend an evening.'],
    ['Stargazing', 'I look for constellations whenever the sky is clear.'],
  ]},
];
export const DEMO_RELATIONS = [
  {users: ['demo-juniper', 'demo-maple'], source: 'Daily question', shared: 'Morning walks and time outdoors'},
  {users: ['demo-juniper', 'demo-river'], source: 'Mini poll', shared: 'Coffee with friends'},
  {users: ['demo-juniper', 'demo-sage'], source: 'Question board', shared: 'Making a new place feel like home'},
  {users: ['demo-maple', 'demo-river'], source: 'Question board', shared: 'A creative hobby to try'},
  {users: ['demo-maple', 'demo-sage'], source: 'Daily question', shared: 'A quiet spot to recharge'},
  {users: ['demo-river', 'demo-sage'], source: 'Mini poll', shared: 'A relaxed evening with friends'},
];
export const connectionKey = (a, b) => [a, b].sort().join('::');
const toPieces = account => account.pieces.map(([shortLabel, description], index) => ({
  id: `${account.id}-piece-${index + 1}`, ownerId: account.id, shortLabel, description, isShared: false,
}));
let memory;
function initialState() {
  return {users: Object.fromEntries(DEMO_ACCOUNTS.map(account => [account.id, {
    id: account.id, alias: account.alias, color: account.color, pieces: toPieces(account),
  }])), connections: Object.fromEntries(DEMO_RELATIONS.map(({users}) => [connectionKey(...users),
    users.flatMap(id => toPieces(DEMO_ACCOUNTS.find(a => a.id === id)).slice(0, 2).map(p => p.id))]))};
}
function read() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(PUZZLE_STORAGE_KEY));
    if (stored?.version === 1 && stored.users && stored.connections) memory = stored;
  } catch { /* In-memory state also supports storage-disabled browsers. */ }
  return memory ||= initialState();
}
function save(state) {
  memory = state;
  try { sessionStorage.setItem(PUZZLE_STORAGE_KEY, JSON.stringify({...state, version: 1})); } catch { /* Keep memory. */ }
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('intersect:puzzle-change'));
}
export function getDemoAccount() {
  try { return DEMO_ACCOUNTS.find(a => a.id === sessionStorage.getItem(DEMO_SESSION_KEY)) || null; }
  catch { return null; }
}
export function signInDemo(id) {
  if (!DEMO_ACCOUNTS.some(a => a.id === id)) throw new Error('Choose a sample account.');
  sessionStorage.setItem(DEMO_SESSION_KEY, id);
  sessionStorage.removeItem('intersect-ui-v1');
}
export function leaveDemo() {
  try { sessionStorage.removeItem(DEMO_SESSION_KEY); } catch { /* No demo session. */ }
}
export function validatePuzzleDrafts(drafts) {
  if (drafts.length < 4 || drafts.length > 8 || drafts.some(p =>
    !p.shortLabel?.trim() || p.shortLabel.trim().length > 20 || !p.description?.trim() || p.description.trim().length > 500)) {
    throw new Error('Create 4 to 8 pieces with a short label and description.');
  }
}
export function createUserPuzzle(id, alias, drafts) {
  validatePuzzleDrafts(drafts);
  const state = read();
  state.users[id] = {id, alias, color: '#2d6791', pieces: drafts.map((p, i) => ({
    id: `${id}-piece-${i + 1}`, ownerId: id, shortLabel: p.shortLabel.trim(), description: p.description.trim(), isShared: false,
  }))};
  save(state);
}
export function getUserPuzzle(id) {
  const user = read().users[id];
  return user ? structuredClone(user) : null;
}
/** Project the authenticated builder's saved pieces into the local chat preview. */
export function syncSavedPuzzle(profile, pieces) {
  if (pieces.length > 8) return; // Older profiles can remove surplus pieces in the editor.
  const state = read();
  state.users[profile.id] = {id: profile.id, alias: profile.alias,
    color: state.users[profile.id]?.color || '#2d6791',
    pieces: pieces.map(piece => ({id: `${profile.id}-saved-piece-${piece.id}`, ownerId: profile.id,
      shortLabel: piece.title, description: piece.description, isShared: false}))};
  save(state);
}
export function getConnectionPuzzle(key, ownerIds) {
  const shared = new Set(read().connections[key] || []);
  return ownerIds.map(id => {
    const owner = getUserPuzzle(id);
    return owner && {...owner, pieces: owner.pieces.map(p => ({...p, isShared: shared.has(p.id)}))};
  });
}
export function sharePiece(key, currentUserId, pieceId) {
  const state = read();
  const owner = state.users[currentUserId];
  if (!owner?.pieces.some(p => p.id === pieceId)) throw new Error('You can only share your own pieces.');
  const shared = state.connections[key] ||= [];
  if (!shared.includes(pieceId)) { shared.push(pieceId); save(state); }
}
