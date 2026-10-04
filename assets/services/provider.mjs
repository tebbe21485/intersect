/** The production provider uses authenticated Reflex/Python HTTP routes. */
import {prepareProvider} from './contracts.mjs';

export async function createProvider() {
  // Explicit injection is available for isolated fixtures/tests. Neither an
  // injected nor the default backend provider falls back to demo records.
  if (typeof window.intersectProviderFactory === 'function') {
    return prepareProvider(await window.intersectProviderFactory());
  }
  const {createBackendProvider} = await import('./backend-provider.mjs');
  return prepareProvider(await createBackendProvider());
}
