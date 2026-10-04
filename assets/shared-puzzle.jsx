
function PuzzlePiece({piece, slot, color, owner, onSelect, preview = false}) {
  const revealed = Boolean(piece?.isShared);
  const activate = () => { if (revealed) onSelect(piece); };
  // Private labels/descriptions are never rendered in the SVG, including titles and ARIA.
  return <g className="puzzle-piece" transform={`translate(${slot.x} ${slot.y})`}
    role={revealed ? 'button' : undefined} tabIndex={revealed ? 0 : undefined}
    aria-label={revealed ? `${piece.shortLabel}, ${preview ? 'your puzzle piece' : `shared by ${owner}`}` : 'Unrevealed puzzle piece'}
    onClick={revealed ? activate : undefined}
    onKeyDown={revealed ? event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
    } : undefined}>
    <path d={slot.path} fill={revealed ? color : '#eee9df'} stroke="#fffdf8" strokeWidth="2" strokeLinejoin="round" />
    {revealed ? <text x="50" y="53" textAnchor="middle" dominantBaseline="middle"
      fill="white" fontSize={piece.shortLabel.length > 13 ? 9 : 13} fontWeight="600"
      pointerEvents="none">{piece.shortLabel}</text> : null}
  </g>;
}


function PuzzlePieceDetail({piece, owner, onClose, preview = false}) {
  if (!piece?.isShared) return null;
  return <section className="puzzle-detail"
    style={{'--piece-color': owner.color}} aria-label="Puzzle piece details">
    <div className="flex items-start justify-between gap-3">
      <h3 className="puzzle-detail-title">{piece.shortLabel}</h3>
      <button type="button" onClick={onClose} className="puzzle-detail-close" aria-label="Close piece details">×</button>
    </div>
    <p className="puzzle-note text-xs">{preview ? 'Your private puzzle piece' : `Shared by ${owner.alias}`}</p>
    <p className="puzzle-description text-sm">{piece.description}</p>
  </section>;
}


function SharePuzzlePiece({pieces, onShare}) {
  const [selectedId, setSelectedId] = PuzzleReact.useState('');
  const selectId = PuzzleReact.useId();
  const unshared = pieces.filter(piece => !piece.isShared);
  const selected = unshared.find(piece => piece.id === selectedId);
  if (!unshared.length) return <p className="puzzle-note text-sm">You have shared all your pieces in this conversation.</p>;
  return <div className="puzzle-stack">
    <label htmlFor={selectId} className="puzzle-select-label">Share a little about you</label>
    <select id={selectId} value={selected?.id || ''} onChange={event => setSelectedId(event.target.value)}
      className="puzzle-select w-full text-sm">
      <option value="">Select a piece</option>
      {unshared.map(piece => <option key={piece.id} value={piece.id}>{piece.shortLabel}</option>)}
    </select>
    <button type="button" disabled={!selected} onClick={() => { onShare(selected.id); setSelectedId(''); }}
      className="btn primary w-full">
      Share piece
    </button>
  </div>;
}


function SharedPuzzle({owners, connectionId, currentUserId, onShare}) {
  const {mixedPuzzleSlots, layoutSize} = puzzleModules;
  const [selectedId, setSelectedId] = PuzzleReact.useState(null);
  const [announcement, setAnnouncement] = PuzzleReact.useState('');
  const pieces = owners.flatMap(owner => owner.pieces);
  const revealed = pieces.filter(piece => piece.isShared).length;
  const current = owners.find(owner => owner.id === currentUserId);
  const selected = pieces.find(piece => piece.id === selectedId && piece.isShared);
  const slots = mixedPuzzleSlots(owners, connectionId);
  const height = Math.max(...owners.map(owner => layoutSize(owner.pieces.length))) / 2 * 100;
  return <section className="puzzle-panel" aria-label="Shared puzzle">
    <div className="puzzle-heading">
      <p className="section-label">A little more of us</p>
      <h2 className="puzzle-title">Your shared puzzle</h2>
      <p className="puzzle-intro text-sm">One connection. Two stories. Share a piece as you get to know each other.</p>
    </div>
    <div className="puzzle-legend flex flex-wrap gap-4 text-sm">
      {owners.map(owner => <span key={owner.id} className="flex items-center gap-2">
        <span className="puzzle-color-dot" style={{backgroundColor: owner.color}} />
        {owner.alias}{owner.id === currentUserId ? ' (you)' : ''}
      </span>)}
    </div>
    <svg viewBox={`-4 -4 408 ${height + 8}`} className="puzzle-board" aria-label={`${revealed} of ${pieces.length} pieces shared`}>
      {slots.map(({slot, piece, owner}, index) => <PuzzlePiece
        key={piece?.id || `blank-${index}`}
        piece={piece} slot={slot} color={owner.color} owner={owner.alias}
        onSelect={piece => setSelectedId(piece.id)} />)}
    </svg>
    <div className="puzzle-heading">
      <p className="puzzle-count text-sm">{revealed} of {pieces.length} pieces shared</p>
      <p className="puzzle-note text-xs">Blank pieces stay private. Select a colored piece to read its story.</p>
    </div>
    <PuzzlePieceDetail piece={selected} owner={owners.find(owner => owner.id === selected?.ownerId)} onClose={() => setSelectedId(null)} />
    {current ? <SharePuzzlePiece pieces={current.pieces} onShare={id => {
      const piece = current.pieces.find(piece => piece.id === id);
      onShare(id); setAnnouncement(`${piece.shortLabel} is now shared in this puzzle.`);
    }} /> : null}
    <p role="status" aria-live="polite" className="puzzle-note text-sm">{announcement}</p>
  </section>;
}


