import {DemoProvider} from './demo-provider.mjs';
import {DEMO_ACCOUNTS, DEMO_RELATIONS, connectionKey} from './puzzle-store.mjs';
import {getConnectionState, observeMessages, sendConnectionMessage, setIdentityConsent} from './connection-state.mjs';
import {ProviderError} from './contracts.mjs';

const identities = {'demo-juniper': 'Juniper Lee', 'demo-maple': 'Alex Morgan', 'demo-river': 'Sam Rivera', 'demo-sage': 'Taylor Chen'};

/** Explicitly selected local demo; never a fallback for failed backend requests. */
export async function createPuzzleDemoProvider(account, options = {}) {
  const response = await fetch('/demo-data.json');
  if (!response.ok) throw new Error('Unable to load sample conversations.');
  const provider = new DemoProvider(await response.json(), options);
  provider.capabilities = {simulateIdentityConsent: false};
  provider.data.profile = {id: account.id, alias: account.alias, name: identities[account.id]};
  provider.data.connections = DEMO_RELATIONS.filter(relation => relation.users.includes(account.id)).map(relation => {
    const peer = DEMO_ACCOUNTS.find(a => a.id === relation.users.find(id => id !== account.id));
    const key = connectionKey(...relation.users);
    const existing = getConnectionState(key, relation.users);
    if (!existing.messages.length) observeMessages(key, relation.users, [
      {id: `${key}-hello`, ownerId: relation.users[0], text: `Hi! We connected through ${relation.shared.toLowerCase()}.`, time: 'Just now'},
      {id: `${key}-reply`, ownerId: relation.users[1], text: 'Nice to meet you! Want to share a little of our stories?', time: 'Just now'},
    ]);
    return {
      id: key, peerId: peer.id, puzzleKey: key, alias: peer.alias,
      color: 'blue', source: relation.source, shared: relation.shared,
      interests: [relation.shared], preview: 'I would love to hear a little more about you.', time: 'Just now',
      reveal: null, identity: null,
      messages: [],
    };
  });
  const project = connection => {
    const state = getConnectionState(connection.id, [account.id, connection.peerId]);
    const mine = Boolean(state.identityConsent[account.id]);
    const theirs = Boolean(state.identityConsent[connection.peerId]);
    const revealed = state.identityAvailable && mine && theirs;
    const messages = state.messages.map(message => ({id: message.id, text: message.text, time: message.time, kind: message.kind || 'message', from: message.ownerId === account.id ? 'me' : 'them'}));
    return {...connection, messages, preview: messages.at(-1)?.text || '', myConsent: mine, peerConsent: theirs,
      reveal: revealed ? 'revealed' : mine ? 'waiting' : null,
      identity: revealed ? identities[connection.peerId] : null};
  };
  provider.load = async () => ({...structuredClone(provider.data), connections: provider.data.connections.map(project)});
  const find = id => {
    const connection = provider.data.connections.find(connection => connection.id === id);
    if (!connection) throw new ProviderError('This conversation is no longer available.');
    return connection;
  };
  const apply = operation => {
    try { operation(); } catch (error) { throw new ProviderError(error.message); }
  };
  provider.sendMessage = async ({connectionId, text, requestId, kind = 'message'}) => {
    const connection = find(connectionId);
    await provider.validateMessage(text);
    apply(() => sendConnectionMessage(connection.id, account.id, text, requestId, kind));
    return project(connection);
  };
  provider.requestIdentityReveal = async ({connectionId}) => {
    const connection = find(connectionId);
    apply(() => setIdentityConsent(connection.id, account.id, true,
      Object.fromEntries(Object.entries(identities).map(([id, name]) => [id, {name}]))));
    return project(connection);
  };
  provider.cancelIdentityReveal = async ({connectionId}) => {
    const connection = find(connectionId);
    apply(() => setIdentityConsent(connection.id, account.id, false));
    return project(connection);
  };
  return provider;
}
