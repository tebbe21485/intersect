import test from 'node:test';
import assert from 'node:assert/strict';
import {PUZZLE_LAYOUTS, layoutSize, mixedPuzzleSlots} from '../../assets/services/puzzle-layouts.mjs';
import {prepareProvider} from '../../assets/services/contracts.mjs';
import {createPuzzleDemoProvider} from '../../assets/services/puzzle-demo-provider.mjs';
import {readFileSync} from 'node:fs';

function storage() {
  const values = new Map();
  return {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)};
}
let revision = 0;
async function fixture() {
  globalThis.sessionStorage = storage();
  return import(`../../assets/services/puzzle-store.mjs?fixture=${++revision}`);
}

test('4–8 pieces select only the three fixed layouts; 5 and 7 retain spare blank slots', () => {
  assert.deepEqual([4, 5, 6, 7, 8].map(layoutSize), [4, 6, 6, 8, 8]);
  for (const count of [4, 6, 8]) {
    assert.equal(PUZZLE_LAYOUTS[count].length, count);
    assert.ok(Object.isFrozen(PUZZLE_LAYOUTS[count]));
  }
  for (const count of [0, 3, 9, 16, 4.5]) assert.throws(() => layoutSize(count), RangeError);
});

test('all four demo accounts have distinct colors and three relationships each', async () => {
  const store = await fixture();
  assert.equal(store.DEMO_ACCOUNTS.length, 4);
  assert.equal(new Set(store.DEMO_ACCOUNTS.map(a => a.color)).size, 4);
  for (const account of store.DEMO_ACCOUNTS) {
    const relations = store.DEMO_RELATIONS.filter(r => r.users.includes(account.id));
    assert.equal(relations.length, 3);
    for (const relation of relations) {
      const owners = store.getConnectionPuzzle(store.connectionKey(...relation.users), relation.users);
      assert.ok(owners.flatMap(o => o.pieces).length <= 16);
      assert.ok(owners.every(o => o.pieces.some(p => p.isShared) && o.pieces.some(p => !p.isShared)));
    }
    store.signInDemo(account.id);
    assert.equal(store.getDemoAccount().id, account.id);
  }
});

test('mixed pieces use fixed slots, retain every piece, and include both owners on both sides', async () => {
  const store = await fixture();
  const drafts = count => Array.from({length: count}, (_, i) => ({shortLabel: `Piece ${i}`, description: `Story ${i}`}));
  for (let first = 4; first <= 8; first++) {
    for (let second = 4; second <= 8; second++) {
      store.createUserPuzzle(`a-${first}`, 'A', drafts(first));
      store.createUserPuzzle(`b-${second}`, 'B', drafts(second));
      const owners = [store.getUserPuzzle(`a-${first}`), store.getUserPuzzle(`b-${second}`)];
      for (let seed = 0; seed < 20; seed++) {
        const slots = mixedPuzzleSlots(owners, `connection-${seed}`);
        assert.equal(slots.length, layoutSize(first) + layoutSize(second));
        assert.deepEqual(slots.filter(s => s.piece).map(s => s.piece.id).sort(), owners.flatMap(o => o.pieces.map(p => p.id)).sort());
        assert.equal(slots.filter(s => !s.piece).length, layoutSize(first) + layoutSize(second) - first - second);
        for (const side of [slots.filter(s => s.slot.x < 200), slots.filter(s => s.slot.x >= 200)]) {
          assert.equal(new Set(side.filter(s => s.piece).map(s => s.piece.ownerId)).size, 2);
        }
        assert.deepEqual(slots.map(s => s.slot.path), owners.flatMap(o => PUZZLE_LAYOUTS[layoutSize(o.pieces.length)].map(s => s.path)));
      }
    }
  }
});

test('mixed positions are stable across viewers and reveals, with different orders per connection', async () => {
  const store = await fixture();
  const ids = store.DEMO_ACCOUNTS.slice(0, 2).map(a => a.id);
  const key = store.connectionKey(...ids);
  const owners = store.getConnectionPuzzle(key, ids);
  const idsIn = slots => slots.map(s => s.piece?.id || null);
  const before = idsIn(mixedPuzzleSlots(owners, key));
  assert.deepEqual(idsIn(mixedPuzzleSlots([...owners].reverse(), key)), before);
  store.sharePiece(key, ids[0], owners[0].pieces[2].id);
  assert.deepEqual(idsIn(mixedPuzzleSlots(store.getConnectionPuzzle(key, ids), key)), before);
  assert.notDeepEqual(idsIn(mixedPuzzleSlots(owners, 'another-connection')), before);
});

