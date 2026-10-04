/**
 * Frontend data contracts. These are view models, independent of database tables.
 * Every ID is an opaque string supplied by the provider. Methods return confirmed
 * records, and reject on failure; the UI never invents a successful backend write.
 * See docs/backend-integration.md for the complete provider interface.
 *
 * @typedef {{id:string, alias:string, name:string, firstName:string, lastName:string, linkedin:string, phone:string, email:string|null, role:'user'|'admin'}} Profile
 * @typedef {{id:string, alias:string, color:string, text:string, interest:string}} DailyResponse
 * @typedef {{id:string, text:string, answer:string, status:'draft'|'published'|'closed'|'archived', responses:DailyResponse[]}} DailyQuestion
 * @typedef {{id:string, text:string, icon:string, percent:number|null}} PollChoice
 * @typedef {{id:string, question:string, choices:PollChoice[], vote:string|null, totalVotes:number|null, resultsPublic:boolean, status:string}} Poll
 * @typedef {{id:string, from:'me'|'them', text:string, time:string}} Message
 * @typedef {{firstName:string, lastName:string, linkedin:string}} PeerIdentity
 * @typedef {{id:string, alias:string, color:string, source:string, shared:string, interests:string[], preview:string, time:string, messages:Message[], reveal:null|'waiting'|'revealed', identity:string|null, identityDetails:PeerIdentity|null, myConsent:boolean, peerConsent:boolean, phone:string|null, phoneShared:boolean, hasOlderMessages:boolean, incremental:boolean}} Connection
 * @typedef {{id:string, alias:string, text:string, isMine:boolean}} Response
 * @typedef {{id:string, category:string, text:string, detail:string, alias:string, time:string, responses:Response[]}} Question
 * @typedef {{id:string, name:string, icon:string, color:string, size:number, description:string, activity:string, question:string, joined:boolean, approval:'pending'|'approved'|'rejected', status:'open'|'closed'|'archived', decisionReason:string, isMine:boolean, messages:Array<Message & {alias:string}>}} Group
 * @typedef {{profile:Profile, dailyQuestions:DailyQuestion[], polls:Poll[], completed:boolean, connections:Connection[], groups:Group[], groupProposals:Group[], questions:Question[], categories:string[]}} AppData
 * @typedef {{kind:'daily-answer', questionId:string, responseId:string}|{kind:'similar-answer', questionId:string}|{kind:'poll', pollId:string}|{kind:'question-response', questionId:string, responseId:string}} ConnectionContext
 * @typedef {{connection:Connection, completed:boolean}} ConnectionResult
 * @typedef {Object} DataProvider
 * @property {{simulateIdentityConsent:boolean}} capabilities
 * @property {() => Promise<AppData>} load
 * @property {(input:{questionId:string,text:string}) => Promise<DailyQuestion>} saveDailyAnswer
 * @property {(input:{pollId:string,choiceId:string}) => Promise<Poll>} voteOnPoll
 * @property {(context:ConnectionContext) => Promise<ConnectionResult>} createConnection
 * @property {(input:{connectionId:string,text:string}) => Promise<Connection>} sendMessage
 * @property {(input:{groupId:string}) => Promise<Group>} joinGroup
 * @property {(input:{groupId:string,text:string}) => Promise<Group>} sendGroupMessage
 * @property {(input:{category:string,text:string,detail:string}) => Promise<Question>} postQuestion
 * @property {(input:{questionId:string,text:string}) => Promise<Question>} replyToQuestion
 * @property {(input:{connectionId:string}) => Promise<Connection>} requestIdentityReveal
 * @property {(input:{connectionId:string}) => Promise<Connection>} cancelIdentityReveal
 * @property {(input:{connectionId:string}) => Promise<void>} endConversation
 * @property {(input:{connectionId:string,reason:string}) => Promise<void>} reportConnection
 * @property {(input:{connectionId:string}) => Promise<void>} blockConnection
 * @property {(input:{connectionId:string}) => Promise<Connection>} [simulateIdentityConsent]
 */

export class ProviderError extends Error {
  constructor(userMessage) {
    super(userMessage);
    this.name = 'ProviderError';
    this.userMessage = userMessage;
  }
}

function assert(condition) {
  if (!condition) throw new ProviderError('The data could not be loaded. Please try again.');
}
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const strings = (value, fields) => object(value) && fields.every(key => typeof value[key] === 'string');
const list = (values, validate) => Array.isArray(values)
  && values.every(value => { validate(value); return true; })
  && new Set(values.map(value => value.id)).size === values.length;
const id = value => typeof value === 'string' && value.length > 0;
const palette = value => ['blue', 'yellow', 'green'].includes(value);

