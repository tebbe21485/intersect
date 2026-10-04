/**
 * Local demo implementation of DataProvider. All fabricated users, matches,
 * identities and storage belong here, never in presentation/event handlers.
 * Messages use the backend word filter before entering local demo state.
 */
import {assertAppData, ProviderError} from './contracts.mjs';

export const DEMO_STORAGE_KEY = 'intersect-demo-data-v2';
const LEGACY_STORAGE_KEY = 'intersect-demo-v1';
const copy = value => structuredClone(value);
const moderateMessage = async message => (await import('./http.mjs')).moderateMessage(message);
const text = (value, max) => {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > max) {
    throw new ProviderError(`Please enter between 1 and ${max} characters.`);
  }
  return value.trim();
};
function read(storage, key) {
  try { return JSON.parse(storage?.getItem(key)); } catch { return null; }
}
function normalizeMessage(message, id, group = false) {
  return {...message, id: String(message.id || id), time: message.time || '2:16 PM', ...(group ? {alias: message.alias || 'You'} : {})};
}
function normalizeConnection(connection) {
  return {...connection, id: String(connection.id), reveal: connection.reveal || null,
    identity: connection.reveal === 'revealed' ? connection.identity : null,
    messages: connection.messages.map((message, i) => normalizeMessage(message, `${connection.id}-message-${i}`))};
}
function normalizeQuestion(question) {
  return {...question, id: String(question.id), responses: question.responses.map((response, i) => ({
    ...response, id: String(response.id || `${question.id}-response-${i}`), isMine: response.isMine ?? response.alias === 'Juniper',
  }))};
}
function initialData(seed, legacy) {
  const choices = [
    ['nature', 'A nature walk', 'leaf', 38], ['creative', 'A creative project', 'palette', 24],
    ['coffee', 'Coffee with friends', 'coffee', 27], ['book', 'Getting lost in a book', 'book-open', 11],
  ].map(([id, label, icon, percent]) => ({id, text: label, icon, percent}));
  return {
    profile: {id: 'demo-juniper', alias: 'Juniper', name: 'Juniper Lee'},
    daily: {id: 'demo-daily-question', text: seed.dailyQuestion, answer: legacy?.answer || '',
      responses: seed.answers.map((answer, i) => ({...answer, id: `demo-daily-response-${i}`}))},
    poll: {id: 'demo-afternoon-poll', question: 'Your ideal way to spend a free afternoon?', choices,
      vote: Number.isInteger(legacy?.vote) ? choices[legacy.vote]?.id || null : null, totalVotes: 128},
    completed: Boolean(legacy?.completed),
    connections: (legacy?.connections || seed.seedConnections).map(normalizeConnection),
    questions: (legacy?.questions || seed.seedQuestions).map(normalizeQuestion),
    categories: seed.categories.filter(category => category !== 'All'),
    groups: seed.groups.map(group => {
      const local = legacy?.groups?.[group.id];
      return {...group, id: String(group.id), joined: Boolean(local?.joined),
        size: group.size + Number(Boolean(local?.joined)),
        messages: (local?.messages || group.messages).map((message, i) => normalizeMessage(message, `${group.id}-message-${i}`, true))};
    }),
  };
}

