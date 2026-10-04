function ConnectionFloor({progress}) {
  const floor = puzzleModules.CONNECTION_FLOORS[progress.currentFloor - 1];
  return <div className="puzzle-heading">
    <p className="section-label">Floor {progress.currentFloor} of 4</p>
    <h2 className="puzzle-title">{floor.name}</h2>
    <p className="puzzle-note text-sm">{floor.goal}</p>
  </div>;
}

function FloorProgress({progress, userId, peer}) {
  const otherId = progress.participantIds.find(id => id !== userId);
  return <div className="floor-progress" aria-label="Floor message progress">
    <p>You: {progress.counts[userId]}/2 messages</p>
    <p>{peer}: {progress.counts[otherId]}/2 messages</p>
    <p className="puzzle-note text-xs">{progress.currentFloor === 4
      ? 'Stay and share at your own pace.'
      : 'Two messages each make progression available. You both choose when to advance.'}</p>
  </div>;
}

function AdvanceFloor({progress, connectionId, userId, onReady}) {
  if (!progress.canAdvance) return progress.currentFloor === 4
    ? <p className="puzzle-note text-sm">You can keep talking and sharing on Trust for as long as you like.</p> : null;
  const ready = Boolean(progress.ready[userId]);
  return <section className="floor-advance" aria-label="Advance floor">
    <h3>Ready for the Next Floor?</h3>
    <p className="puzzle-note text-sm">{ready ? 'Waiting for your connection to agree. You can stay here.' : 'Advance only when you both feel ready.'}</p>
    <button type="button" className="btn primary w-full"
      onClick={() => onReady(!ready)}>
      {ready ? 'Cancel readiness' : 'I’m ready for the next floor'}
    </button>
  </section>;
}

function SensitivePromptOptIn({progress, connectionId, userId, onChange}) {
  return <section className="sensitive-opt-in">
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={Boolean(progress.sensitive[userId])}
        onChange={event => onChange(event.target.checked)} />
      Allow sensitive prompts
    </label>
    <p className="puzzle-note text-xs">{progress.allowSensitivePrompts
      ? 'Both of you opted in. Sensitive prompts may appear on Trust.'
      : 'Sensitive prompts stay hidden unless both of you opt in.'}</p>
  </section>;
}

function InteractionCard({activity, onUse}) {
  return <article className="interaction-card">
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="tag">{activity.type.replaceAll('-', ' ')}</span>
      <span className="puzzle-note">{activity.direction}</span>
    </div>
    {activity.type === 'image' ? <svg viewBox="0 0 200 80" role="img" aria-label="A quiet mountain lake at sunset" className="interaction-image">
      <rect width="200" height="80" fill="#e7edf0" /><circle cx="150" cy="20" r="12" fill="#e5be72" />
      <path d="M0 60L55 10L105 60L150 30L200 60Z" fill="#6b8790" /><path d="M0 60H200V80H0Z" fill="#92b9cd" />
    </svg> : null}
    <p className="text-sm">{activity.prompt}</p>
    <button type="button" className="btn secondary" onClick={() => onUse(activity)}>Use this</button>
  </article>;
}

function InteractionSuggestions({progress, context, onUse}) {
  const activities = puzzleModules.suggestInteractions({floor: progress.currentFloor,
    recentMessages: progress.messages, context, allowSensitivePrompts: progress.allowSensitivePrompts});
  return <section className="interaction-suggestions" aria-label="Suggested interactions">
    <h3>Suggested interactions</h3>
    {activities.map(activity => <InteractionCard key={activity.id} activity={activity} onUse={onUse} />)}
  </section>;
}

function IdentityRevealControl({progress, connection}) {
  const mine = Boolean(connection.myConsent), theirs = Boolean(connection.peerConsent);
  const revealed = connection.reveal === 'revealed';
  return <section className="puzzle-panel identity-module" aria-label="Identity sharing">
    <h2 className="puzzle-title">Identity sharing</h2>
    <p className="puzzle-note text-sm">{!progress.identityAvailable ? 'Available after both people complete Floor 2.'
      : revealed ? 'You both approved sharing your identities.'
      : mine ? 'Waiting for your connection to approve.'
      : theirs ? 'Your connection requested identity sharing. It is your choice.'
      : 'Available. Your name stays private unless you both approve.'}</p>
    {revealed ? <p>{connection.identity}</p> : <button type="button" className="btn primary w-full"
      disabled={!progress.identityAvailable} data-action="unlock">
      {!progress.identityAvailable ? 'Unavailable' : mine ? 'View identity request' : theirs ? 'Review identity request' : 'Request identity sharing'}
    </button>}
  </section>;
}

