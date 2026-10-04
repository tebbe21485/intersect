import {MIN_MESSAGES_PER_USER} from '../data/connection-floors.mjs';

export const CONNECTION_STATE_KEY = 'intersect-connection-floors-v1';
let memory = {connections: {}};
function read() {
  try {
    const state = JSON.parse(sessionStorage.getItem(CONNECTION_STATE_KEY));
    if (state?.version === 1 && state.connections) memory = state;
  } catch { /* Demo state works in memory when storage is unavailable. */ }
  return memory;
}
function save(state, notify = true) {
  memory = state;
  try { sessionStorage.setItem(CONNECTION_STATE_KEY, JSON.stringify({...state, version: 1})); } catch { /* Keep memory. */ }
  if (notify && typeof window !== 'undefined') window.dispatchEvent(new Event('intersect:connection-change'));
}
function ensure(state, key, ids) {
  if (!state.connections[key]) {
    if (ids.length !== 2 || new Set(ids).size !== 2) throw new Error('A connection needs two users.');
    state.connections[key] = {participantIds: [...ids].sort(), currentFloor: 1, messages: [], ready: {}, sensitive: {}, identityConsent: {}};
    save(state, false);
  }
  return state.connections[key];
}
function participant(connection, id) {
  if (!connection.participantIds.includes(id)) throw new Error('You are not part of this connection.');
}
function progress(connection) {
  const counts = Object.fromEntries(connection.participantIds.map(id => [id, Math.min(MIN_MESSAGES_PER_USER,
    connection.messages.filter(message => message.floor === connection.currentFloor && message.ownerId === id).length)]));
  const minimumMet = connection.participantIds.every(id => counts[id] >= MIN_MESSAGES_PER_USER);
  return {...connection, counts, canAdvance: connection.currentFloor < 4 && minimumMet,
    identityAvailable: connection.currentFloor > 2 || (connection.currentFloor === 2 && minimumMet),
    allowSensitivePrompts: connection.participantIds.every(id => connection.sensitive[id] === true)};
}
export function getConnectionState(key, ids) { return structuredClone(progress(ensure(read(), key, ids))); }
export function observeMessages(key, ids, messages) {
  const state = read(), connection = ensure(state, key, ids);
  const seen = new Set(connection.messages.map(message => message.id));
  const lastNumericId = Math.max(0, ...connection.messages.map(message => /^\d+$/.test(message.id) ? Number(message.id) : 0));
  const incoming = messages.filter(message => !seen.has(message.id));
  if (!incoming.length) return;
  for (const message of incoming) {
    if (seen.has(message.id)) continue;
    participant(connection, message.ownerId);
    const olderHistory = /^\d+$/.test(message.id) && Number(message.id) <= lastNumericId;
    connection.messages.push({...message, floor: olderHistory ? 0 : connection.currentFloor});
    seen.add(message.id);
  }
  save(state);
}
export function sendConnectionMessage(key, userId, text, requestId = crypto.randomUUID()) {
  if (typeof text !== 'string' || !text.trim() || text.trim().length > 1000) throw new Error('Write a message of 1 to 1000 characters.');
  const state = read(), connection = state.connections[key];
  if (!connection) throw new Error('Choose a connection first.');
  participant(connection, userId);
  const duplicate = connection.messages.find(message => message.ownerId === userId && message.requestId === requestId);
  if (duplicate) {
    if (duplicate.text !== text.trim()) throw new Error('This request was already used for another message.');
    return;
  }
  connection.messages.push({id: crypto.randomUUID(), ownerId: userId, text: text.trim(), time: 'Just now', requestId, floor: connection.currentFloor});
  save(state);
}
export function setFloorReady(key, userId, ready) {
  const state = read(), connection = state.connections[key];
  if (!connection) throw new Error('Choose a connection first.');
  participant(connection, userId);
  if (!progress(connection).canAdvance) throw new Error('Both people need two messages on this floor first.');
  connection.ready[userId] = Boolean(ready);
  if (connection.participantIds.every(id => connection.ready[id])) {
    connection.currentFloor++;
    connection.ready = {};
  }
  save(state);
}
export function setSensitiveOptIn(key, userId, enabled) {
  const state = read(), connection = state.connections[key];
  if (!connection) throw new Error('Choose a connection first.');
  participant(connection, userId);
  connection.sensitive[userId] = Boolean(enabled);
  save(state);
}
export function setIdentityConsent(key, userId, enabled) {
  const state = read(), connection = state.connections[key];
  if (!connection) throw new Error('Choose a connection first.');
  participant(connection, userId);
  if (!progress(connection).identityAvailable) throw new Error('Identity sharing is available after both people complete floor 2.');
  if (!enabled && connection.participantIds.every(id => connection.identityConsent[id])) throw new Error('Identity has already been revealed.');
  connection.identityConsent[userId] = Boolean(enabled);
  save(state);
}
