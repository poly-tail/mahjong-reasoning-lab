import { byteSize, limits, type Envelope } from '../domain/model';
import { evaluate, formatShare } from '../domain/scoring';
import { importJson } from './jsonTransfer';
import { parseEnvelope } from '../domain/validation';
import { explainHypothesis } from '../domain/explanations';

const escapeText = (text: string) =>
  text
    .replace(/[&<>`*_{}[\]()#+.!|~\\-]/g, (c) => `&#${c.charCodeAt(0)};`)
    .replace(/\r?\n/g, '<br>');
export function exportMarkdown(envelope: Envelope): string {
  // JSON string newlines are escaped by JSON.stringify; user text cannot start a fence line.
  const json = JSON.stringify(parseEnvelope(envelope));
  const board = envelope.snapshots[envelope.cursor].document;
  const evaluation = evaluate(board);
  const main = [...evaluation.hypotheses].sort(
    (a, b) => b.displayShare - a.displayShare,
  )[0];
  const lines = [
    '# Focused Pruning Canvas',
    '',
    '本文の編集は復元に反映されず、埋込データが正本です。専用Markdown形式。相対配分（未校正）・実測確率ではありません。',
    '',
    `問い: ${escapeText(board.question)}`,
    `分類仮定: ${escapeText(board.classificationAssumption)}`,
    `本線: ${escapeText(board.hypotheses.find((h) => h.id === main.id)!.label)}`,
    '',
    '## 仮説と主要理由',
  ];
  for (const h of board.hypotheses) {
    const result = evaluation.hypotheses.find((r) => r.id === h.id)!;
    lines.push(
      `- ${escapeText(h.label)}: ${formatShare(result.displayShare)}${h.residual ? ' [残余・例外]' : ''}${h.mustKeep ? ' [保護]' : ''}`,
      `  ${escapeText(h.riskNote)}`,
    );
    explainHypothesis(board, result).weak.forEach((l) =>
      lines.push(
        `  - ${escapeText(l.label)}: ${l.appliedValue} (${escapeText(l.reason)})`,
      ),
    );
  }
  lines.push(
    '',
    '## 未確定事項',
    ...evaluation.warnings.map((w) => `- ${escapeText(w)}`),
    '',
    '## メモ',
    escapeText(board.decisionMemo),
    escapeText(board.reflectionMemo),
    ...board.notes.map(
      (n) => `- ${escapeText(n.label)}: ${escapeText(n.body)}`,
    ),
    '',
    '```pruning-ui-json',
    json,
    '```',
    '',
  );
  const text = lines.join('\n');
  if (byteSize(text) > limits.file)
    throw new Error('Markdown出力が5MiBを超えました。JSONで退避してください');
  return text;
}
export function importMarkdown(raw: string): Envelope {
  if (byteSize(raw) > limits.file)
    throw new Error('入力ファイルは5MiBまでです');
  const normalized = raw.replace(/\r\n/g, '\n');
  const openings = normalized.match(/^```pruning-ui-json[ \t]*$/gm) ?? [];
  const blocks = [
    ...normalized.matchAll(
      /^```pruning-ui-json[ \t]*\n([\s\S]*?)^```[ \t]*$/gm,
    ),
  ];
  if (openings.length !== 1 || blocks.length !== 1)
    throw new Error(
      '専用 pruning-ui-json block が厳密に一つ必要です。本文編集は復元に反映されません',
    );
  return importJson(blocks[0][1]);
}
