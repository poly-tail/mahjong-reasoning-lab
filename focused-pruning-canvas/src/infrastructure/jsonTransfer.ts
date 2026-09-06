import { byteSize, limits, type Envelope } from '../domain/model';
import { parseEnvelope } from '../domain/validation';
export function exportJson(envelope: Envelope): string {
  const validated = parseEnvelope(envelope);
  const pretty = JSON.stringify(validated, null, 2);
  return byteSize(pretty) <= limits.file ? pretty : JSON.stringify(validated);
}
export function importJson(raw: string): Envelope {
  if (byteSize(raw) > limits.file)
    throw new Error('入力ファイルは5MiBまでです');
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error('JSONを読み取れません。復元用のJSON形式を確認してください');
  }
  return parseEnvelope(value);
}
export function serializeStorage(envelope: Envelope): string {
  return JSON.stringify(parseEnvelope(envelope));
}
