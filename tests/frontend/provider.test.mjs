import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DemoProvider, DEMO_STORAGE_KEY} from '../../assets/services/demo-provider.mjs';
import {assertAppData, prepareProvider, ProviderError, resultValidators} from '../../assets/services/contracts.mjs';
import {createProvider} from '../../assets/services/provider.mjs';
import {loadUiState, saveUiState, UI_STORAGE_KEY} from '../../assets/services/ui-state.mjs';

const seed = JSON.parse(readFileSync(new URL('../../assets/demo-data.json', import.meta.url), 'utf8'));
function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)};
}
function fixture(store = storage()) {
  let counter = 0;
  const raw = new DemoProvider(seed, {storage: store, newId: () => `new-${++counter}`});
  return {raw, provider: prepareProvider(raw), store};
}

test('returned records are isolated from provider state and survive reload', async () => {
  const {provider, store} = fixture();
  const first = await provider.load();
  first.connections[0].messages[0].text = 'UI overwrite';
  assert.notEqual((await provider.load()).connections[0].messages[0].text, 'UI overwrite');
  const daily = await provider.saveDailyAnswer({questionId: first.daily.id, text: '  A sunny walk  '});
  assert.equal(daily.answer, 'A sunny walk');
  daily.answer = 'Another UI overwrite';
  assert.equal((await fixture(store).provider.load()).daily.answer, 'A sunny walk');
});

test('legacy sessions migrate answers, votes, messages, membership and opaque IDs', async () => {
  const connections = structuredClone(seed.seedConnections.slice(1));
  connections[0].reveal = 'waiting';
  connections[0].identity = 'Must be stripped';
  connections[0].messages.push({from: 'me', text: 'A previous message'});
  const store = storage({'intersect-demo-v1': JSON.stringify({
    answer: 'Legacy answer', vote: 2, completed: true, connections,
    questions: [...seed.seedQuestions, {id: 123, category: 'Advice', text: 'Old question',
      detail: '', alias: 'Juniper', time: 'Now', responses: [{alias: 'Juniper', text: 'Old reply'}]}],
    groups: {coding: {joined: true, messages: [{from: 'me', alias: 'You', text: 'Old group message'}]}},
  })});
  const {provider} = fixture(store);
  const data = await provider.load();
  assert.equal(data.daily.answer, 'Legacy answer');
  assert.equal(data.poll.vote, 'coffee');
  assert.equal(data.completed, true);
  assert.equal(data.connections.length, 2);
  assert.equal(data.connections[0].identity, null);
  assert.equal(data.connections[0].messages.at(-1).text, 'A previous message');
  assert.equal(data.questions.at(-1).id, '123');
  assert.equal(data.questions.at(-1).responses[0].isMine, true);
  assert.equal(data.groups[0].joined, true);
  assert.equal(data.groups[0].size, seed.groups[0].size + 1);
  assert.equal(data.groups[0].messages[0].text, 'Old group message');
  assert.equal(JSON.parse(store.getItem(DEMO_STORAGE_KEY)).version, 1);
});

test('failed writes leave both the snapshot and storage unchanged', async () => {
  const {provider, store} = fixture();
  const before = await provider.load();
  const saved = store.getItem(DEMO_STORAGE_KEY);
  await assert.rejects(provider.saveDailyAnswer({questionId: 'stale', text: 'Hello'}), ProviderError);
  await assert.rejects(provider.voteOnPoll({pollId: before.poll.id, choiceId: 'missing'}), ProviderError);
  await assert.rejects(provider.sendMessage({connectionId: 'missing', text: 'Hello'}), ProviderError);
  await assert.rejects(provider.sendGroupMessage({groupId: before.groups[0].id, text: 'Not joined'}), ProviderError);
  await assert.rejects(provider.postQuestion({category: 'Unknown', text: 'Hello', detail: ''}), ProviderError);
  assert.equal(store.getItem(DEMO_STORAGE_KEY), saved);
  assert.deepEqual(await provider.load(), before);
});

test('writes return canonical records; join is idempotent and authors are provider-owned', async () => {
  const {provider} = fixture();
  const data = await provider.load();
  const groupId = data.groups[0].id;
  const joined = await provider.joinGroup({groupId});
  assert.equal(joined.size, data.groups[0].size + 1);
  assert.equal((await provider.joinGroup({groupId})).size, joined.size);
  const group = await provider.sendGroupMessage({groupId, text: 'Hello group'});
  assert.equal(group.messages.at(-1).from, 'me');
  const question = await provider.postQuestion({category: data.categories[0], text: 'A question?', detail: ''});
  assert.equal(question.alias, data.profile.alias);
  const reply = await provider.replyToQuestion({questionId: question.id, text: 'My reply'});
  assert.equal(reply.responses[0].isMine, true);
  await assert.rejects(provider.createConnection({kind: 'question-response', questionId: question.id,
    responseId: reply.responses[0].id}), ProviderError);
  const message = await provider.sendMessage({connectionId: data.connections[0].id, text: '  Hello peer  '});
  assert.equal(message.messages.at(-1).text, 'Hello peer');
  assert.equal(message.messages.at(-1).from, 'me');
});

