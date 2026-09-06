import {
  boardSchema,
  envelopeSchema,
  byteSize,
  limits,
  type BoardDocument,
  type Envelope,
  type GateExpression,
} from './model';
import { aggregateContributions, contributionCandidates } from './scoring';

function fail(message: string): never {
  throw new Error(message);
}
function safeShape(
  value: unknown,
  ancestors = new Set<object>(),
  depth = 0,
): void {
  if (depth > 40) fail('データ構造が深すぎます');
  if (value && typeof value === 'object') {
    if (ancestors.has(value)) fail('循環したデータは読み込めません');
    ancestors.add(value);
    for (const child of Object.values(value))
      safeShape(child, ancestors, depth + 1);
    ancestors.delete(value);
  }
}
function validateExpression(
  expression: GateExpression,
  factors: Set<string>,
  depth = 1,
): void {
  if (depth > 8) fail('条件木は最大深さ8です');
  if (expression.kind === 'condition') {
    if (!factors.has(expression.factorId))
      fail(`条件参照が不明: ${expression.factorId}`);
  } else if (expression.kind === 'not')
    validateExpression(expression.child, factors, depth + 1);
  else
    expression.children.forEach((c) =>
      validateExpression(c, factors, depth + 1),
    );
}
export function semanticValidation(board: BoardDocument): void {
  const elements = [
    board,
    ...board.hypotheses,
    ...board.factors,
    ...board.effects,
    ...board.evidenceGroups,
    ...board.gates,
    ...board.notes,
    ...board.sourceMaterials,
  ];
  if (new Set(elements.map((e) => e.id)).size !== elements.length)
    fail('要素IDが重複しています');
  const hypotheses = new Map(board.hypotheses.map((h) => [h.id, h]));
  const factors = new Set(board.factors.map((f) => f.id));
  const groups = new Set(board.evidenceGroups.map((g) => g.id));
  const sources = new Set(board.sourceMaterials.map((s) => s.id));
  const residuals = board.hypotheses.filter((h) => h.residual);
  if (residuals.length !== 1) fail('残余枝は必ず一つ必要です');
  if (board.hypotheses.filter((h) => !h.residual).length > 50)
    fail('通常仮説は50件までです');
  for (const h of board.hypotheses) {
    if (h.mustKeep && h.manualPruned) fail('保護する前に復元してください');
    if (h.residual && (!h.mustKeep || h.manualPruned))
      fail('残余枝の保護は解除できません');
  }
  for (const element of elements)
    if ('sourceRefs' in element)
      for (const ref of element.sourceRefs)
        if (!sources.has(ref)) fail(`原文参照が不明: ${ref}`);
  if (board.sourceMaterials.reduce((sum, s) => sum + s.text.length, 0) > 64000)
    fail('原文は合計64,000文字までです');
  for (const group of board.evidenceGroups)
    if (group.aggregation === 'sum' && !group.rationale.trim())
      fail('sumには加算理由が必要です');
  const keys = new Set<string>();
  for (const effect of board.effects) {
    if (!factors.has(effect.factorId) || !hypotheses.has(effect.hypothesisId))
      fail(`Effect参照が不明: ${effect.id}`);
    if (effect.evidenceGroupId && !groups.has(effect.evidenceGroupId))
      fail(`同根参照が不明: ${effect.id}`);
    if (new Set(effect.activeStates).size !== effect.activeStates.length)
      fail('activeStatesが重複しています');
    if (effect.when) validateExpression(effect.when, factors);
    const canonical = (e: GateExpression): unknown =>
      e.kind === 'condition'
        ? [e.kind, e.factorId, e.is]
        : e.kind === 'not'
          ? [e.kind, canonical(e.child)]
          : [
              e.kind,
              e.children
                .map(canonical)
                .map((c) => JSON.stringify(c))
                .sort(),
            ];
    const key = JSON.stringify([
      effect.factorId,
      effect.hypothesisId,
      [...effect.activeStates].sort(),
      effect.when ? canonical(effect.when) : null,
    ]);
    if (keys.has(key))
      fail('同じ要因・仮説・状態・適用条件のEffectは重複登録できません');
    keys.add(key);
  }
  for (const gate of board.gates) {
    if (!hypotheses.has(gate.hypothesisId)) fail(`Gate参照が不明: ${gate.id}`);
    if (hypotheses.get(gate.hypothesisId)?.residual)
      fail('残余枝にゲートは設定できません');
    if (gate.evidenceGroupId && !groups.has(gate.evidenceGroupId))
      fail('Gateの同根参照が不明です');
    validateExpression(gate.expression, factors);
  }
  const notes = new Map(board.notes.map((n) => [n.id, n]));
  for (const note of board.notes) {
    if (!hypotheses.has(note.ownerHypothesisId))
      fail(`Noteの仮説参照が不明: ${note.id}`);
    const seen = new Set([note.id]);
    let parent = note.parentNoteId;
    let depth = 1;
    while (parent) {
      if (seen.has(parent)) fail('Noteが循環しています');
      seen.add(parent);
      const p = notes.get(parent);
      if (!p) fail(`Noteの親参照が不明: ${parent}`);
      if (p.ownerHypothesisId !== note.ownerHypothesisId)
        fail('異なる仮説のNoteは親子化できません');
      if (++depth > 6) fail('Noteは最大深さ6です');
      parent = p.parentNoteId;
    }
  }
  for (const h of board.hypotheses)
    aggregateContributions(board, contributionCandidates(board, h));
  if (byteSize(board) > limits.document)
    fail('Boardは512KiBまでです。現在の内容は変更されていません');
}
export function parseBoard(value: unknown): BoardDocument {
  safeShape(value);
  const result = boardSchema.safeParse(value);
  if (!result.success)
    fail(
      `文書形式エラー: ${result.error.issues
        .slice(0, 5)
        .map((i) => `${i.path.join('.')}: ${i.message}`)
        .join(' / ')}`,
    );
  semanticValidation(result.data);
  return result.data;
}
export function parseEnvelope(value: unknown): Envelope {
  safeShape(value);
  if (byteSize(value) > limits.envelope)
    fail('履歴込みデータは2MiBまでです。importでは短縮しません');
  const result = envelopeSchema.safeParse(value);
  if (!result.success)
    fail(
      `保存形式/versionエラー: ${result.error.issues
        .slice(0, 5)
        .map((i) => `${i.path.join('.')}: ${i.message}`)
        .join(' / ')}`,
    );
  const env = result.data;
  if (env.cursor >= env.snapshots.length) fail('履歴cursorが範囲外です');
  if (new Set(env.snapshots.map((s) => s.id)).size !== env.snapshots.length)
    fail('snapshot IDが重複しています');
  env.snapshots.forEach((s) => semanticValidation(s.document));
  return env;
}
