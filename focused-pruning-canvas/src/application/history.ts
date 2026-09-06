import {
  type BoardDocument,
  type Envelope,
  byteSize,
  limits,
} from '../domain/model';
import { applyCommand, type Command } from '../domain/commands';
import { parseBoard, parseEnvelope } from '../domain/validation';

export interface CommandMetadata {
  id: string;
  revision: string;
  timestamp: string;
  actionLabel: string;
}
export function currentDocument(env: Envelope): BoardDocument {
  return env.snapshots[env.cursor].document;
}
export function createEnvelope(
  document: BoardDocument,
  meta: CommandMetadata,
): Envelope {
  const { revision, ...snapshot } = meta;
  return parseEnvelope({
    schemaVersion: 'pruning-canvas.v1',
    engineVersion: 'weighted-score.v1',
    revision,
    snapshots: [{ ...snapshot, document: parseBoard(document) }],
    cursor: 0,
  });
}
export function commit(
  env: Envelope,
  command: Command,
  meta: CommandMetadata,
): { envelope: Envelope; trimmed: boolean } {
  const document = applyCommand(currentDocument(env), command);
  if (JSON.stringify(document) === JSON.stringify(currentDocument(env)))
    return { envelope: env, trimmed: false };
  const { revision, ...snapshot } = meta;
  const next: Envelope = {
    ...env,
    revision,
    snapshots: [
      ...env.snapshots.slice(0, env.cursor + 1),
      { ...snapshot, document },
    ],
    cursor: env.cursor + 1,
  };
  let trimmed = false;
  while (
    next.snapshots.length > limits.history ||
    byteSize(next) > limits.envelope
  ) {
    if (next.snapshots.length === 1)
      throw new Error('現在の文書を含めた保存上限を超えています');
    next.snapshots.shift();
    next.cursor -= 1;
    trimmed = true;
  }
  return { envelope: parseEnvelope(next), trimmed };
}
export function moveCursor(env: Envelope, cursor: number): Envelope {
  if (cursor < 0 || cursor >= env.snapshots.length || cursor === env.cursor)
    return env;
  return { ...env, cursor };
}
