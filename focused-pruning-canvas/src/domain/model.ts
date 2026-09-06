import { z } from 'zod';

export type GateExpression =
  | { kind: 'condition'; factorId: string; is: 'present' | 'absent' }
  | { kind: 'all' | 'any'; children: GateExpression[] }
  | { kind: 'not'; child: GateExpression };
const id = z.string().min(1).max(120);
const label = z
  .string()
  .min(1)
  .max(120)
  .refine((s) => s.trim().length > 0, 'ラベルは空にできません');
const text = z.string().max(4000);
const sourceRefs = z.array(id).max(100);
const confidence = z.number().min(0).max(1);
export const factorStates = [
  'present',
  'absent',
  'unknown',
  'unobservable',
] as const;
export const expressionSchema: z.ZodType<GateExpression> = z.lazy(() =>
  z.discriminatedUnion('kind', [
    z.strictObject({
      kind: z.literal('condition'),
      factorId: id,
      is: z.enum(['present', 'absent']),
    }),
    z.strictObject({
      kind: z.literal('all'),
      children: z.array(expressionSchema).min(1).max(100),
    }),
    z.strictObject({
      kind: z.literal('any'),
      children: z.array(expressionSchema).min(1).max(100),
    }),
    z.strictObject({ kind: z.literal('not'), child: expressionSchema }),
  ]),
);
export const hypothesisSchema = z.strictObject({
  id,
  label,
  baseScore: z.number().min(-5).max(5),
  manualAdjustment: z.number().min(-5).max(5),
  manualPruned: z.boolean(),
  mustKeep: z.boolean(),
  residual: z.boolean(),
  decisionImpact: z.number().min(0).max(100),
  riskNote: text,
  sourceRefs,
});
export const factorSchema = z.strictObject({
  id,
  label,
  kind: z.enum(['observation', 'assumption', 'model_rule']),
  state: z.enum(factorStates),
  confidence,
  opportunity: z.enum(['yes', 'no', 'unknown']),
  verification: z.enum(['unverified', 'verified']),
  sourceRefs,
});
export const effectSchema = z.strictObject({
  id,
  factorId: id,
  hypothesisId: id,
  strength: z.number().min(-2).max(2),
  applicabilityConfidence: confidence,
  activeStates: z
    .array(z.enum(['present', 'absent']))
    .min(1)
    .max(2),
  when: expressionSchema.optional(),
  evidenceGroupId: id.nullable(),
  sourceRefs,
});
export const groupSchema = z.strictObject({
  id,
  label,
  aggregation: z.enum(['maxAbs', 'mean', 'sum']),
  rationale: text,
});
export const gateSchema = z.strictObject({
  id,
  hypothesisId: id,
  expression: expressionSchema,
  mode: z.enum(['informational', 'soft', 'hard']),
  falsePenalty: z
    .number()
    .min(-2)
    .max(0)
    .refine((n) => n < 0, 'falsePenalty は負値'),
  evidenceGroupId: id.nullable(),
  explanation: text,
});
export const noteSchema = z.strictObject({
  id,
  ownerHypothesisId: id,
  parentNoteId: id.nullable(),
  order: z.number().int().min(0),
  label,
  body: text,
  sourceRefs,
});
export const boardSchema = z.strictObject({
  id,
  title: label,
  question: text,
  classificationAssumption: text,
  hypotheses: z.array(hypothesisSchema).min(1).max(51),
  factors: z.array(factorSchema).max(100),
  effects: z.array(effectSchema).max(300),
  evidenceGroups: z.array(groupSchema).max(300),
  gates: z.array(gateSchema).max(50),
  notes: z.array(noteSchema).max(300),
  sourceMaterials: z
    .array(z.strictObject({ id, label, text: z.string().max(64000) }))
    .max(100),
  modelConfig: z.strictObject({
    scoreScale: z.number().min(0.1).max(1),
    temperature: z.number().min(0.5).max(3),
  }),
  decisionMemo: text,
  reflectionMemo: text,
});
export const snapshotSchema = z.strictObject({
  id,
  timestamp: z.iso.datetime(),
  actionLabel: label,
  document: boardSchema,
});
export const envelopeSchema = z.strictObject({
  schemaVersion: z.literal('pruning-canvas.v1'),
  engineVersion: z.literal('weighted-score.v1'),
  revision: id,
  snapshots: z.array(snapshotSchema).min(1).max(50),
  cursor: z.number().int().min(0),
});
export type BoardDocument = z.infer<typeof boardSchema>;
export type Hypothesis = z.infer<typeof hypothesisSchema>;
export type Factor = z.infer<typeof factorSchema>;
export type Effect = z.infer<typeof effectSchema>;
export type EvidenceGroup = z.infer<typeof groupSchema>;
export type Gate = z.infer<typeof gateSchema>;
export type Note = z.infer<typeof noteSchema>;
export type Envelope = z.infer<typeof envelopeSchema>;
export type Snapshot = z.infer<typeof snapshotSchema>;
export type Truth = 'true' | 'false' | 'unknown';
export const limits = {
  document: 512 * 1024,
  envelope: 2 * 1024 * 1024,
  file: 5 * 1024 * 1024,
  history: 50,
} as const;
export const byteSize = (value: unknown) =>
  new TextEncoder().encode(
    typeof value === 'string' ? value : JSON.stringify(value),
  ).length;
