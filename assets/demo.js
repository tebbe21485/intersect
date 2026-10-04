/* Intersect presentation and UI events.
 * All domain reads/writes go through services/provider.mjs. The default provider
 * uses the authenticated Reflex/Python backend.
 * Only UI preferences are persisted here. Rendered user content is escaped.
 */
(async () => {
  if (window.intersectDemoLoaded) return;
  window.intersectDemoLoaded = true;
  if (document.querySelector('[data-page="welcome"]')) {
    document.documentElement.dataset.demoReady = 'true';
    return;
  }
  if (document.querySelector('[data-page="admin"]')) {
    document.getElementById('data-status').hidden = true;
    return;
  }
  const {createProvider} = await import('/services/provider.mjs');
  const {loadUiState, saveUiState} = await import('/services/ui-state.mjs');
  const ui = loadUiState();
  let data = null, provider = null, pending = false;
  let revision = 0, refreshing = false;
  const answerDrafts = new Map();
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escape = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const paths = {
    'leaf': '<path d="M11 20A7 7 0 0 1 4 13C4 4 20 3 20 3s-1 16-10 16m-7 3L16 9"/>',
    'palette': '<path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-4c-1-1 0-3 2-3h2a3 3 0 0 0 3-3 9 9 0 0 0-9-8Z"/><circle cx="7" cy="10" r=".5"/><circle cx="10" cy="7" r=".5"/><circle cx="15" cy="7" r=".5"/>',
    'coffee': '<path d="M18 8h1a3 3 0 0 1 0 6h-1M3 8h15v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3ZM6 2v3m4-3v3m4-3v3"/>',
    'book-open': '<path d="M12 7c-3-3-7-3-10-2v14c3-1 7-1 10 2 3-3 7-3 10-2V5c-3-1-7-1-10 2Zm0 0v14"/>',
    'code': '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    'music': '<path d="M9 18V5l12-2v13M9 8l12-2"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3a4 4 0 0 1 0 8"/><circle cx="9" cy="7" r="4"/>',
    'gamepad-2': '<path d="M6 12h4m-2-2v4m7-1h.01m3-2h.01M6 8h12c2 0 3 2 4 8s-2 6-5 2H7c-3 4-6 4-5-2S4 8 6 8Z"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    'arrow-right': '<path d="M5 12h14m-7-7 7 7-7 7"/>',
    'arrow-left': '<path d="M19 12H5m7 7-7-7 7-7"/>',
    'lock': '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4m-5 5v2"/>',
    'send': '<path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13"/>',
    'x': '<path d="m18 6-12 12M6 6l12 12"/>',
    'check': '<path d="m20 6-11 11-5-5"/>',
    'message': '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
    'flag': '<path d="M4 22V3m0 1s3-3 8 0 8 0 8 0v11s-3 3-8 0-8 0-8 0"/>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14 5-5-5-5M21 12H9"/>',
  };
  const icon = (name, size = 16) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[({Code: 'code', Music: 'music', Users: 'users', Gamepad2: 'gamepad-2', Flag: 'flag'})[name] || name] || paths.message}</svg>`;
  const avatar = (alias, color = 'blue', small = false) => `<span class="avatar ${escape(color)} ${small ? 'small' : ''}" aria-hidden="true">${escape(alias[0])}</span>`;
  const button = (label, action, extra = '', variant = 'primary', classes = '') => `<button type="button" class="btn ${variant} ${classes}" data-action="${action}" ${extra}>${label}</button>`;
  const name = c => c.reveal === 'revealed' ? c.identity : c.alias;
  const newRequestId = () => crypto.randomUUID?.() || [...crypto.getRandomValues(new Uint8Array(16))].map(n => n.toString(16).padStart(2,'0')).join('');
  const displayTime = value => {
    const parsed = new Date(/^\d{4}-\d{2}-\d{2} \d{2}:/.test(value) ? value.replace(' ', 'T') + 'Z' : value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {hour:'numeric',minute:'2-digit',...(parsed.toDateString() === new Date().toDateString() ? {} : {month:'short',day:'numeric'})}).format(parsed);
  };
  const active = () => data.connections.find(c => c.id === ui.activeId);
  const persist = () => saveUiState(ui);
  const replaceRecord = (records, record) => records.map(item => item.id === record.id ? record : item);
  async function runOperation(operation) {
    if (pending || !data) return;
    pending = true;
    revision++;
    const controls = $$('button, form input, form textarea, form select').map(control => [control, control.disabled]);
    controls.forEach(([control]) => { control.disabled = true; });
    $('[data-page]')?.setAttribute('aria-busy', 'true');
    try { await operation(); }
    catch (error) { notify(error.userMessage || 'That change could not be saved. Please try again.'); }
    finally {
      pending = false;
      controls.forEach(([control, disabled]) => { if (control.isConnected) control.disabled = disabled; });
      $('[data-page]')?.setAttribute('aria-busy', 'false');
    }
  }
  let toastTimer;
  function notify(message) {
    const toast = $('#demo-toast');
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
  }
  let previousFocus;
  function showModal(title, body) {
    const modal = $('#demo-modal');
    if (!modal.open) previousFocus = document.activeElement;
    $('#modal-title').textContent = title;
    $('#modal-body').innerHTML = body;
    if (!modal.open) modal.showModal();
  }
  function closeModal() {
    $('#demo-modal')?.close();
    if (previousFocus?.isConnected) previousFocus.focus();
  }
  function setActivity(key, focus = false) {
    ui.activity = key;
    $$('[data-action="activity"]').forEach(tab => {
      const selected = tab.dataset.activity === key;
      tab.setAttribute('aria-selected', selected);
      tab.tabIndex = selected ? 0 : -1;
      const panel = $(`#panel-${tab.dataset.activity}`);
      if (panel) panel.hidden = !selected;
    });
    if (focus) $(`#activity-${key}`)?.focus();
    persist();
  }
  function renderAnswer() {
    $$('[data-action="similar-answer"]').forEach(el => { el.hidden = provider.capabilities.automaticMatching === false; });
    if (!data.daily) {
      if ($('#daily-question-title')) $('#daily-question-title').textContent = 'No active questions yet.';
      if ($('#daily-form')) $('#daily-form').hidden = true;
      if ($('#daily-selector')) $('#daily-selector').parentElement.hidden = true;
      if ($('#daily-responses')) $('#daily-responses').innerHTML = '<p class="muted">An admin will publish questions here.</p>';
      if ($('#your-answer-card')) $('#your-answer-card').hidden = true;
      return;
    }
    if ($('#daily-form')) $('#daily-form').hidden = false;
    if ($('#daily-selector')) {
      $('#daily-selector').parentElement.hidden = data.dailyQuestions.length < 2;
      $('#daily-selector').innerHTML = data.dailyQuestions.map(q => `<option value="${escape(q.id)}" ${q.id === data.daily.id ? 'selected' : ''}>${escape(q.text)}${q.status === 'closed' ? ' (closed)' : ''}</option>`).join('');
    }
    if ($('#daily-question-title')) $('#daily-question-title').textContent = data.daily.text;
    if ($('#daily-response')) {
      $('#daily-response').value = answerDrafts.get(data.daily.id) ?? data.daily.answer;
      $('#daily-response').disabled = data.daily.status === 'closed';
      $('#daily-form button').disabled = data.daily.status === 'closed';
    }
    if ($('#daily-submit-label')) $('#daily-submit-label').textContent = data.daily.answer ? 'Update answer' : 'Share anonymously';
    if ($('#submitted-answer')) {
      $('#submitted-answer').textContent = `“${data.daily.answer}”`;
      $('#submitted-answer').hidden = !data.daily.answer;
    }
    if ($('#your-answer')) $('#your-answer').textContent = data.daily.answer;
    if ($('#your-answer-card')) $('#your-answer-card').hidden = !data.daily.answer;
    if ($('#daily-responses')) $('#daily-responses').innerHTML = data.daily.responses.map(response => `<section class="card answer-card">
      ${avatar(response.alias, response.color)}<div><strong>${escape(response.alias)}</strong><p>${escape(response.text)}</p><span class="tag">${escape(response.interest)}</span></div>
      ${button(`Connect ${icon('arrow-right')}`, 'connect', `data-response-id="${escape(response.id)}"` , 'secondary')}</section>`).join('') || '<p class="muted">No other responses yet. Share your perspective to get things started.</p>';
    $$('[data-action="similar-answer"]').forEach(el => { el.hidden = provider.capabilities.automaticMatching === false; });
  }
  function renderPoll() {
    if (!data.poll) {
      if ($('#poll-title')) $('#poll-title').textContent = 'No active polls yet.';
      if ($('#poll-options')) $('#poll-options').innerHTML = '';
      if ($('#poll-note')) $('#poll-note').textContent = 'An admin will publish polls here.';
      if ($('#poll-selector')) $('#poll-selector').parentElement.hidden = true;
      if ($('#poll-match')) $('#poll-match').hidden = true;
      return;
    }
    if ($('#poll-selector')) {
      $('#poll-selector').parentElement.hidden = data.polls.length < 2;
      $('#poll-selector').innerHTML = data.polls.map(p => `<option value="${escape(p.id)}" ${p.id === data.poll.id ? 'selected' : ''}>${escape(p.question)}${p.status === 'closed' ? ' (closed)' : ''}</option>`).join('');
    }
    if ($('#poll-title')) $('#poll-title').textContent = data.poll.question;
    if ($('#poll-options')) $('#poll-options').innerHTML = data.poll.choices.map(choice => `<button type="button" class="poll-option" data-action="vote" data-choice="${escape(choice.id)}" data-percent="${choice.percent}" aria-pressed="false"><span class="poll-fill"></span><span class="relative flex items-center gap-3"><span class="radio"></span>${icon(choice.icon, 17)}${escape(choice.text)}</span><strong class="relative text-xs" hidden>${choice.percent}%</strong></button>`).join('');
    $$('[data-action="vote"]').forEach(option => {
      const selected = option.dataset.choice === data.poll.vote;
      option.classList.toggle('selected', selected);
      option.classList.toggle('voted', data.poll.vote !== null);
      option.setAttribute('aria-pressed', selected);
      option.querySelector('.poll-fill').style.width = data.poll.vote === null || data.poll.resultsPublic === false ? '0%' : `${option.dataset.percent}%`;
      option.querySelector('strong').hidden = data.poll.vote === null || data.poll.resultsPublic === false;
      option.querySelector('.radio').innerHTML = selected ? icon('check', 11) : '';
      option.disabled = data.poll.status === 'closed';
    });
    if ($('#poll-note')) $('#poll-note').textContent = data.poll.resultsPublic === false ? (data.poll.vote ? 'Your vote is saved. Results are private.' : 'Results are private. Your choice stays anonymous.') : (data.poll.vote === null ? 'One choice. A little common ground.' : `${data.poll.totalVotes} votes`);
    if ($('#poll-match')) $('#poll-match').hidden = data.poll.vote === null || provider.capabilities.automaticMatching === false;
  }
  function updateCounts() { $$('[data-connection-count]').forEach(el => { el.textContent = data.connections.length; }); }
  function renderChallenge() {
    if (!$('#challenge-title')) return;
    $('#challenge-title').textContent = data.completed ? 'Curiosity, rewarded.' : 'Let curiosity lead.';
    $('#challenge-description').textContent = data.completed ? 'You started a conversation with a new perspective. That’s how connection begins.' : 'Start a conversation with someone whose answer surprised you.';
    $('#challenge-progress').style.width = data.completed ? '100%' : '0%';
    $('#challenge-count').textContent = `${Number(data.completed)} of 1`;
  }
  function renderConnections() {
    const grid = $('#connections-grid');
    if (!grid) return;
    grid.innerHTML = data.connections.map(c => `<section class="card connection-card">
      <div class="flex items-center gap-4">${avatar(c.alias, c.color)}<div><h3>${escape(name(c))}</h3><span class="muted text-xs">Connected through ${escape(c.source.toLowerCase())}</span></div><span class="ml-auto muted">${icon('lock')}</span></div>
      <div class="shared-answer"><span class="section-label">Your common ground</span><p>“${escape(c.shared)}”</p></div>
      <div class="flex gap-2 mb-6">${c.interests.map(t => `<span class="tag">${escape(t)}</span>`).join('')}</div>
      ${button(`Open conversation ${icon('message')}`, 'open-chat', `data-id="${escape(c.id)}"`)}
    </section>`).join('') || '<div class="empty"><h3>A new connection is a question away</h3><p>Share your daily answer or explore the question board.</p><a href="/daily" class="btn primary">Explore responses</a></div>';
  }
  function openChat(id) { ui.activeId = id; persist(); location.assign('/messages'); }
  async function connect(context) {
    const result = await provider.createConnection(context);
    const connection = result.connection;
    data.completed = result.completed;
    ui.notice = `You’re connected with ${connection.alias}. Say a thoughtful hello.`;
    openChat(connection.id);
  }
  function renderConversationList() {
    const list = $('#conversation-list');
    if (!list) return;
    list.innerHTML = data.connections.map(c => `<button type="button" class="message-list-row ${c.id === ui.activeId ? 'active' : ''}" data-action="select-chat" data-id="${escape(c.id)}" ${c.id === ui.activeId ? 'aria-current="true"' : ''}>
      ${avatar(c.alias, c.color)}<span class="conversation-list-copy"><strong>${escape(name(c))}</strong><span>${escape(c.messages.at(-1)?.text || 'Say a thoughtful hello…')}</span></span></button>`).join('') || '<div class="empty"><h3>A fresh start</h3><p>Explore shared answers to find your next conversation.</p></div>';
    updateCounts();
  }
  const starters = ['What got you into that?', 'What’s been the best part of your week?'];
  function renderChat(preserveDraft = false) {
    if (!$('#chat-content')) return;
    const draft = preserveDraft ? ($('[data-form="message"] input')?.value || '') : '';
    const oldInput = $('[data-form="message"] input');
    const focused = preserveDraft && document.activeElement === oldInput;
    const selection = focused ? [oldInput.selectionStart, oldInput.selectionEnd] : null;
    const requestId = preserveDraft ? $('[data-form="message"]')?.dataset.requestId : null;
    const oldMessages = $('.chat-messages');
    const scrollTop = oldMessages?.scrollTop || 0;
    const atBottom = !oldMessages || oldMessages.scrollHeight - oldMessages.scrollTop - oldMessages.clientHeight < 60;
    const c = active();
    $('.app-shell').classList.toggle('has-active-chat', !!c);
    $('.messaging-layout').classList.toggle('chat-selected', !!c);
    renderConversationList();
    if (!c) {
      $('#chat-content').innerHTML = '<div class="empty"><h3>Pick a conversation</h3><p>A thoughtful hello can go a long way.</p><a href="/daily" class="btn primary">Explore responses</a></div>';
      return;
    }
    const visibleStarters = starters.filter(prompt => !(ui.dismissed[c.id] || []).includes(prompt));
    $('#chat-content').innerHTML = `<header class="chat-header">
      <button type="button" class="icon-button mobile-back" data-action="back-messages" aria-label="Back to messages">${icon('arrow-left', 20)}</button>
      ${avatar(c.alias, c.color, true)}<div><h3>${escape(name(c))}</h3><span class="muted text-xs">${c.reveal === 'revealed' ? 'Identity mutually revealed' : 'Anonymous connection'}</span></div><span class="chat-status"><span></span>Here to connect</span>
      </header><div class="chat-context">${icon('lock', 14)}${c.reveal === 'revealed' ? 'You both agreed to share your identities.' : `Connected through ${escape(c.source.toLowerCase())} · ${escape(c.shared)}`}</div>
      <div class="chat-messages" role="log" aria-label="Conversation messages" aria-live="polite">${c.hasOlderMessages ? button('Load earlier messages', 'older-messages', '', 'secondary') : ''}<p class="chat-date">This is the beginning of something good</p>${c.messages.map(m => `<div class="message ${m.from === 'me' ? 'me' : 'them'}"><p>${escape(m.text)}</p><span>${m.from === 'me' ? 'You' : escape(name(c))} · ${escape(displayTime(m.time))}</span></div>`).join('')}</div>
      <div class="chat-bottom">${visibleStarters.length ? `<section class="suggested-starters" aria-label="Suggested conversation starters"><div class="starter-heading"><span>Try a little curiosity</span><button type="button" class="icon-button" data-action="dismiss-all" aria-label="Dismiss suggested prompts">${icon('x', 18)}</button></div><div class="starter-row">${visibleStarters.map(prompt => `<span class="starter-chip"><button type="button" data-action="starter" data-prompt="${escape(prompt)}">${escape(prompt)}</button><button type="button" class="starter-dismiss" data-action="dismiss-starter" data-prompt="${escape(prompt)}" aria-label="Dismiss prompt: ${escape(prompt)}">${icon('x')}</button></span>`).join('')}</div></section>` : '<button type="button" class="suggestion-toggle" data-action="show-starters">Show conversation starters</button>'}
      <form class="message-form" data-form="message"><input name="message" aria-label="Message" placeholder="Write a thoughtful hello…" maxlength="1000" autocomplete="off" required/><button class="btn primary" type="submit" aria-label="Send message" disabled>${icon('send', 18)}</button></form>
      <div class="chat-controls"><button type="button" class="chat-action unlock-action" data-action="unlock">${icon('lock', 14)}${c.reveal === 'revealed' ? 'Identity revealed' : c.reveal === 'waiting' ? 'Waiting for other person' : 'Request identity unlock'}</button>
      <button type="button" class="chat-action" data-action="end">${icon('logout', 14)}End conversation</button><button type="button" class="chat-action" data-action="report">${icon('flag', 14)}Report / block</button></div></div>`;
    if (provider.capabilities.backend) $('.chat-controls').insertAdjacentHTML('beforeend', `<button type="button" class="chat-action" data-action="share-phone">${c.phoneShared ? 'Stop sharing my phone' : 'Share my phone number'}</button>${c.phone ? `<p class="phone-note">${escape(name(c))} shared their phone: ${escape(c.phone)}</p>` : ''}`);
    const messages = $('.chat-messages');
    $('[data-form="message"] input').value = draft;
    $('[data-form="message"] button').disabled = !draft.trim();
    if (requestId) $('[data-form="message"]').dataset.requestId = requestId;
    messages.scrollTop = !preserveDraft || atBottom ? messages.scrollHeight : scrollTop;
    if (focused) { const input = $('[data-form="message"] input'); input.focus({preventScroll:true}); input.setSelectionRange(...selection); }
  }
  let currentGroup, currentQuestion, filter = 'All';
  function renderGroups() {
    if ($('#group-proposals')) $('#group-proposals').innerHTML = (data.groupProposals || []).map(g => `<section class="card proposal-row"><strong>${escape(g.name)}</strong><p class="muted">${escape(g.approval)} · ${escape(g.status)}${g.decisionReason ? ' · ' + escape(g.decisionReason) : ''}</p>${button('Edit and resubmit for approval', 'edit-group', `data-id="${escape(g.id)}"`, 'secondary')}</section>`).join('');
    if (!$('#groups-grid')) return;
    $('#groups-grid').innerHTML = data.groups.map(group => `<button type="button" class="group-tile ${escape(group.color)} detailed" data-action="group" data-id="${escape(group.id)}"><span class="group-icon ${escape(group.color)}">${icon(group.icon, 25)}</span><span class="min-w-0 text-left"><strong>${escape(group.name)}</strong><span class="group-description">${escape(group.description)}</span><span class="group-size">${icon('users', 12)}${group.size} members · ${escape(group.activity)}</span></span><span class="group-arrow">${icon('chevron-right')}</span></button>`).join('') || '<p class="muted">There are no groups to join yet.</p>';
  }
  function showGroup(id) {
    currentGroup = data.groups.find(g => g.id === id);
    const g = currentGroup;
    showModal(g.name, `<p class="muted">${g.size} people · A small space for shared interests</p><div class="group-prompt">${escape(g.question)}</div><div class="group-thread">${g.messages.map(m => `<div class="flex gap-3 my-4">${avatar(m.alias, 'blue', true)}<div><strong class="text-sm">${escape(m.alias)}</strong><p class="text-sm mt-1">${escape(m.text)}</p></div></div>`).join('')}</div>
      ${g.joined ? '<form class="message-form" data-form="group"><input name="message" aria-label="Message to group" placeholder="Add to the conversation…" maxlength="1000" required/><button class="btn primary" type="submit" aria-label="Send group message">' + icon('send', 18) + '</button></form>' : button(`Join the discussion ${icon('arrow-right')}`, 'join-group')}
      <p class="text-xs muted mt-4">Your alias is ${escape(data.profile.alias)}. Keep it kind, curious, and anonymous.</p>`);
  }
  function renderQuestions() {
    if (!$('#question-list')) return;
    $('#question-list').innerHTML = data.questions.filter(q => filter === 'All' || q.category === filter).map(q => `<button type="button" class="card question-row" data-action="question" data-id="${escape(q.id)}"><div class="flex gap-2 items-center text-xs"><span class="tag">${escape(q.category)}</span><span class="muted">${escape(q.alias)} · ${escape(displayTime(q.time))}</span></div><h3>${escape(q.text)}</h3><p>${escape(q.detail)}</p><span class="text-link mt-5">${icon('message', 15)}${q.responses.length} responses ${icon('arrow-right', 15)}</span></button>`).join('') || '<p class="muted">No questions in this category yet.</p>';
    if ($('#question-filters')) $('#question-filters').innerHTML = ['All', ...data.categories].map(category => `<button type="button" data-action="filter" data-category="${escape(category)}">${escape(category)}</button>`).join('');
    $$('[data-action="filter"]').forEach(el => { const selected = el.dataset.category === filter; el.classList.toggle('active', selected); el.setAttribute('aria-pressed', selected); });
  }
  function showQuestion(id) {
    currentQuestion = data.questions.find(q => q.id === id);
    const q = currentQuestion;
    showModal(q.text, `<span class="tag">${escape(q.category)}</span><p class="muted my-4">${escape(q.detail)}</p>${q.responses.map(r => `<div class="board-response"><div class="flex gap-3">${avatar(r.alias, 'blue', true)}<div><strong>${escape(r.alias)}</strong><p>${escape(r.text)}</p></div></div>${!r.isMine ? `<button type="button" class="text-link" data-action="connect" data-question-id="${escape(q.id)}" data-response-id="${escape(r.id)}">Start a private conversation ${icon('arrow-right', 15)}</button>` : ''}</div>`).join('')}
      <form class="form-stack mt-5" data-form="reply"><label>Your anonymous response<textarea name="reply" required maxlength="800" placeholder="Share your perspective…"></textarea></label><button type="submit" class="btn primary">Add response ${icon('send')}</button></form>`);
  }
  function showUnlock() {
    const c = active();
    showModal(c.reveal === 'revealed' ? 'A connection, with a name.' : 'Your identity. Your choice.',
      `<div class="unlock-symbol">${icon('lock', 30)}</div><p class="unlock-explanation">Both people must choose to reveal their identity.</p><p class="muted text-sm text-center">Your name stays hidden until you both agree. You can keep talking anonymously for as long as you like.</p>
      <div class="consent-row"><span>${avatar(data.profile.alias, 'blue', true)}You</span><span>${c.reveal ? '✓ Agreed to reveal' : 'Identity hidden'}</span></div><div class="consent-row"><span>${avatar(c.alias, c.color, true)}${escape(c.alias)}</span><span>${c.peerConsent || c.reveal === 'revealed' ? '✓ Agreed to reveal' : 'Identity hidden'}</span></div>
      ${!c.reveal ? button(`Request Unlock ${icon('arrow-right')}`, 'request-unlock', '', 'primary', 'w-full mt-5') : c.reveal === 'waiting' ? `<div class="waiting-state">Waiting for Other Person</div>${provider.capabilities.simulateIdentityConsent ? `<div class="demo-control"><p>Demo control · Play the other person’s side</p>${button(`Simulate their consent ${icon('check')}`, 'consent', '', 'secondary')}</div>` : ''}<button type="button" class="text-link mx-auto mt-4" data-action="cancel-unlock">Cancel my request</button>` : `<div class="revealed-card">${icon('check', 23)}<strong>Identity Revealed</strong><p>You’re ${escape(data.profile.name)}. Meet ${escape(c.identity)}.</p>${c.identityDetails?.linkedin?.startsWith('https://') ? `<a class="text-link" href="${escape(c.identityDetails.linkedin)}" target="_blank" rel="noopener noreferrer">LinkedIn profile</a>` : ''}<span>Phone numbers are shared separately.</span></div>`}`);
  }
  function groupForm(record) {
    showModal(record ? 'Edit group/thread proposal' : 'Create a group/thread', `<p class="muted">An admin reviews proposals before they appear in the community.</p><form class="form-stack mt-5" data-form="proposal" data-id="${escape(record?.id || '')}"><label>Group name<input name="name" required maxlength="100" value="${escape(record?.name || '')}"/></label><label>Description<textarea name="description" maxlength="800">${escape(record?.description || '')}</textarea></label><button type="submit" class="btn primary">Submit for approval</button></form>`);
  }
  async function removeConnection(method, message, reason) {
    const connectionId = ui.activeId;
    await provider[method]({connectionId, ...(reason ? {reason} : {})});
    data.connections = data.connections.filter(c => c.id !== connectionId);
    ui.activeId = null; persist(); closeModal(); renderChat(); notify(message);
  }
  document.addEventListener('click', event => {
    const el = event.target.closest('[data-action]');
    if (!el || el.disabled) return;
    const d = el.dataset;
    if (d.action === 'retry-load') { loadData(); return; }
    if (!data || pending) return;
    switch (d.action) {
      case 'activity': setActivity(d.activity); break;
      case 'vote': runOperation(async () => { data.poll = await provider.voteOnPoll({pollId: data.poll.id, choiceId: d.choice}); data.polls = replaceRecord(data.polls, data.poll); renderPoll(); }); break;
      case 'poll-match': if (data.poll.vote !== null) runOperation(() => connect({kind: 'poll', pollId: data.poll.id})); break;
      case 'similar-answer': runOperation(() => connect({kind: 'similar-answer', questionId: data.daily.id})); break;
      case 'connect': runOperation(() => connect(d.questionId ? {kind: 'question-response', questionId: d.questionId, responseId: d.responseId} : {kind: 'daily-answer', questionId: data.daily.id, responseId: d.responseId})); break;
      case 'open-chat': openChat(d.id); break;
      case 'select-chat': closeModal(); ui.activeId = d.id; persist(); renderChat(); break;
      case 'back-messages': ui.activeId = null; persist(); renderChat(); break;
      case 'close-modal': closeModal(); break;
      case 'profile': if (provider.capabilities.backend) location.assign('/profile'); else showModal(`Hello, ${data.profile.alias}.`, `<p>${escape(data.profile.name)}</p>`); break;
      case 'propose-group': groupForm(); break;
      case 'edit-group': groupForm(data.groupProposals.find(g => g.id === d.id)); break;
      case 'group': showGroup(d.id); break;
      case 'join-group': runOperation(async () => { const group = await provider.joinGroup({groupId: currentGroup.id}); data.groups = replaceRecord(data.groups, group); renderGroups(); showGroup(group.id); }); break;
      case 'filter': filter = d.category; renderQuestions(); break;
      case 'question': showQuestion(d.id); break;
      case 'post-question': showModal('What’s on your mind?', `<p class="muted mb-6">Your question will appear under your anonymous alias.</p><form class="form-stack" data-form="question"><label>Category<select name="category">${data.categories.map(c => `<option>${escape(c)}</option>`).join('')}</select></label><label>Your question<input name="title" required maxlength="180" placeholder="Something you’ve been wondering…"/></label><label>A little context<textarea name="detail" maxlength="800" placeholder="Tell the community a little more (optional)"></textarea></label><button type="submit" class="btn primary">Post anonymously ${icon('send')}</button></form>`); break;
      case 'starter': $('[data-form="message"] input').value = d.prompt; $('[data-form="message"] button').disabled = false; $('[data-form="message"] input').focus(); break;
      case 'dismiss-starter': ui.dismissed[ui.activeId] = [...(ui.dismissed[ui.activeId] || []), d.prompt]; persist(); renderChat(true); break;
      case 'dismiss-all': ui.dismissed[ui.activeId] = [...starters]; persist(); renderChat(true); break;
      case 'show-starters': ui.dismissed[ui.activeId] = []; persist(); renderChat(true); break;
      case 'unlock': showUnlock(); break;
      case 'share-phone': showModal('Share your phone number?', `<p class="muted my-4">${active().phoneShared ? 'Stop sharing your phone number in this conversation.' : `Share your phone number only with ${escape(name(active()))}. They can save it once you share it.`}</p>${button(active().phoneShared ? 'Stop sharing' : 'Share my number', 'confirm-phone')}`); break;
      case 'confirm-phone': runOperation(async () => { const c = await provider.sharePhone({connectionId:ui.activeId,share:!active().phoneShared}); data.connections = replaceRecord(data.connections,c); closeModal(); renderChat(true); }); break;
      case 'older-messages': runOperation(async () => { const c = active(); const older = await provider.loadOlderMessages({connectionId:c.id,before:c.messages[0].id}); c.messages = [...older,...c.messages]; c.hasOlderMessages = older.length === 100; renderChat(true); }); break;
      case 'request-unlock': runOperation(async () => { const connection = await provider.requestIdentityReveal({connectionId: ui.activeId}); data.connections = replaceRecord(data.connections, connection); renderChat(true); showUnlock(); }); break;
      case 'consent': if (provider.capabilities.simulateIdentityConsent) runOperation(async () => { const connection = await provider.simulateIdentityConsent({connectionId: ui.activeId}); data.connections = replaceRecord(data.connections, connection); renderChat(true); showUnlock(); }); break;
      case 'cancel-unlock': runOperation(async () => { const connection = await provider.cancelIdentityReveal({connectionId: ui.activeId}); data.connections = replaceRecord(data.connections, connection); renderChat(true); showUnlock(); }); break;
      case 'end': showModal('End this conversation?', `<p class="muted my-5">This will remove your conversation with ${escape(active().alias)}. You can always discover another connection.</p><div class="flex gap-3">${button('Keep talking', 'close-modal', '', 'secondary')}${button('End conversation', 'confirm-end')}</div>`); break;
      case 'confirm-end': runOperation(() => removeConnection('endConversation', 'Conversation ended')); break;
      case 'report': showModal('Let’s keep this space kind.', `<p class="muted my-4">Blocking removes this conversation.</p><label class="form-stack">Reason<select id="report-reason"><option>Unkind or inappropriate messages</option><option>Spam or unwanted contact</option><option>Sharing personal information</option><option>Something else</option></select></label><div class="flex flex-wrap gap-3 mt-6">${button('Report & block', 'confirm-report')}${button('Block only', 'block', '', 'secondary')}</div>`); break;
      case 'confirm-report': { const reason = $('#report-reason').value; runOperation(() => removeConnection('reportConnection', 'Report recorded and connection blocked', reason)); break; }
      case 'block': runOperation(() => removeConnection('blockConnection', 'Connection blocked')); break;
    }
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!form.dataset.form) return;
    event.preventDefault();
    if (!data || pending) return;
    const fields = new FormData(form);
    const value = key => String(fields.get(key) || '').trim();
    switch (form.dataset.form) {
      case 'daily':
        if (!value('answer')) return;
        runOperation(async () => { data.daily = await provider.saveDailyAnswer({questionId: data.daily.id, text: value('answer')}); data.dailyQuestions = replaceRecord(data.dailyQuestions,data.daily); answerDrafts.delete(data.daily.id); renderAnswer(); notify('Your answer has been shared anonymously.'); }); break;
      case 'message':
        if (!value('message') || !active()) return;
        form.dataset.requestId ||= newRequestId();
        runOperation(async () => { const connection = await provider.sendMessage({connectionId: ui.activeId, text: value('message'),requestId:form.dataset.requestId}); data.connections = replaceRecord(data.connections, connection); renderChat(); $('[data-form="message"] input').focus(); }); break;
      case 'group':
        if (!value('message') || !currentGroup.joined) return;
        form.dataset.requestId ||= newRequestId();
        runOperation(async () => { const group = await provider.sendGroupMessage({groupId: currentGroup.id, text: value('message'),requestId:form.dataset.requestId}); data.groups = replaceRecord(data.groups, group); showGroup(group.id); $('[data-form="group"] input').focus(); }); break;
      case 'proposal':
        runOperation(async () => { const proposal = await provider[form.dataset.id ? 'editGroupProposal' : 'proposeGroup']({name:value('name'),description:value('description'),...(form.dataset.id ? {groupId:form.dataset.id} : {})}); data.groupProposals = [proposal,...data.groupProposals.filter(g => g.id !== proposal.id)]; data.groups = data.groups.filter(g => g.id !== proposal.id); renderGroups(); closeModal(); notify('Your group proposal is waiting for admin approval.'); }); break;
      case 'question':
        if (!value('title')) return;
        runOperation(async () => { const question = await provider.postQuestion({category: value('category'), text: value('title'), detail: value('detail')}); data.questions = [question, ...data.questions]; filter = 'All'; renderQuestions(); closeModal(); notify('Your question is on the board.'); }); break;
      case 'reply':
        if (!value('reply')) return;
        runOperation(async () => { const question = await provider.replyToQuestion({questionId: currentQuestion.id, text: value('reply')}); data.questions = replaceRecord(data.questions, question); renderQuestions(); showQuestion(question.id); $('[data-form="reply"] textarea').focus(); }); break;
    }
  });
  document.addEventListener('input', event => {
    if (event.target.matches('[data-form="message"] input')) $('[data-form="message"] button').disabled = !event.target.value.trim();
    if (event.target.closest('[data-form="message"], [data-form="group"]')) delete event.target.closest('form').dataset.requestId;
    if (event.target.id === 'daily-response' && data?.daily) answerDrafts.set(data.daily.id,event.target.value);
  });
  document.addEventListener('change', event => {
    if (event.target.id === 'community') { ui.community = event.target.value; persist(); }
    if (event.target.id === 'daily-selector') { ui.dailyId = event.target.value; selectActivities(); renderAnswer(); persist(); revision++; }
    if (event.target.id === 'poll-selector') { ui.pollId = event.target.value; selectActivities(); renderPoll(); persist(); revision++; }
  });
  document.addEventListener('keydown', event => {
    if (!event.target.matches('[data-action="activity"]')) return;
    const tabs = $$('[data-action="activity"]');
    const current = tabs.indexOf(event.target);
    const next = event.key === 'ArrowRight' ? (current + 1) % tabs.length : event.key === 'ArrowLeft' ? (current + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
    if (next !== null) { event.preventDefault(); setActivity(tabs[next].dataset.activity, true); }
  });
  $('#demo-modal')?.addEventListener('click', event => {
    if (event.target !== $('#demo-modal')) return;
    const rect = event.target.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeModal();
  });
  $('#demo-modal')?.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
  async function loadData() {
    if (pending) return;
    pending = true;
    const controls = $$('button, form input, form textarea, form select').map(control => [control, control.disabled]);
    controls.forEach(([control]) => { control.disabled = true; });
    $('[data-page]')?.setAttribute('aria-busy', 'true');
    document.documentElement.dataset.demoReady = 'false';
    if ($('#data-status')) { $('#data-status').hidden = false; $('#data-status-message').textContent = 'Loading…'; $('#retry-load').hidden = true; }
    try {
      provider ||= await createProvider();
      data = await provider.load();
      if (ui.viewerId !== data.profile.id) {
        ui.activeId = undefined; ui.dismissed = {}; ui.dailyId = undefined; ui.pollId = undefined; ui.notice = ''; answerDrafts.clear();
      }
      ui.viewerId = data.profile.id;
      selectActivities();
      if (ui.activeId === undefined || (ui.activeId !== null && !active())) ui.activeId = data.connections[0]?.id || null;
      renderAnswer(); renderPoll(); renderConnections(); renderQuestions(); renderGroups(); renderChat(); updateCounts();
      if ($('.profile-button')) $('.profile-button').innerHTML = avatar(data.profile.alias, 'blue', true);
      if (data.profile.role === 'admin' && $('.sidebar') && !$('.admin-link')) $('.sidebar').insertAdjacentHTML('beforeend','<a href="/admin" class="nav-item admin-link">Manage community</a>');
      if ($('#community')) $('#community').value = ui.community;
      if ($('#activity-daily')) setActivity(ui.activity);
      if ($('#challenge-title')) {
        $('#challenge-title').textContent = data.completed ? 'Curiosity, rewarded.' : 'Let curiosity lead.';
        $('#challenge-description').textContent = data.completed ? 'You started a conversation with a new perspective. That’s how connection begins.' : 'Start a conversation with someone whose answer surprised you.';
        $('#challenge-progress').style.width = data.completed ? '100%' : '0%'; $('#challenge-count').textContent = `${Number(data.completed)} of 1`;
      }
      if (ui.notice) { const notice = ui.notice; ui.notice = ''; notify(notice); }
      persist();
      if ($('#data-status')) $('#data-status').hidden = true;
      document.documentElement.dataset.demoReady = 'true';
    } catch (error) {
      data = null;
      if ($('#data-status')) { $('#data-status').hidden = false; $('#data-status-message').textContent = error.userMessage || 'Unable to load the page. Please try again.'; $('#retry-load').hidden = false; }
    } finally {
      pending = false;
      controls.forEach(([control, disabled]) => { if (control.isConnected) control.disabled = disabled; });
      $('[data-page]')?.setAttribute('aria-busy', 'false');
    }
  }
  function selectActivities() {
    data.dailyQuestions ||= data.daily ? [data.daily] : [];
    data.polls ||= data.poll ? [data.poll] : [];
    data.daily = data.dailyQuestions.find(q => q.id === ui.dailyId) || data.dailyQuestions[0] || null;
    data.poll = data.polls.find(p => p.id === ui.pollId) || data.polls[0] || null;
    ui.dailyId = data.daily?.id; ui.pollId = data.poll?.id;
  }
  function refreshModal(render) {
    const requestId = $('#modal-body form')?.dataset.requestId;
    const modalScroll = $('#demo-modal').scrollTop;
    const values = [...$('#modal-body').querySelectorAll('input,textarea,select')].map(el => [el.name,el.value]);
    const focused = document.activeElement;
    const selection = focused?.matches('input,textarea') ? [focused.selectionStart,focused.selectionEnd] : null;
    const focusName = focused?.name;
    const focusAction = focused?.dataset.action;
    render();
    for (const [name,value] of values) { const el = $('#modal-body').querySelector(`[name="${name}"]`); if (el) el.value = value; }
    if (requestId && $('#modal-body form')) $('#modal-body form').dataset.requestId = requestId;
    $('#demo-modal').scrollTop = modalScroll;
    const next = focusName && $('#modal-body').querySelector(`[name="${focusName}"]`);
    if (next) { next.focus({preventScroll:true}); if (selection && next.setSelectionRange) next.setSelectionRange(...selection); }
    else if (focusAction) $('#modal-body').querySelector(`[data-action="${focusAction}"]`)?.focus({preventScroll:true});
  }
  async function refresh() {
    if (!data || pending || refreshing || document.hidden || !provider.capabilities.backend) return;
    refreshing = true;
    const before = revision;
    try {
      const cursors = Object.fromEntries(data.connections.slice(0,100).filter(c => c.messages.length).map(c => [c.id,c.messages.at(-1).id]));
      const next = await provider.load({afterMessages:cursors});
      if (before !== revision || pending) return;
      if (next.profile.id !== data.profile.id) { location.reload(); return; }
      const previous = data;
      // Keep explicitly loaded older history while refreshing the current tail.
      for (const connection of next.connections) {
        const old = previous.connections.find(c => c.id === connection.id);
        if (old && connection.incremental) {
          const existing = new Set(old.messages.map(m => m.id));
          connection.messages = [...old.messages,...connection.messages.filter(m => !existing.has(m.id))];
          connection.hasOlderMessages = old.hasOlderMessages;
        } else if (old?.messages.length > 100 && connection.messages.length) {
          connection.messages = [...old.messages.filter(m => Number(m.id) < Number(connection.messages[0].id)), ...connection.messages];
          connection.hasOlderMessages = old.hasOlderMessages;
        }
        connection.incremental = false;
      }
      data = next; selectActivities();
      if (JSON.stringify(previous.daily) !== JSON.stringify(data.daily)) renderAnswer();
      if (JSON.stringify(previous.poll) !== JSON.stringify(data.poll)) renderPoll();
      if (JSON.stringify(previous.connections) !== JSON.stringify(data.connections)) { renderConnections(); renderChat(true); updateCounts(); }
      if (JSON.stringify(previous.groups) !== JSON.stringify(data.groups) || JSON.stringify(previous.groupProposals) !== JSON.stringify(data.groupProposals)) renderGroups();
      if (JSON.stringify(previous.questions) !== JSON.stringify(data.questions)) renderQuestions();
      if (previous.completed !== data.completed) renderChallenge();
      if ($('#demo-modal').open) {
        if ($('.unlock-explanation') && active()) {
          const old = previous.connections.find(c => c.id === ui.activeId);
          if (!old || old.myConsent !== active().myConsent || old.peerConsent !== active().peerConsent || old.identity !== active().identity) refreshModal(showUnlock);
        }
        else if ($('[data-form="group"]') && currentGroup) {
          const group = data.groups.find(g => g.id === currentGroup.id);
          if (!group) { closeModal(); notify('This group is no longer open.'); }
          else if (JSON.stringify(group) !== JSON.stringify(currentGroup)) refreshModal(() => showGroup(group.id));
        } else if ($('[data-form="reply"]') && currentQuestion) {
          const question = data.questions.find(q => q.id === currentQuestion.id);
          if (question && JSON.stringify(question) !== JSON.stringify(currentQuestion)) refreshModal(() => showQuestion(question.id));
        }
        if (!active() && $('.unlock-explanation, [data-action="confirm-phone"], [data-action="confirm-end"], [data-action="confirm-report"]')) closeModal();
      }
      if ($('#data-status')) $('#data-status').hidden = true;
    } catch (error) {
      if ($('#data-status')) { $('#data-status').hidden = false; $('#data-status-message').textContent = error.userMessage || 'Unable to refresh. Retrying…'; }
    } finally { refreshing = false; }
  }
  await loadData();
  const timer = setInterval(refresh,2000);
  addEventListener('pagehide',() => clearInterval(timer),{once:true});
})().catch(() => {
  const status = document.getElementById('data-status');
  if (status) { status.hidden = false; document.getElementById('data-status-message').textContent = 'Unable to load the page. Please refresh and try again.'; }
});