function PuzzlePreview() {
  const [, setRevision] = PuzzleReact.useState(0);
  const [selectedId, setSelectedId] = PuzzleReact.useState(null);
  PuzzleReact.useEffect(() => {
    const update = () => setRevision(value => value + 1);
    window.addEventListener('intersect:puzzle-change', update);
    return () => window.removeEventListener('intersect:puzzle-change', update);
  }, []);
  const owner = puzzleModules.getUserPuzzle(window.intersectPuzzleOwnerId);
  if (!owner?.pieces.length || owner.pieces.length > 8) return null;
  const size = puzzleModules.layoutSize(Math.max(4, owner.pieces.length));
  const pieces = owner.pieces.map(piece => ({...piece, isShared: true}));
  const selected = pieces.find(piece => piece.id === selectedId);
  return <div className="puzzle-builder-preview">
    <svg viewBox={`-4 -4 208 ${size / 2 * 100 + 8}`} className="puzzle-board" aria-label="Your puzzle preview">
      {puzzleModules.PUZZLE_LAYOUTS[size].map((slot, index) => <PuzzlePiece key={index}
        piece={pieces[index]} slot={slot} color={owner.color} owner={owner.alias} preview
        onSelect={piece => setSelectedId(piece.id)} />)}
    </svg>
    <PuzzlePieceDetail piece={selected} owner={owner} onClose={() => setSelectedId(null)} preview />
    <p className="puzzle-note text-sm">Preview only. Your pieces stay private until you share them in a chat.</p>
  </div>;
}

function PuzzleSignup() {
  const [pieces, setPieces] = PuzzleReact.useState(() => Array.from({length: 4}, () => ({shortLabel: '', description: ''})));
  function update(index, field, value) {
    setPieces(previous => previous.map((piece, i) => i === index ? {...piece, [field]: value} : piece));
  }
  return <fieldset className="puzzle-signup" data-puzzle-signup="true">
    <legend className="puzzle-subtitle">Your puzzle pieces</legend>
    <p className="puzzle-note text-sm">Create 4–8 pieces about yourself. They stay hidden until you choose to share them in a conversation.</p>
    {pieces.map((piece, index) => <div key={index} className="puzzle-draft">
      <label className="puzzle-field text-sm">Piece {index + 1} · Title
        <input name={`puzzle-label-${index}`} required maxLength={20} value={piece.shortLabel}
          pattern=".*\S.*" title="Use a label with at least one non-space character."
          placeholder="e.g. Robotics" onChange={event => update(index, 'shortLabel', event.target.value)}
          className="puzzle-input mt-1 w-full" />
      </label>
      <label className="puzzle-field text-sm">Description
        <textarea name={`puzzle-description-${index}`} required maxLength={500} value={piece.description}
          placeholder="Tell a little of your story…" onChange={event => {
            event.target.setCustomValidity(event.target.value.trim() ? '' : 'Describe your piece.');
            update(index, 'description', event.target.value);
          }} className="puzzle-input mt-1 w-full" rows={2} />
      </label>
    </div>)}
    <div className="flex items-center gap-3 text-sm">
      <button type="button" disabled={pieces.length === 8} className="btn secondary"
        onClick={() => setPieces(previous => [...previous, {shortLabel: '', description: ''}])}>Add piece</button>
      <button type="button" disabled={pieces.length === 4} className="btn secondary"
        onClick={() => setPieces(previous => previous.slice(0, -1))}>Remove last piece</button>
      <span>{pieces.length} / 8</span>
    </div>
  </fieldset>;
}