test('sharing is owner checked, idempotent, reciprocal, and isolated to one connection', async () => {
  const store = await fixture();
  const [a, b, c] = store.DEMO_ACCOUNTS;
  const key = store.connectionKey(a.id, b.id);
  const piece = store.getUserPuzzle(a.id).pieces[2];
  assert.equal(store.getConnectionPuzzle(key, [a.id, b.id])[0].pieces[2].isShared, false);
  assert.throws(() => store.sharePiece(key, b.id, piece.id), /own pieces/);
  store.sharePiece(key, a.id, piece.id);
  store.sharePiece(key, a.id, piece.id);
  assert.equal(store.getConnectionPuzzle(key, [b.id, a.id])[1].pieces[2].isShared, true);
  assert.equal(store.getConnectionPuzzle(store.connectionKey(a.id, c.id), [a.id, c.id])[0].pieces[2].isShared, false);
  const fresh = await import(`../../assets/services/puzzle-store.mjs?reload=${++revision}`);
  assert.equal(fresh.getConnectionPuzzle(key, [a.id, b.id])[0].pieces[2].isShared, true);
});

test('signup creates exactly the supplied 4–8 private pieces and rejects invalid input', async () => {
  const store = await fixture();
  const drafts = Array.from({length: 8}, (_, i) => ({shortLabel: `Piece ${i}`, description: `My story ${i}`}));
  for (const count of [4, 5, 6, 7, 8]) {
    const id = `signup-${count}`;
    store.createUserPuzzle(id, 'New user', drafts.slice(0, count));
    const user = store.getUserPuzzle(id);
    assert.equal(user.pieces.length, count);
    assert.ok(user.pieces.every(p => p.ownerId === id && p.isShared === false));
    assert.deepEqual(Object.keys(user.pieces[0]).sort(), ['description', 'id', 'isShared', 'ownerId', 'shortLabel']);
  }
  for (const invalid of [drafts.slice(0, 3), [...drafts, drafts[0]], [{shortLabel: ' ', description: 'Text'}, ...drafts.slice(0, 3)]]) {
    assert.throws(() => store.createUserPuzzle('invalid', 'Alias', invalid), /4 to 8/);
    assert.equal(store.getUserPuzzle('invalid'), null);
  }
});

test('saved builder titles and descriptions keep sharing decisions through edits and reloads', async () => {
  const store = await fixture();
  const profile = {id: 'builder-user', alias: 'Builder'};
  const saved = Array.from({length: 4}, (_, i) => ({id: String(i + 1), title: `Title ${i + 1}`, description: `Description ${i + 1}`}));
  store.syncSavedPuzzle(profile, saved);
  const pieceId = store.getUserPuzzle(profile.id).pieces[0].id;
  const key = store.connectionKey(profile.id, 'demo-maple');
  store.sharePiece(key, profile.id, pieceId);
  store.syncSavedPuzzle(profile, [{...saved[0], title: 'Edited title', description: 'Edited description'}, ...saved.slice(1)]);
  const fresh = await import(`../../assets/services/puzzle-store.mjs?builderReload=${++revision}`);
  const piece = fresh.getConnectionPuzzle(key, [profile.id, 'demo-maple'])[0].pieces[0];
  assert.equal(piece.id, pieceId);
  assert.equal(piece.shortLabel, 'Edited title');
  assert.equal(piece.description, 'Edited description');
  assert.equal(piece.isShared, true);
  assert.equal(fresh.getConnectionPuzzle('another-connection', [profile.id, 'demo-maple'])[0].pieces[0].isShared, false);
});

test('sample conversations satisfy the existing provider contract for every account', async () => {
  const store = await fixture();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ok: true, json: async () => JSON.parse(readFileSync(new URL('../../assets/demo-data.json', import.meta.url), 'utf8'))});
  try {
    for (const account of store.DEMO_ACCOUNTS) {
      const provider = prepareProvider(await createPuzzleDemoProvider(account));
      const data = await provider.load();
      assert.equal(data.profile.id, account.id);
      assert.equal(data.connections.length, 3);
      assert.ok(data.connections.every(c => c.peerId !== account.id && c.puzzleKey === c.id));
    }
  } finally { globalThis.fetch = originalFetch; }
});