/** @implements {import('./contracts.mjs').DataProvider} */
export class DemoProvider {
  capabilities = {simulateIdentityConsent: true};
  constructor(seed, {storage = null, newId = () => crypto.randomUUID(), validateMessage = moderateMessage} = {}) {
    this.storage = storage;
    this.newId = newId;
    this.validateMessage = validateMessage;
    const stored = read(storage, DEMO_STORAGE_KEY);
    try {
      this.data = stored?.version === 1 ? assertAppData(stored.data) : assertAppData(initialData(seed, read(storage, LEGACY_STORAGE_KEY)));
    } catch {
      this.data = assertAppData(initialData(seed, null));
    }
  }
  _save() {
    try { this.storage?.setItem(DEMO_STORAGE_KEY, JSON.stringify({version: 1, data: this.data})); } catch { /* Continue in memory if browser storage is unavailable. */ }
  }
  _commit(operation) {
    const next = copy(this.data);
    const result = operation(next);
    assertAppData(next);
    this.data = next;
    this._save();
    return copy(result);
  }
  _find(records, id) {
    const record = records.find(item => item.id === id);
    if (!record) throw new ProviderError('That item is no longer available. Please refresh and try again.');
    return record;
  }
  async load() { this._save(); return copy(this.data); }
  async saveDailyAnswer({questionId, text: answer}) {
    return this._commit(data => {
      if (questionId !== data.daily.id) throw new ProviderError('The daily question has changed. Please refresh.');
      data.daily.answer = text(answer, 500);
      return data.daily;
    });
  }
  async voteOnPoll({pollId, choiceId}) {
    return this._commit(data => {
      if (pollId !== data.poll.id) throw new ProviderError('The poll has changed. Please refresh.');
      this._find(data.poll.choices, choiceId);
      data.poll.vote = choiceId;
      return data.poll;
    });
  }
  async createConnection(context) {
    return this._commit(data => {
      let alias, source, shared;
      if (['daily-answer', 'similar-answer'].includes(context.kind)) {
        if (context.questionId !== data.daily.id) throw new ProviderError('The daily question has changed. Please refresh.');
        const response = context.kind === 'similar-answer' ? data.daily.responses[0] : this._find(data.daily.responses, context.responseId);
        if (!response) throw new ProviderError('No match is available yet. Please try again later.');
        alias = response.alias;
        source = context.kind === 'similar-answer' ? 'Similar daily answer' : 'Daily question';
        shared = context.kind === 'similar-answer' ? data.daily.answer : response.text;
      } else if (context.kind === 'poll') {
        if (context.pollId !== data.poll.id || !data.poll.vote) throw new ProviderError('Choose a poll answer first.');
        const choice = this._find(data.poll.choices, data.poll.vote);
        alias = choice.id === 'coffee' ? 'River' : 'Willow'; source = 'Mini poll'; shared = choice.text;
      } else if (context.kind === 'question-response') {
        const question = this._find(data.questions, context.questionId);
        const response = this._find(question.responses, context.responseId);
        if (response.isMine) throw new ProviderError('Choose someone else’s response to connect.');
        alias = response.alias; source = 'Question board'; shared = question.text;
      } else throw new ProviderError('This connection could not be started.');
      let connection = data.connections.find(item => item.alias === alias);
      if (!connection) {
        connection = {id: this.newId(), alias, source, shared,
          color: data.connections.length % 2 ? 'yellow' : 'blue',
          interests: [source === 'Mini poll' ? 'Shared choice' : 'Shared perspective'],
          time: 'Just now', preview: 'A new conversation is waiting.', reveal: null, identity: null,
          messages: [{id: this.newId(), from: 'them', text: 'Hey! It’s nice to meet someone who connected with this too. What stood out to you?', time: '2:14 PM'}]};
        data.connections.push(connection);
      }
      data.completed = true;
      return {connection, completed: data.completed};
    });
  }
  async sendMessage({connectionId, text: message}) {
    const content = text(message, 1000);
    await this.validateMessage(content);
    return this._commit(data => {
      const connection = this._find(data.connections, connectionId);
      connection.messages.push({id: this.newId(), from: 'me', text: content, time: 'Just now'});
      connection.preview = content; connection.time = 'Just now';
      return connection;
    });
  }
  async joinGroup({groupId}) {
    return this._commit(data => {
      const group = this._find(data.groups, groupId);
      if (!group.joined) { group.joined = true; group.size += 1; }
      return group;
    });
  }
  async sendGroupMessage({groupId, text: message}) {
    const content = text(message, 1000);
    await this.validateMessage(content);
    return this._commit(data => {
      const group = this._find(data.groups, groupId);
      if (!group.joined) throw new ProviderError('Join the discussion before sending a message.');
      group.messages.push({id: this.newId(), alias: 'You', from: 'me', text: content, time: 'Just now'});
      return group;
    });
  }
  async postQuestion({category, text: title, detail}) {
    return this._commit(data => {
      if (!data.categories.includes(category)) throw new ProviderError('Please choose a valid category.');
      if (typeof detail !== 'string' || detail.trim().length > 800) throw new ProviderError('Please keep the context under 800 characters.');
      const question = {id: this.newId(), category, text: text(title, 180), detail: detail.trim(), alias: data.profile.alias, time: 'Just now', responses: []};
      data.questions.unshift(question);
      return question;
    });
  }
  async replyToQuestion({questionId, text: response}) {
    return this._commit(data => {
      const question = this._find(data.questions, questionId);
      question.responses.push({id: this.newId(), alias: data.profile.alias, text: text(response, 800), isMine: true});
      return question;
    });
  }
  async requestIdentityReveal({connectionId}) {
    return this._commit(data => {
      const connection = this._find(data.connections, connectionId);
      if (connection.reveal !== 'revealed') connection.reveal = 'waiting';
      return connection;
    });
  }
  async cancelIdentityReveal({connectionId}) {
    return this._commit(data => {
      const connection = this._find(data.connections, connectionId);
      if (connection.reveal === 'waiting') connection.reveal = null;
      return connection;
    });
  }
  async simulateIdentityConsent({connectionId}) {
    return this._commit(data => {
      const connection = this._find(data.connections, connectionId);
      if (connection.reveal !== 'waiting') throw new ProviderError('Request an identity unlock first.');
      connection.reveal = 'revealed';
      connection.identity = connection.alias === 'River' ? 'Sam Rivera' : connection.alias === 'Sage' ? 'Taylor Chen' : 'Alex Morgan';
      return connection;
    });
  }
  async endConversation({connectionId}) {
    this._commit(data => { this._find(data.connections, connectionId); data.connections = data.connections.filter(item => item.id !== connectionId); });
  }
  async blockConnection({connectionId}) { await this.endConversation({connectionId}); }
  async reportConnection({connectionId, reason}) {
    text(reason, 500);
    await this.endConversation({connectionId});
  }
}

export async function createDemoProvider() {
  const response = await fetch('/demo-data.json');
  if (!response.ok) throw new ProviderError('The demo data could not be loaded. Please try again.');
  let storage = null;
  try { storage = sessionStorage; } catch { /* Demo can run without storage. */ }
  return new DemoProvider(await response.json(), {storage});
}
