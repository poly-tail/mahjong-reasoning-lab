import { createBoardStore } from '../application/boardStore';
import {
  LocalStorageRepository,
  STORAGE_KEY,
} from '../infrastructure/LocalStorageRepository';
import { createSeed } from '../seed/ponDiscardCase';

export function createApplication() {
  const repository = new LocalStorageRepository(() => window.localStorage);
  const store = createBoardStore(repository, createSeed, (actionLabel) => ({
    id: crypto.randomUUID(),
    revision: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    actionLabel,
  }));
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY || event.key === null)
      store.getState().externalChange(event.newValue);
  };
  window.addEventListener('storage', onStorage);
  return {
    store,
    dispose: () => window.removeEventListener('storage', onStorage),
  };
}