test('connection contexts resolve scoped references rather than trusting a submitted alias', async () => {
  const {provider} = fixture();
  const data = await provider.load();
  const response = data.daily.responses[1];
  const result = await provider.createConnection({kind: 'daily-answer', questionId: data.daily.id,
    responseId: response.id, alias: 'Forged name'});
  assert.equal(result.connection.alias, response.alias);
  assert.equal(result.completed, true);
  await assert.rejects(provider.createConnection({kind: 'question-response', questionId: data.questions[1].id,
    responseId: data.questions[0].responses[0].id}), ProviderError);
  await provider.voteOnPoll({pollId: data.poll.id, choiceId: 'coffee'});
  assert.equal((await provider.createConnection({kind: 'poll', pollId: data.poll.id})).connection.alias, 'River');
});

test('identity remains null until consent; cancellation and removal return confirmed changes', async () => {
  const {provider} = fixture();
  const {connections} = await provider.load();
  const connectionId = connections[0].id;
  await assert.rejects(provider.simulateIdentityConsent({connectionId}), ProviderError);
  const waiting = await provider.requestIdentityReveal({connectionId});
  assert.equal(waiting.reveal, 'waiting');
  assert.equal(waiting.identity, null);
  assert.equal((await provider.cancelIdentityReveal({connectionId})).reveal, null);
  await provider.requestIdentityReveal({connectionId});
  assert.equal((await provider.simulateIdentityConsent({connectionId})).reveal, 'revealed');
  assert.equal((await provider.cancelIdentityReveal({connectionId})).reveal, 'revealed');
  await provider.endConversation({connectionId});
  await assert.rejects(provider.reportConnection({connectionId: connections[1].id, reason: ''}), ProviderError);
  await provider.reportConnection({connectionId: connections[1].id, reason: 'Spam'});
  await provider.blockConnection({connectionId: connections[2].id});
  assert.deepEqual((await provider.load()).connections, []);
});

test('contracts reject concealed identities and duplicate IDs', async () => {
  const {provider} = fixture();
  const data = await provider.load();
  const hiddenIdentity = structuredClone(data);
  hiddenIdentity.connections[0].identity = 'Private name';
  assert.throws(() => assertAppData(hiddenIdentity), ProviderError);
  data.connections.push(structuredClone(data.connections[0]));
  assert.throws(() => assertAppData(data), ProviderError);
});

test('explicit provider failures propagate without demo fallback; production disables simulation', async () => {
  const {raw} = fixture();
  const external = {capabilities: {simulateIdentityConsent: false}};
  for (const name of Object.keys(resultValidators)) external[name] = raw[name].bind(raw);
  const original = globalThis.window;
  try {
    globalThis.window = {intersectProviderFactory: async () => external};
    const provider = await createProvider();
    assert.equal(provider.simulateIdentityConsent, undefined);
    assert.equal(provider.capabilities.simulateIdentityConsent, false);
    assertAppData(await provider.load());
    window.intersectProviderFactory = async () => { throw new ProviderError('Server unavailable'); };
    await assert.rejects(createProvider(), /Server unavailable/);
    external.load = async () => ({broken: true});
    await assert.rejects(prepareProvider(external).load(), ProviderError);
  } finally { globalThis.window = original; }
});

test('UI preference storage omits domain records and identities', () => {
  const original = globalThis.sessionStorage;
  try {
    globalThis.sessionStorage = storage();
    saveUiState({activeId: 'connection-1', activity: 'poll', dismissed: {},
      connections: [{identity: 'Private'}], answer: 'Domain answer', profile: {name: 'Private'}});
    const persisted = JSON.parse(sessionStorage.getItem(UI_STORAGE_KEY));
    assert.equal(persisted.activeId, 'connection-1');
    assert.equal(persisted.activity, 'poll');
    assert.equal(persisted.connections, undefined);
    assert.equal(persisted.answer, undefined);
    assert.equal(persisted.profile, undefined);
    assert.equal(loadUiState().activity, 'poll');
  } finally { globalThis.sessionStorage = original; }
});
