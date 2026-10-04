/** The single integration point for a future Reflex/Python or HTTP provider. */
import {prepareProvider} from './contracts.mjs';

export async function createProvider() {
  // A host can supply a provider factory before demo.js runs. When integrating,
  // replace this selection with an import of the real provider. Never fall back
  // to demo data if an explicitly selected provider fails.
  if (typeof window.intersectProviderFactory === 'function') {
    return prepareProvider(await window.intersectProviderFactory());
  }
  const {createDemoProvider} = await import('./demo-provider.mjs');
  return prepareProvider(await createDemoProvider());
}