function ConnectionTools({connectionId, profile, connection, owners, onShare}) {
  const [tab, setTab] = PuzzleReact.useState('conversation');
  const baseId = PuzzleReact.useId();
  const progress = connection.floorProgress
    ? {...connection.floorProgress, messages: connection.messages.filter(message => message.kind !== 'notice')}
    : puzzleModules.getConnectionState(connectionId, owners.map(owner => owner.id));
  const [error, setError] = PuzzleReact.useState('');
  async function update(method, input, local) {
    setError('');
    try {
      if (connection.floorProgress) await window.intersectConnectionAction(method, {connectionId: connection.id, ...input});
      else { local(); await window.intersectRefreshLocalConnection?.(); }
    } catch (error) { setError(error.message); }
  }
  const tabs = [['conversation', 'Conversation'], ['puzzle', 'Puzzle'], ['identity', 'Identity']];
  function choose(index, focus = false) {
    setTab(tabs[index][0]);
    if (focus) document.getElementById(`${baseId}-tab-${tabs[index][0]}`)?.focus();
  }
  function use(activity) {
    if (activity.type === 'puzzle') { setTab('puzzle'); return; }
    const input = document.querySelector('[data-form="message"] input');
    if (input) { input.value = activity.prompt; input.dispatchEvent(new Event('input', {bubbles: true})); input.focus(); }
  }
  return <div className="connection-tools">
    {error ? <p role="alert" className="puzzle-panel">{error}</p> : null}
    <div className="module-tabs" role="tablist" aria-label="Connection tools">
      {tabs.map(([id, label], index) => <button key={id} type="button" role="tab" id={`${baseId}-tab-${id}`}
        aria-selected={tab === id} aria-controls={`${baseId}-panel-${id}`} tabIndex={tab === id ? 0 : -1}
        onClick={() => choose(index)} onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
          if (next !== null) { event.preventDefault(); choose(next, true); }
        }}>{label}</button>)}
    </div>
    <section role="tabpanel" id={`${baseId}-panel-conversation`} aria-labelledby={`${baseId}-tab-conversation`} hidden={tab !== 'conversation'} className="puzzle-panel">
      <ConnectionFloor progress={progress} />
      <FloorProgress progress={progress} userId={profile.id} peer={connection.alias} />
      <AdvanceFloor progress={progress} connectionId={connectionId} userId={profile.id}
        onReady={ready => update('setConnectionFloorReady', {ready, floor: progress.currentFloor}, () => puzzleModules.setFloorReady(connectionId, profile.id, ready))} />
      <InteractionSuggestions progress={progress} context={connection.shared} onUse={use} />
      <SensitivePromptOptIn progress={progress} connectionId={connectionId} userId={profile.id}
        onChange={enabled => update('setConnectionSensitiveOptIn', {enabled}, () => puzzleModules.setSensitiveOptIn(connectionId, profile.id, enabled))} />
    </section>
    <section role="tabpanel" id={`${baseId}-panel-puzzle`} aria-labelledby={`${baseId}-tab-puzzle`} hidden={tab !== 'puzzle'}>
      {owners.every(owner => owner.pieces.length >= 4 && owner.pieces.length <= 8) ? <SharedPuzzle owners={owners} connectionId={connectionId} currentUserId={profile.id} onShare={onShare} />
        : <div className="puzzle-panel"><h2 className="puzzle-title">Your shared puzzle</h2>
          <p className="puzzle-note text-sm">Create your pieces at signup, or try a sample account to build a shared puzzle.</p>
          <a href="/login?demo=1" className="text-link">Try a sample account</a></div>}
    </section>
    <section role="tabpanel" id={`${baseId}-panel-identity`} aria-labelledby={`${baseId}-tab-identity`} hidden={tab !== 'identity'}>
      <IdentityRevealControl progress={progress} connection={connection} />
    </section>
  </div>;
}
