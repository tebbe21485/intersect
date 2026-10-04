import {action, request, session} from './http.mjs';

export async function createBackendProvider() {
  const current = await session();
  if (!current.profile) { window.location.assign('/login'); throw new Error('Please sign in.'); }
  const provider = {capabilities: {simulateIdentityConsent: false, automaticMatching: false, backend: true}, load: ({afterMessages} = {}) => request(afterMessages ? `load?afterMessages=${encodeURIComponent(JSON.stringify(afterMessages))}` : 'load')};
  for (const method of ['saveDailyAnswer','voteOnPoll','createConnection','sendMessage','joinGroup','sendGroupMessage','postQuestion','replyToQuestion','requestIdentityReveal','cancelIdentityReveal','endConversation','reportConnection','blockConnection','saveProfile','proposeGroup','editGroupProposal','sharePhone']) {
    provider[method] = input => action(method, input);
  }
  provider.loadOlderMessages = ({connectionId, before}) => request(`messages?connectionId=${encodeURIComponent(connectionId)}&before=${encodeURIComponent(before)}`);
  return provider;
}