function DemoAccounts() {
  const {DEMO_ACCOUNTS, signInDemo, leaveDemo, getDemoAccount} = puzzleModules;
  return <section className="puzzle-demo-accounts" aria-label="Sample accounts">
    <h2 className="puzzle-subtitle">Try a sample account</h2>
    <p className="puzzle-note text-sm">Four local demo accounts, connected through shared answers, polls, and questions. No password needed.</p>
    <div className="puzzle-account-grid">
      {DEMO_ACCOUNTS.map(account => <button key={account.id} type="button"
        className="puzzle-account-button text-left"
        onClick={() => { signInDemo(account.id); window.location.assign('/messages'); }}>
        <span className="puzzle-account-name" style={{color: account.color}}>Sign in as {account.alias}</span>
        <span className="puzzle-account-note text-xs">{account.pieces.length} pieces · 3 connections</span>
      </button>)}
    </div>
    {getDemoAccount() ? <button type="button" className="text-link" onClick={() => { leaveDemo(); window.location.assign('/login'); }}>Leave demo</button> : null}
  </section>;
}

let puzzleModules;

function PuzzleChat() {
  const {getConnectionPuzzle, getUserPuzzle, sharePiece} = puzzleModules;
  const [chat, setChat] = PuzzleReact.useState(() => window.intersectPuzzleChat || null);
  const [, setRevision] = PuzzleReact.useState(0);
  PuzzleReact.useEffect(() => {
    const select = event => setChat(event.detail);
    const update = () => setRevision(value => value + 1);
    window.addEventListener('intersect:chat-selected', select);
    window.addEventListener('intersect:puzzle-change', update);
    window.addEventListener('intersect:connection-change', update);
    return () => {
      window.removeEventListener('intersect:chat-selected', select);
      window.removeEventListener('intersect:puzzle-change', update);
      window.removeEventListener('intersect:connection-change', update);
    };
  }, []);
  if (!chat?.connection) return null;
  const {profile, connection} = chat;
  const key = connection.puzzleKey || `local:${profile.id}:${connection.id}`;
  const ids = [profile.id, connection.peerId || `peer:${connection.id}`].sort();
  let owners = getConnectionPuzzle(key, ids);
  // Without a puzzle backend, an authenticated peer's local pieces are unavailable.
  owners = owners.map((owner, index) => owner || {
    id: ids[index], alias: ids[index] === profile.id ? profile.alias : connection.alias,
    color: ids[index] === profile.id ? '#2d6791' : '#ad4c32',
    pieces: ids[index] === profile.id ? [] : Array.from({length: 4}, (_, i) => ({id: `${ids[index]}-blank-${i}`, ownerId: ids[index], shortLabel: '', description: '', isShared: false})),
  });
  return <ConnectionTools key={key} connectionId={key} owners={owners} profile={profile} connection={connection}
    onShare={pieceId => sharePiece(key, profile.id, pieceId)} />;
}

function PuzzleWidget({mode}) {
  const [ready, setReady] = PuzzleReact.useState(false);
  const [error, setError] = PuzzleReact.useState(false);
  PuzzleReact.useEffect(() => {
    let disposed = false;
    // Absolute URLs keep Vite's dynamic-import helper from adding ?import to
    // public assets. These modules must be served unchanged in dev and prod.
    const assetURL = path => new URL(path, window.location.origin).href;
    const storePath = assetURL('/services/puzzle-store.mjs');
    const layoutsPath = assetURL('/services/puzzle-layouts.mjs');
    const floorsPath = assetURL('/services/connection-state.mjs');
    const definitionsPath = assetURL('/data/connection-floors.mjs');
    const suggestionsPath = assetURL('/services/interaction-suggestions.mjs');
    Promise.all([
      import(/* @vite-ignore */ storePath),
      import(/* @vite-ignore */ layoutsPath),
      import(/* @vite-ignore */ floorsPath),
      import(/* @vite-ignore */ definitionsPath),
      import(/* @vite-ignore */ suggestionsPath),
    ]).then(([store, layouts, floors, definitions, suggestions]) => {
      puzzleModules = {...store, ...layouts, ...floors, ...definitions, ...suggestions};
      if (!disposed) setReady(true);
    }).catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, []);
  if (error) return <p role="status" className="puzzle-note">Unable to load your puzzle. Refresh and try again.</p>;
  if (!ready) return null;
  return mode === 'preview' ? <PuzzlePreview /> : mode === 'signup' ? <PuzzleSignup /> : mode === 'accounts' ? <DemoAccounts /> : <PuzzleChat />;
}
