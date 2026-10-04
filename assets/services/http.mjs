import {ProviderError} from './contracts.mjs';

const base = (window.intersectApiBaseURL || '').replace(/\/$/, '');
let csrfToken = '';
export async function request(path, input, {redirect = true, timeoutMs = 15000} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}/api/${path}`, {
      method: input === undefined ? 'GET' : 'POST', credentials: 'include', cache: 'no-store',
      headers: input === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
      body: input === undefined ? undefined : JSON.stringify(input), signal: controller.signal,
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 401 && redirect) {
        sessionStorage.removeItem('intersect-ui-v1');
        window.location.assign('/login');
      }
      const error = new ProviderError(value.message || 'Please try again.');
      error.status = response.status;
      throw error;
    }
    if (value?.csrfToken) csrfToken = value.csrfToken;
    return value;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    throw new ProviderError('Unable to reach the server. Check your connection and try again.');
  } finally { clearTimeout(timer); }
}

export const session = () => request('session', undefined, {redirect: false});
export async function moderateMessage(text) {
  if (!csrfToken) await session();
  await request('moderate-message', {text}, {redirect: false});
}
// The first saved piece can include loading the existing local matching model.
export const action = (method, input) => request('action', {method, input}, {timeoutMs: method === 'savePuzzlePiece' ? 60000 : 15000});
