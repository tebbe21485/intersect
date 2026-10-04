import test from 'node:test';
import assert from 'node:assert/strict';
import {suggestInteractions} from '../../assets/services/interaction-suggestions.mjs';
import {INTERACTION_PROMPTS} from '../../assets/data/interaction-prompts.mjs';

let revision = 0;
async function fixture() {
  const values = new Map();
  globalThis.sessionStorage = {getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value)};
  const store = await import(`../../assets/services/connection-state.mjs?test=${++revision}`);
  store.getConnectionState('pair', ['a', 'b']);
  return store;
}
function talk(store, floor) {
  for (const user of ['a', 'b']) for (let index = 0; index < 2; index++) {
    store.sendConnectionMessage('pair', user, 'A friendly message', `${floor}-${user}-${index}`);
  }
}
function advance(store) {
  store.setFloorReady('pair', 'a', true);
  store.setFloorReady('pair', 'b', true);
}

test('two messages from each person enable readiness, never automatic advancement', async () => {
  const store = await fixture();
  assert.throws(() => store.setFloorReady('pair', 'a', true), /two messages/);
  for (let i = 0; i < 5; i++) store.sendConnectionMessage('pair', 'a', 'Hello', `a-${i}`);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).canAdvance, false);
  store.sendConnectionMessage('pair', 'b', 'Hello', 'b-1');
  assert.equal(store.getConnectionState('pair', ['a', 'b']).canAdvance, false);
  store.sendConnectionMessage('pair', 'b', 'Hello again', 'b-2');
  let state = store.getConnectionState('pair', ['a', 'b']);
  assert.equal(state.canAdvance, true);
  assert.equal(state.currentFloor, 1);
  store.setFloorReady('pair', 'a', true);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).currentFloor, 1);
  store.setFloorReady('pair', 'a', false);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).ready.a, false);
  advance(store);
  state = store.getConnectionState('pair', ['a', 'b']);
  assert.equal(state.currentFloor, 2);
  assert.deepEqual(state.counts, {a: 0, b: 0});
  assert.deepEqual(state.ready, {});
});

test('all four floors require new reciprocal messages; Trust has no further advancement', async () => {
  const store = await fixture();
  for (let floor = 1; floor <= 4; floor++) {
    assert.equal(store.getConnectionState('pair', ['a', 'b']).currentFloor, floor);
    talk(store, floor);
    assert.equal(store.getConnectionState('pair', ['a', 'b']).currentFloor, floor);
    if (floor < 4) advance(store);
  }
  assert.equal(store.getConnectionState('pair', ['a', 'b']).canAdvance, false);
  assert.throws(() => advance(store), /two messages/);
});

test('identity becomes available only after both complete floor 2; consent stays separate', async () => {
  const store = await fixture();
  assert.throws(() => store.setIdentityConsent('pair', 'a', true), /floor 2/);
  talk(store, 1); advance(store);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).identityAvailable, false);
  talk(store, 2);
  let state = store.getConnectionState('pair', ['a', 'b']);
  assert.equal(state.identityAvailable, true);
  assert.equal(state.currentFloor, 2);
  assert.deepEqual(state.identityConsent, {});
  store.setIdentityConsent('pair', 'a', true);
  state = store.getConnectionState('pair', ['a', 'b']);
  assert.equal(state.identityConsent.a, true);
  assert.equal(Boolean(state.identityConsent.b), false);
  store.setIdentityConsent('pair', 'b', true);
  assert.throws(() => store.setIdentityConsent('pair', 'a', false), /already been revealed/);
});

test('sensitive opt-in needs both users and is isolated to each connection', async () => {
  const store = await fixture();
  store.setSensitiveOptIn('pair', 'a', true);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).allowSensitivePrompts, false);
  store.setSensitiveOptIn('pair', 'b', true);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).allowSensitivePrompts, true);
  assert.equal(store.getConnectionState('other-pair', ['a', 'c']).allowSensitivePrompts, false);
  store.setSensitiveOptIn('pair', 'b', false);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).allowSensitivePrompts, false);
  assert.throws(() => store.setSensitiveOptIn('pair', 'stranger', true), /not part/);
});

test('retries, duplicate observations and older history cannot add floor progress', async () => {
  const store = await fixture();
  store.sendConnectionMessage('pair', 'a', 'Hello', 'retry');
  store.sendConnectionMessage('pair', 'a', 'Hello', 'retry');
  assert.equal(store.getConnectionState('pair', ['a', 'b']).counts.a, 1);
  assert.throws(() => store.sendConnectionMessage('pair', 'a', 'Different', 'retry'), /another message/);
  const seen = {id: '10', ownerId: 'b', text: 'Hello', time: 'Now'};
  store.observeMessages('pair', ['a', 'b'], [seen, seen]);
  store.observeMessages('pair', ['a', 'b'], [seen]);
  assert.equal(store.getConnectionState('pair', ['a', 'b']).counts.b, 1);
  talk(store, 1); advance(store);
  store.observeMessages('pair', ['a', 'b'], [{...seen, id: '1'}, {...seen, id: '2', ownerId: 'a'}]);
  assert.deepEqual(store.getConnectionState('pair', ['a', 'b']).counts, {a: 0, b: 0});
  const reloaded = await import(`../../assets/services/connection-state.mjs?reload=${++revision}`);
  assert.equal(reloaded.getConnectionState('pair', ['a', 'b']).currentFloor, 2);
});

test('suggestions stay on the current floor, with two related and one different prompt', () => {
  for (let floor = 1; floor <= 4; floor++) {
    const suggestions = suggestInteractions({floor, recentMessages: [{text: 'I like hiking outdoors and traveling with friends.'}]});
    assert.equal(suggestions.length, 3);
    assert.deepEqual(suggestions.map(item => item.direction), ['Related', 'Related', 'A new direction']);
    assert.equal(new Set(suggestions.map(item => item.id)).size, 3);
    assert.ok(suggestions.every(item => item.floor === floor && item.sensitivity !== 'sensitive'));
  }
  const score = (_, activity) => activity.sensitivity === 'sensitive' ? 1 : 0;
  assert.equal(suggestInteractions({floor: 4, allowSensitivePrompts: false}, score).some(p => p.sensitivity === 'sensitive'), false);
  assert.equal(suggestInteractions({floor: 4, allowSensitivePrompts: true}, score).some(p => p.sensitivity === 'sensitive'), true);
  assert.ok(INTERACTION_PROMPTS.every(p => p.id && p.type && p.prompt && p.tags.length && ['light', 'personal', 'sensitive'].includes(p.sensitivity)));
});
