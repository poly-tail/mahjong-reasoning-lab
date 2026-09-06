import { limits } from '../domain/model';
export function downloadText(
  text: string,
  format: 'json' | 'md' | 'txt',
): void {
  const url = URL.createObjectURL(
    new Blob([text], {
      type:
        format === 'json'
          ? 'application/json;charset=utf-8'
          : 'text/plain;charset=utf-8',
    }),
  );
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `focused-pruning-canvas.${format}`;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
export async function readFile(file: File): Promise<string> {
  if (file.size > limits.file) throw new Error('入力ファイルは5MiBまでです');
  return file.text();
}
