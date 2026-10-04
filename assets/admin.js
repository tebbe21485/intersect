(async () => {
  const {request, session} = await import('/services/http.mjs');
  const host = document.getElementById('admin-content'), status = document.getElementById('admin-status');
  if (!host || host.dataset.ready) return;
  host.dataset.ready = 'true';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data, pending = false;
  let selected = 'questions';
  const navigation = document.getElementById('admin-navigation');
  const sections = [
    ['questions', 'Daily questions', 'Publish and edit questions'],
    ['polls', 'Polls', 'Manage choices and results'],
    ['proposals', 'Group proposals', 'Review community suggestions'],
    ['groups', 'Groups', 'Create and manage groups'],
    ['reports', 'Reports', 'Review community reports'],
  ];
  function selectSection(key) {
    selected = key;
    host.querySelectorAll('[data-admin-section]').forEach(section => { section.hidden = section.dataset.adminSection !== key; });
    navigation.querySelectorAll('button').forEach(button => {
      const active = button.dataset.adminSelect === key;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'true');
      else button.removeAttribute('aria-current');
    });
  }
  navigation.addEventListener('click', event => {
    const button = event.target.closest('[data-admin-select]');
    if (button && !pending) selectSection(button.dataset.adminSelect);
  });
  const options = (values, selected) => values.map(v => `<option ${v === selected ? 'selected' : ''}>${v}</option>`).join('');
  const activity = (record, poll = false) => `<form class="form-stack admin-editor" data-method="${poll ? 'savePoll' : 'saveQuestion'}" data-id="${escape(record?.id || '')}"><label>${poll ? 'Poll' : 'Question'}<textarea name="text" required maxlength="500">${escape(record?.question || record?.text || '')}</textarea></label>${poll ? `<label>Choices (one per line)<textarea name="choices" required>${escape(record?.choices.map(c => c.text).join('\n') || '')}</textarea></label><label>Results<select name="resultsPublic"><option value="true" ${record?.resultsPublic !== false ? 'selected' : ''}>Public percentages</option><option value="false" ${record?.resultsPublic === false ? 'selected' : ''}>Private responses</option></select></label>${record ? `<p class="muted text-sm">${record.totalVotes} votes · ${record.choices.map(c => `${escape(c.text)}: ${c.count}`).join(' · ')}</p>` : ''}` : ''}<label>Status<select name="status">${options(['draft','published','closed','archived'], record?.status || 'draft')}</select></label><button class="btn primary" type="submit">${record ? 'Save changes' : 'Create ' + (poll ? 'poll' : 'question')}</button></form>`;
  const group = record => `<form class="form-stack admin-editor" data-method="saveGroup" data-id="${escape(record?.id || '')}"><label>Group name<input name="name" maxlength="100" required value="${escape(record?.name || '')}"/></label><label>Description<textarea name="description" maxlength="800">${escape(record?.description || '')}</textarea></label><label>Status<select name="status">${options(['open','closed','archived'], record?.status || 'open')}</select></label><button type="submit" class="btn primary">${record ? 'Save group' : 'Create approved group'}</button></form>`;
  function render() {
    host.hidden = false;
    host.innerHTML = `<section class="card admin-section" id="admin-section-questions" data-admin-section="questions"><h2>Daily questions</h2>${activity()}${data.dailyQuestions.map(q => activity(q)).join('')}</section><section class="card admin-section" id="admin-section-polls" data-admin-section="polls"><h2>Polls</h2><p class="muted">Choices cannot change once votes are recorded.</p>${activity(null,true)}${data.polls.map(p => activity(p,true)).join('')}</section><section class="card admin-section" id="admin-section-proposals" data-admin-section="proposals"><h2>Group proposals</h2>${data.groups.filter(g => g.approval === 'pending').map(g => `<form class="form-stack admin-editor" data-method="reviewGroup" data-id="${escape(g.id)}"><h3>${escape(g.name)}</h3><p>${escape(g.description)}</p><label>Decision<select name="decision">${options(['approved','rejected'],'approved')}</select></label><label>Reason (optional)<input name="reason" maxlength="500"/></label><button class="btn primary" type="submit">Review proposal</button></form>`).join('') || '<p class="muted">No pending proposals.</p>'}</section><section class="card admin-section" id="admin-section-groups" data-admin-section="groups"><h2>Groups</h2>${group()}${data.groups.filter(g => g.approval === 'approved').map(group).join('')}</section><section class="card admin-section" id="admin-section-reports" data-admin-section="reports"><h2>Reports</h2>${data.reports.map(r => `<div class="admin-editor"><p><strong>${escape(r.reporter)}</strong> reported ${escape(r.reported)}</p><p>${escape(r.reason)}</p><details><summary>Conversation history</summary>${r.messages.map(m => `<p><strong>${escape(m.alias)}</strong>: ${escape(m.text)} <span class="muted">${escape(m.time)}</span></p>`).join('')}</details><p class="muted">${escape(r.time)} · ${escape(r.status)}</p>${r.status === 'open' ? `<form data-method="reviewReport" data-id="${escape(r.id)}"><button type="submit" class="btn secondary">Mark reviewed</button></form>` : ''}</div>`).join('') || '<p class="muted">No reports.</p>'}</section>`;
    navigation.hidden = false;
    if (!navigation.childElementCount) {
      navigation.innerHTML = sections.map(([key,label,description]) => `<button type="button" class="message-list-row" data-admin-select="${key}" aria-controls="admin-section-${key}"><span class="conversation-list-copy"><strong>${label}</strong><span>${description}</span></span></button>`).join('');
    }
    selectSection(selected);

  }
  host.addEventListener('submit', async event => {
    event.preventDefault(); if (pending) return;
    const form = event.target, input = Object.fromEntries(new FormData(form));
    if (form.dataset.id) input.id = form.dataset.id;
    if (input.choices !== undefined) { input.choices = input.choices.split('\n').map(c => c.trim()).filter(Boolean); input.resultsPublic = input.resultsPublic === 'true'; }
    pending = true; status.textContent = 'Saving…';
    const controls = [...host.querySelectorAll('button,input,select,textarea'), ...navigation.querySelectorAll('button')]; controls.forEach(el => { el.disabled = true; });
    try { data = await request('admin/action', {method:form.dataset.method, input}); render(); status.textContent = 'Changes saved.'; }
    catch (error) { status.textContent = error.userMessage; }
    finally { pending = false; controls.forEach(el => { el.disabled = false; }); }
  });
  try { await session(); data = await request('admin'); render(); status.textContent = ''; }
  catch (error) { status.textContent = error.userMessage || 'Unable to load administrator tools.'; }
})();
