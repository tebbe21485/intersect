(async () => {
  const {request, session, action} = await import('/services/http.mjs');
  const {leaveDemo, getDemoAccount} = await import('/services/puzzle-store.mjs');
  const form = document.getElementById('account-form');
  const status = document.getElementById('account-status');
  if (!form || form.dataset.ready) return;
  form.dataset.ready = 'true';
  const mode = form.dataset.mode;
  let ready = false;
  const show = (message, error = false) => {
    status.textContent = message;
    status.hidden = !message;
    status.dataset.error = String(error);
  };
  const controls = () => [...form.elements];
  const disabledStates = new Map();
  const disable = value => {
    if (value) controls().forEach(control => {
      if (!disabledStates.has(control)) disabledStates.set(control, control.disabled);
      control.disabled = true;
    });
    else {
      disabledStates.forEach((disabled, control) => { if (control.isConnected) control.disabled = disabled; });
      disabledStates.clear();
      form.querySelector('button[type="submit"]').disabled = false;
    }
  };
  const clearField = field => {
    field.removeAttribute('aria-invalid');
    field.removeAttribute('aria-describedby');
  };
  const markField = name => {
    const field = form.elements.namedItem(name);
    if (!field) return;
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', 'account-status');
  };
  const focusInvalid = () => form.querySelector('[aria-invalid="true"]')?.focus();
  if (mode === 'login') form.noValidate = true;
  form.addEventListener('input', event => {
    if (event.target.getAttribute('aria-invalid') !== 'true') return;
    clearField(event.target);
    if (!form.querySelector('[aria-invalid="true"]')) show('');
  });
  function validateLogin() {
    const email = form.elements.namedItem('email');
    const password = form.elements.namedItem('password');
    const messages = [];
    if (!email.value.trim() || !email.validity.valid || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
      markField('email');
      messages.push('Enter a valid email address.');
    }
    if (password.value.length < 10 || password.value.length > 128) {
      markField('password');
      messages.push('Use a password of 10 to 128 characters.');
    }
    if (messages.length) { show(messages.join(' '), true); focusInvalid(); return false; }
    return true;
  }
  async function initialize() {
    disable(true);
    try {
      if (mode === 'login' && (getDemoAccount() || new URLSearchParams(location.search).has('demo'))) {
        ready = true; form.dataset.initialized = 'true'; show(''); return;
      }
      const current = await session();
      if (mode === 'profile') {
        if (!current.profile) { location.assign('/login'); return; }
        for (const name of ['firstName','lastName','linkedin','phone']) form.elements.namedItem(name).value = current.profile[name] || '';
      } else if (current.profile) { location.assign('/'); return; }
      ready = true; form.dataset.initialized = 'true'; show('');
    } catch (error) { show(error.userMessage || 'Unable to load. Refresh and try again.', true); }
    finally { disable(false); }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!ready) { await initialize(); return; }
    controls().forEach(clearField);
    if (mode === 'login' && !validateLogin()) return;
    const input = Object.fromEntries(new FormData(form));
    disable(true); show('Saving…');
    try {
      if (mode === 'profile') { await action('saveProfile', input); show('Profile saved. Phone sharing choices have been reset.'); }
      else {
        await request(mode, input, {redirect:false});
        leaveDemo();
        sessionStorage.removeItem('intersect-ui-v1');
        location.assign(mode === 'register' ? '/matching' : '/');
      }
    } catch (error) {
      const message = error.userMessage || 'Unable to save. Please try again.';
      if (mode === 'login') {
        if (error.status === 401) { markField('email'); markField('password'); }
        else if (error.status === 400) {
          if (/email/i.test(message)) markField('email');
          if (/password/i.test(message)) markField('password');
        }
      }
      show(message, true);
    }
    finally { disable(false); focusInvalid(); }
  });
  document.getElementById('logout-button')?.addEventListener('click', async () => {
    try { await request('logout', {}); sessionStorage.removeItem('intersect-ui-v1'); location.assign('/login'); }
    catch (error) { show(error.userMessage, true); }
  });
  await initialize();
})();
