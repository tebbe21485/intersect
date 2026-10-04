/* Matching forms preserve drafts on failure; all scoring happens in Python. */
(async () => {
  const root = document.querySelector('[data-page="matching"]');
  if (!root || root.dataset.matchingReady) return;
  root.dataset.matchingReady = 'true';
  const {createBackendProvider} = await import('/services/backend-provider.mjs');
  const {loadUiState, saveUiState} = await import('/services/ui-state.mjs');
  const {getUserPuzzle, syncSavedPuzzle} = await import('/services/puzzle-store.mjs');
  const $ = selector => root.querySelector(selector);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label = value => String(value).replaceAll('_',' ').replaceAll('-',' ');
  const feedback = message => { $('#matching-status').textContent = message; };
  const tabs = [...root.querySelectorAll('[data-matching-tab]')];
  function selectTab(index, focus = false) {
    tabs.forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(index === i));
      tab.tabIndex = index === i ? 0 : -1;
      $(`#matching-panel-${tab.dataset.matchingTab}`).hidden = index !== i;
    });
    if (focus) tabs[index].focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(index));
    tab.addEventListener('keydown', event => {
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
      if (next !== null) { event.preventDefault(); selectTab(next, true); }
    });
  });
  let provider, profile, activity, pending = false, initialized = false;
  function updatePieceControls() {
    if (!profile) return;
    const count = profile.puzzlePieces.length;
    const complete = count >= 4 && count <= 8;
    const setDisabled = (selector, value) => {
      const control = $(selector);
      if (control.disabled !== value) control.disabled = value;
    };
    setDisabled('#puzzle-editor button[type=submit]', pending || (count >= 8 && !$('#puzzle-editor [name=id]').value));
    setDisabled('#matching-search button[type=submit]', pending || !complete);
    setDisabled('#puzzle-continue', pending || !complete);
  }
  // Reflex hydration can restore the initial disabled submit props after the
  // API has loaded. Keep these controls consistent with this script's state.
  const submitObserver = new MutationObserver(() => {
    if (!initialized || pending) return;
    const personalSubmit = $('#personal-editor button[type=submit]');
    if (personalSubmit.disabled) personalSubmit.disabled = false;
    updatePieceControls();
  });
  submitObserver.observe(root, {subtree:true, attributes:true, attributeFilter:['disabled']});
  const controls = () => [...root.querySelectorAll('.matching-card button, .matching-card input, .matching-card textarea, .matching-card select')];
  const modes = () => {
    const selected = $('#matching-mode').value === 'trait';
    $('#matching-trait-label').hidden = !selected;
    $('#matching-trait').disabled = !selected || pending;
    $('#matching-trait').required = selected;
  };
  async function run(operation) {
    if (pending || !initialized) return;
    pending = true;
    const previous = controls().map(control => [control, control.disabled]);
    previous.forEach(([control]) => { control.disabled = true; });
    feedback('Working…');
    try { await operation(); }
    catch (error) { feedback(error.userMessage || 'Please try again.'); }
    finally {
      pending = false;
      previous.forEach(([control, disabled]) => { if (control.isConnected) control.disabled = disabled; });
      modes();
      updatePieceControls();
    }
  }
  function renderPieces() {
    const count = profile.puzzlePieces.length;
    $('#puzzle-piece-count').textContent = `${count}/8 pieces · Required: minimum 4, maximum 8.${count < 4 ? ` Add ${4 - count} more to complete your puzzle.` : count > 8 ? ' Remove extra pieces to complete your puzzle.' : ' Your puzzle is ready.'}`;
    $('#matching-pieces').innerHTML = count ? profile.puzzlePieces.map(piece => `<article class="matching-piece"><strong>${escape(piece.title)}</strong><span class="muted text-sm">${escape(label(piece.category))}</span><div class="matching-piece-actions"><button type="button" class="btn secondary" data-piece-edit="${escape(piece.id)}">Edit</button><button type="button" class="text-link" data-piece-delete="${escape(piece.id)}">Remove</button></div></article>`).join('') : '<p class="muted">Add your first piece below.</p>';
    window.intersectPuzzleOwnerId = activity.profile.id;
    syncSavedPuzzle(activity.profile, profile.puzzlePieces);
    updatePieceControls();
  }
  function renderPersonal() {
    $('#personal-fields').innerHTML = Object.entries(profile.personalFields).map(([field, definition]) => {
      const answer = profile.personalAnswers[field];
      if (definition.kind === 'multi') return `<fieldset class="matching-choices" data-personal="${escape(field)}"><legend>${escape(label(field))}</legend>${definition.options.map(option => `<label><input type="checkbox" value="${escape(option)}" ${answer?.includes(option) ? 'checked' : ''}>${escape(label(option))}</label>`).join('')}</fieldset>`;
      return `<label>${escape(label(field))}<select data-personal="${escape(field)}"><option value="">Prefer not to answer</option>${definition.options.map(option => `<option value="${escape(option)}" ${answer === option ? 'selected' : ''}>${escape(label(option))}</option>`).join('')}</select></label>`;
    }).join('');
  }
  function renderTraits() {
    const before = $('#matching-trait').value;
    const traits = profile.puzzlePieces.map(piece => [{category:'puzzle',value:piece.id}, `Puzzle: ${piece.title}`]);
    for (const [field, answer] of Object.entries(profile.personalAnswers)) {
      for (const value of (Array.isArray(answer) ? answer : [answer])) traits.push([{category:'personal',field,value}, `${label(field)}: ${label(value)}`]);
    }
    for (const group of activity.groups.filter(group => group.joined)) traits.push([{category:'groups',value:group.id}, `Group: ${group.name}`]);
    for (const question of activity.dailyQuestions.filter(question => question.answer)) traits.push([{category:'daily_questions',value:question.id}, `Question: ${question.text.slice(0,70)}`]);
    for (const poll of activity.polls.filter(poll => poll.vote)) traits.push([{category:'polls',value:poll.id}, `Poll: ${poll.question.slice(0,70)}`]);
    $('#matching-trait').innerHTML = '<option value="">Select a saved trait</option>' + traits.map(([value, text]) => `<option value="${escape(JSON.stringify(value))}">${escape(text)}</option>`).join('');
    if ([...$('#matching-trait').options].some(option => option.value === before)) $('#matching-trait').value = before;
    modes();
  }
  function clearPieceEditor() {
    $('#puzzle-editor').reset();
    $('#puzzle-editor [name=id]').value = '';
    $('#cancel-piece-edit').hidden = true;
    updatePieceControls();
  }
  function clearResults() { $('#matching-results').replaceChildren(); }
  $('#cancel-piece-edit').addEventListener('click', clearPieceEditor);
  $('#puzzle-continue').addEventListener('click', () => {
    if (profile.puzzlePieces.length >= 4 && profile.puzzlePieces.length <= 8) selectTab(2, true);
  });
  root.addEventListener('click', event => {
    const edit = event.target.closest('[data-piece-edit]');
    const remove = event.target.closest('[data-piece-delete]');
    if (pending || !initialized) return;
    if (edit) {
      const piece = profile.puzzlePieces.find(piece => piece.id === edit.dataset.pieceEdit);
      for (const key of ['id','category','title','description']) $('#puzzle-editor').elements.namedItem(key).value = piece[key];
      $('#cancel-piece-edit').hidden = false;
      $('#puzzle-editor [name=title]').focus();
      updatePieceControls();
    }
    if (remove) run(async () => {
      await provider.deletePuzzlePiece({id:remove.dataset.pieceDelete});
      profile = await provider.matchingProfile(); renderPieces(); renderTraits(); clearResults();
      if ($('#puzzle-editor [name=id]').value === remove.dataset.pieceDelete) clearPieceEditor();
      feedback('Piece removed.');
    });
  });
  $('#puzzle-editor').addEventListener('submit', event => {
    event.preventDefault();
    const input = Object.fromEntries(new FormData(event.currentTarget));
    if (!input.id) delete input.id;
    if (!input.id && profile.puzzlePieces.length >= 8) { feedback('Your puzzle can have at most 8 pieces. Edit an existing piece.'); return; }
    if (!input.title.trim() || !input.description.trim()) { feedback('Enter a title and description.'); return; }
    run(async () => {
      await provider.savePuzzlePiece(input);
      profile = await provider.matchingProfile(); clearPieceEditor(); renderPieces(); renderTraits(); clearResults(); feedback('Puzzle piece saved.');
    });
  });
  $('#personal-editor').addEventListener('submit', event => {
    event.preventDefault();
    const answers = Object.fromEntries([...root.querySelectorAll('[data-personal]')].map(control => [control.dataset.personal, control.tagName === 'SELECT' ? (control.value || null) : [...control.querySelectorAll('input:checked')].map(input => input.value)]));
    run(async () => { profile = await provider.savePersonalAnswers({answers}); renderTraits(); clearResults(); feedback('Personal answers saved.'); });
  });
  $('#matching-mode').addEventListener('change', () => { modes(); clearResults(); });
  $('#matching-trait').addEventListener('change', clearResults);
  $('#matching-search').addEventListener('submit', event => {
    event.preventDefault();
    if (profile.puzzlePieces.length < 4 || profile.puzzlePieces.length > 8) { feedback('Create 4–8 puzzle pieces before finding connections.'); return; }
    const mode = $('#matching-mode').value;
    const trait = mode === 'trait' ? JSON.parse($('#matching-trait').value || 'null') : null;
    run(async () => {
      const result = await provider.findMatches({mode,...(trait ? {trait} : {})});
      feedback(result.matches.length ? `${result.matches.length} connection${result.matches.length === 1 ? '' : 's'} found.` : 'No connections meet this mode yet. Add more answers or try another mode.');
      $('#matching-results').innerHTML = result.matches.map(match => `<article class="match-result"><h3>${escape(match.alias)}</h3><strong>Similarity score: ${Math.round(match.overall_similarity * 100)}%</strong><p>${escape(match.match_reason)}</p><details><summary>How this score was calculated</summary><dl>${Object.entries(match.category_scores).map(([category, score]) => `<dt>${escape(label(category))}</dt><dd>${score === null ? 'No comparable data' : `${Math.round(score * 100)}%`}</dd>`).join('')}</dl><p class="muted">${match.comparable_counts.daily_questions} shared questions, ${match.comparable_counts.polls} shared polls. Missing sections are left out.</p><p class="muted">Strong puzzle areas: ${escape([...new Set(match.puzzle_details.strongest.map(piece => label(piece.category_a)))].join(', ') || 'None yet')}. Different puzzle areas: ${escape([...new Set(match.puzzle_details.weakest.map(piece => label(piece.category_a)))].join(', ') || 'None compared')}.</p></details><button type="button" class="btn primary" data-match-user="${match.user_id}">Start conversation</button></article>`).join('');
      for (const button of root.querySelectorAll('[data-match-user]')) button.addEventListener('click', () => run(async () => {
        const result = await provider.createConnection({kind:'match',mode,userId:button.dataset.matchUser,...(trait ? {trait} : {})});
        const ui = loadUiState(); ui.activeId = result.connection.id; saveUiState(ui); location.assign('/messages');
      }));
    });
  });
  try {
    provider = await createBackendProvider();
    [profile, activity] = await Promise.all([provider.matchingProfile(), provider.load()]);
    // Preserve pieces created by the earlier signup form when opening this builder.
    const local = getUserPuzzle(activity.profile.id);
    if (local?.pieces.length && local.pieces.every(piece => piece.id.startsWith(`${activity.profile.id}-piece-`))) {
      for (const piece of local.pieces) {
        if (!profile.puzzlePieces.some(saved => saved.title === piece.shortLabel && saved.description === piece.description)) {
          await provider.savePuzzlePiece({category: 'interests', title: piece.shortLabel, description: piece.description});
        }
      }
      profile = await provider.matchingProfile();
    }
    $('#puzzle-category').innerHTML = profile.puzzleCategories.map(category => `<option value="${escape(category)}">${escape(label(category))}</option>`).join('');
    renderPieces(); renderPersonal(); renderTraits(); initialized = true;
    controls().forEach(control => { control.disabled = false; }); modes(); feedback('');
    updatePieceControls();
  } catch (error) { feedback(error.userMessage || 'Unable to load matching. Refresh and try again.'); }
})();