export function assertDaily(value) {
  assert(strings(value, ['id', 'text', 'answer']) && id(value.id));
  assert(list(value.responses, response => {
    assert(strings(response, ['id', 'alias', 'color', 'text', 'interest']) && id(response.id) && palette(response.color));
  }));
  return value;
}
export function assertPoll(value) {
  assert(strings(value, ['id', 'question']) && id(value.id));
  assert(list(value.choices, choice => {
    assert(strings(choice, ['id', 'text', 'icon']) && id(choice.id) && (choice.percent === null || (Number.isFinite(choice.percent) && choice.percent >= 0 && choice.percent <= 100)));
  }));
  assert(value.vote === null || value.choices.some(choice => choice.id === value.vote));
  assert(value.totalVotes === null || (Number.isFinite(value.totalVotes) && value.totalVotes >= 0));
  if (value.resultsPublic === false) assert(value.totalVotes === null && value.choices.every(choice => choice.percent === null && choice.count === undefined));
  return value;
}
function assertMessage(value) {
  assert(strings(value, ['id', 'text', 'time']) && id(value.id) && ['me', 'them'].includes(value.from));
}
export function assertConnection(value) {
  assert(strings(value, ['id', 'alias', 'color', 'source', 'shared', 'preview', 'time']) && id(value.id) && palette(value.color));
  assert(Array.isArray(value.interests) && value.interests.every(interest => typeof interest === 'string'));
  assert(list(value.messages, assertMessage));
  assert([null, 'waiting', 'revealed'].includes(value.reveal));
  // The frontend must never receive a hidden peer's real identity.
  assert(value.reveal === 'revealed' ? typeof value.identity === 'string' : value.identity === null);
  if (value.identityDetails !== undefined) assert(value.reveal === 'revealed' ? strings(value.identityDetails, ['firstName', 'lastName', 'linkedin']) : value.identityDetails === null);
  return value;
}
export function assertGroup(value) {
  assert(strings(value, ['id', 'name', 'icon', 'color', 'description', 'activity', 'question']) && id(value.id) && palette(value.color));
  assert(typeof value.joined === 'boolean' && Number.isFinite(value.size) && value.size >= 0);
  assert(list(value.messages, message => { assertMessage(message); assert(typeof message.alias === 'string'); }));
  return value;
}
export function assertQuestion(value) {
  assert(strings(value, ['id', 'category', 'text', 'detail', 'alias', 'time']) && id(value.id));
  assert(list(value.responses, response => {
    assert(strings(response, ['id', 'alias', 'text']) && id(response.id) && typeof response.isMine === 'boolean');
  }));
  return value;
}
export function assertAppData(value) {
  assert(object(value) && strings(value.profile, ['id', 'alias', 'name']) && id(value.profile.id));
  // Legacy snapshots are accepted only for the explicitly injected demo provider.
  assert(list(value.dailyQuestions ?? [value.daily], assertDaily));
  assert(list(value.polls ?? [value.poll], assertPoll));
  assert(typeof value.completed === 'boolean');
  assert(list(value.connections, assertConnection) && list(value.groups, assertGroup) && list(value.questions, assertQuestion));
  if (value.groupProposals !== undefined) assert(list(value.groupProposals, assertGroup));
  assert(Array.isArray(value.categories) && value.categories.every(category => typeof category === 'string'));
  return value;
}

export const resultValidators = {
  load: assertAppData,
  saveDailyAnswer: assertDaily,
  voteOnPoll: assertPoll,
  createConnection: value => { assert(object(value) && typeof value.completed === 'boolean'); assertConnection(value.connection); return value; },
  sendMessage: assertConnection,
  joinGroup: assertGroup,
  sendGroupMessage: assertGroup,
  postQuestion: assertQuestion,
  replyToQuestion: assertQuestion,
  requestIdentityReveal: assertConnection,
  cancelIdentityReveal: assertConnection,
  endConversation: value => value,
  reportConnection: value => value,
  blockConnection: value => value,
};

/** Validate a provider and its replies before the presentation layer uses them. */
export function prepareProvider(provider) {
  assert(object(provider) && object(provider.capabilities));
  assert(typeof provider.capabilities.simulateIdentityConsent === 'boolean');
  const wrapped = {capabilities: {...provider.capabilities}};
  for (const [method, validate] of Object.entries(resultValidators)) {
    assert(typeof provider[method] === 'function');
    wrapped[method] = async (...args) => validate(await provider[method](...args));
  }
  if (provider.capabilities.simulateIdentityConsent) {
    assert(typeof provider.simulateIdentityConsent === 'function');
    wrapped.simulateIdentityConsent = async input => assertConnection(await provider.simulateIdentityConsent(input));
  }
  for (const method of ['saveProfile','proposeGroup','editGroupProposal','sharePhone','loadOlderMessages']) {
    if (typeof provider[method] === 'function') wrapped[method] = (...args) => provider[method](...args);
  }
  return wrapped;
}
