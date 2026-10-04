(async () => {
  const {request, session, action} = await import('/services/http.mjs');
  const form = document.getElementById('account-form');
  const status = document.getElementById('account-status');
  if (!form || form.dataset.ready) return;
  form.dataset.ready = 'true';
  const mode = form.dataset.mode;
  let ready = false;
  const show = message => { status.textContent = message; };
  const controls = [...form.elements];
  const disable = value => controls.forEach(control => { control.disabled = value; });
  async function initialize() {
    disable(true);
    try {
      const current = await session();
      if (mode === 'profile') {
        if (!current.profile) { location.assign('/login'); return; }
        for (const name of ['firstName','lastName','linkedin','phone']) form.elements.namedItem(name).value = current.profile[name] || '';
      } else if (current.profile) { location.assign('/'); return; }
      ready = true; form.dataset.initialized = 'true'; show('');
    } catch (error) { show(error.userMessage || 'Unable to load. Refresh and try again.'); }
    finally { disable(false); }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!ready) { await initialize(); return; }
    const input = Object.fromEntries(new FormData(form));
    disable(true); show('Saving…');
    try {
      if (mode === 'profile') { await action('saveProfile', input); show('Profile saved. Phone sharing choices have been reset.'); }
      else {
        await request(mode, input, {redirect:false});
        sessionStorage.removeItem('intersect-ui-v1');
        location.assign('/');
      }
    } catch (error) { show(error.userMessage || 'Unable to save. Please try again.'); }
    finally { disable(false); }
  });
  document.getElementById('logout-button')?.addEventListener('click', async () => {
    try { await request('logout', {}); sessionStorage.removeItem('intersect-ui-v1'); location.assign('/login'); }
    catch (error) { show(error.userMessage); }
  });
  await initialize();
})();
