import type {
  BoardDocument,
  Factor,
  GateExpression,
  Hypothesis,
} from '../domain/model';
import { parseBoard } from '../domain/validation';
import { originalSource } from './sourceMaterial';

export const condition = (
  factorId: string,
  is: 'present' | 'absent',
): GateExpression => ({ kind: 'condition', factorId, is });
export function emptyBoard(boardId: string, residualId: string): BoardDocument {
  return {
    id: boardId,
    title: '新しい考察',
    question: '何を比較しますか',
    classificationAssumption:
      '同じ問いに対する競合仮説として比較する。分類の重なり・網羅性は未検証。',
    hypotheses: [
      {
        id: residualId,
        label: 'その他・例外',
        baseScore: -0.8,
        manualAdjustment: 0,
        manualPruned: false,
        mustKeep: true,
        residual: true,
        decisionImpact: 80,
        riskNote:
          '未分類の可能性を残す。未知ケースの頻度や網羅性は保証しない。',
        sourceRefs: [],
      },
    ],
    factors: [],
    effects: [],
    evidenceGroups: [],
    gates: [],
    notes: [],
    sourceMaterials: [],
    modelConfig: { scoreScale: 0.5, temperature: 1 },
    decisionMemo: '',
    reflectionMemo: '',
  };
}
export function createSeed(): BoardDocument {
  const hypotheses: Hypothesis[] = [
    ['H1', '近くの対子・雀頭固定', 0.4, 65, false],
    ['H2', '両面固定', 0.1, 95, true],
    ['H3', '対子フォローからカンチャン固定', -0.5, 45, false],
    ['H4', 'リャンカンからカンチャン固定', -0.3, 60, false],
    ['H5', 'その他・例外', -0.8, 80, true],
  ].map((row) => ({
    id: String(row[0]),
    label: String(row[1]),
    baseScore: Number(row[2]),
    decisionImpact: Number(row[3]),
    mustKeep: Boolean(row[4]),
    residual: row[0] === 'H5',
    manualAdjustment: 0,
    manualPruned: false,
    riskNote:
      row[0] === 'H2'
        ? '赤跨ぎ等の高打点ケースは、薄くても見落とさない。打点は仮説・未検証。'
        : '',
    sourceRefs: ['S1'],
  }));
  const factorRows: [string, Factor['kind'], Factor['state'], number][] = [
    ['関連牌構成率を対子固定支持と評価', 'model_rule', 'present', 0.6],
    ['ブロックが狭い', 'assumption', 'present', 0.7],
    ['XY周辺に構成余地がある', 'assumption', 'absent', 0.7],
    ['字牌雀頭候補が十分にある', 'assumption', 'absent', 0.7],
    ['聴牌している', 'assumption', 'absent', 0.8],
    ['3飜以上の高打点が見込める', 'assumption', 'absent', 0.7],
    ['安い非聴牌での発進動機は弱い', 'model_rule', 'present', 0.6],
    [
      'チートイ・対々和等の代替ルートへ逃げやすい',
      'model_rule',
      'present',
      0.6,
    ],
    ['対子をポン材として保持する価値がある', 'model_rule', 'present', 0.7],
    ['役牌から発進した', 'assumption', 'absent', 0.7],
    ['非役牌の愚形発進レンジが狭い', 'model_rule', 'present', 0.6],
    ['ドラに反応した', 'observation', 'unknown', 0.6],
    ['鳴きのラグがあった', 'observation', 'unknown', 0.5],
    ['赤赤の構成が否定された', 'assumption', 'unknown', 0.6],
    ['役牌バック条件が成立する', 'assumption', 'unknown', 0.7],
    ['その後に手出しが入った', 'observation', 'unknown', 0.7],
  ];
  const factors: Factor[] = factorRows.map(
    ([label, kind, state, confidence], i) => ({
      id: `F${i + 1}`,
      label,
      kind,
      state,
      confidence,
      opportunity: 'unknown',
      verification: 'unverified',
      sourceRefs: ['S1'],
    }),
  );
  const cheap: GateExpression = {
    kind: 'all',
    children: [condition('F5', 'absent'), condition('F6', 'absent')],
  };
  const effectRows: [
    number,
    number,
    'present' | 'absent',
    number,
    GateExpression | undefined,
    string | null,
  ][] = [
    [1, 1, 'present', 1, undefined, null],
    [2, 2, 'present', -1, undefined, 'G1'],
    [3, 2, 'absent', -2, undefined, 'G1'],
    [4, 2, 'absent', -1, undefined, 'G1'],
    [5, 2, 'present', 2, undefined, null],
    [6, 2, 'present', 2, undefined, null],
    [7, 2, 'present', -1, cheap, 'G2'],
    [8, 2, 'present', -2, cheap, 'G2'],
    [8, 3, 'present', -1, condition('F5', 'absent'), null],
    [9, 3, 'present', -2, undefined, null],
    [10, 4, 'present', 2, undefined, null],
    [11, 4, 'present', -1.5, condition('F10', 'absent'), null],
    [12, 2, 'absent', -1, condition('F5', 'absent'), 'G3'],
    [13, 2, 'absent', -0.5, condition('F5', 'absent'), 'G3'],
    [14, 2, 'present', -1, condition('F5', 'absent'), null],
  ];
  const board: BoardDocument = {
    ...emptyBoard('B1', 'H5'),
    title: 'ポン出し関連牌の読み',
    question: 'ポン出し関連牌は、どの手牌構造から出たのか',
    classificationAssumption:
      'デモ用仮置きモデル。安手・非聴牌を仮定した比較シナリオ。競合分類の重なりがないと実証したものではない。H3はH4のリャンカン由来を含めない。麻雀理論・頻度は未検証。',
    hypotheses,
    factors,
    effects: effectRows.map(
      ([f, h, state, strength, when, evidenceGroupId], i) => ({
        id: `E${i + 1}`,
        factorId: `F${f}`,
        hypothesisId: `H${h}`,
        strength,
        applicabilityConfidence: f === 13 ? 0.6 : 1,
        activeStates: [state],
        ...(when ? { when } : {}),
        evidenceGroupId,
        sourceRefs: ['S1'],
      }),
    ),
    evidenceGroups: [
      {
        id: 'G1',
        label: '構成自由度不足',
        aggregation: 'maxAbs',
        rationale: '構成余地に関する同根仮定。統計的相関の推定ではない。',
      },
      {
        id: 'G2',
        label: '安手非聴牌の発進選択',
        aggregation: 'maxAbs',
        rationale: '発進動機と代替ルートを同根と仮定。',
      },
      {
        id: 'G3',
        label: '鳴き反応の不在',
        aggregation: 'maxAbs',
        rationale:
          '同一機会の観測なら同根と仮定。異なる機会なら同根とは限らない。',
      },
    ],
    gates: [
      {
        id: 'GT1',
        hypothesisId: 'H2',
        expression: {
          kind: 'any',
          children: [
            condition('F5', 'present'),
            {
              kind: 'all',
              children: [
                condition('F5', 'absent'),
                condition('F3', 'present'),
                condition('F6', 'present'),
              ],
            },
          ],
        },
        mode: 'informational',
        falsePenalty: -1,
        evidenceGroupId: null,
        explanation:
          '聴牌 OR（非聴牌 AND 構成余地 AND 高打点）。説明用の簡略化・必要十分条件の証明ではない。',
      },
      {
        id: 'GT2',
        hypothesisId: 'H4',
        expression: {
          kind: 'any',
          children: [condition('F10', 'present'), condition('F15', 'present')],
        },
        mode: 'informational',
        falsePenalty: -1,
        evidenceGroupId: null,
        explanation: '役牌発進 OR 役牌バック。未検証の説明用条件。',
      },
    ],
    sourceMaterials: [
      {
        id: 'S1',
        label: 'ユーザー原文 · ポン出し関連牌の考察',
        text: originalSource,
      },
    ],
    notes: [],
    decisionMemo:
      '本線と薄い枝を区別しつつ、高打点の見落としを避ける。押し引きの推奨ではない。',
    reflectionMemo:
      '理論・頻度・重みは未検証。原文の「246から2か4切り」は要確認。明確な例は246から2切り→46。',
  };
  const add = (
    id: string,
    owner: string,
    parent: string | null,
    label: string,
    body: string,
  ) => {
    board.notes.push({
      id,
      ownerHypothesisId: owner,
      parentNoteId: parent,
      order: board.notes.length,
      label,
      body,
      sourceRefs: ['S1'],
    });
  };
  add(
    'N1',
    'H1',
    null,
    '関連牌の構成率',
    '近くの対子・雀頭固定を本線に置く仮説。頻度は未検証。',
  );
  add(
    'N2',
    'H2',
    null,
    '聴牌 / 非聴牌',
    '聴牌なら発進の説明が変わる。非聴牌では構成余地・打点・役が重要という仮説。',
  );
  add(
    'N3',
    'H2',
    'N2',
    '構成余地と X が字牌の場合',
    'XXYY334（Yポン）で X/Y の愚形フォローが捨て牌にない仮定。ブロックが狭い、字牌雀頭候補が少ないほど窮屈。',
  );
  add(
    'N4',
    'H2',
    'N2',
    'ドラドラ・赤跨ぎ',
    'X がドラドラ以上、赤含み雀頭、赤跨ぎ両面の3飜以上に注意。手なりの河・手出し回数との関係は未検証。',
  );
  add(
    'N5',
    'H2',
    'N2',
    '安手で別ルートへ移る理由',
    '非聴牌安手なら守備力を残し、チートイ・対々和へ移る仮説。',
  );
  add(
    'N6',
    'H2',
    null,
    '後続観測',
    '手出し、空切りスライド、ドラ反応、ラグ、赤赤否定。手出しがあれば必ず非聴牌とは判定しない。観測不在には機会の確認が必要。',
  );
  add(
    'N7',
    'H2',
    null,
    '役制約 · 役確定 / 未確定',
    '役未確定なら、X以外の役牌暗刻・全体役・X雀頭の3ブロック役などが必要になるという原文の仮説。',
  );
  add(
    'N8',
    'H2',
    'N7',
    '全体役・片アガリ・役牌シャンポン',
    '全体役なら両面の片方のみアガリになるケース。役牌シャンポンを残したいレンジもある。',
  );
  add(
    'N9',
    'H2',
    'N7',
    '形式聴牌と役牌バック',
    '334XX246 で、他で役が確保されている場合の選択。役がない場合の X バックと形式聴牌の例外。数値効果は付けていない。',
  );
  add(
    'N10',
    'H3',
    null,
    'シャンポン→カンチャン固定',
    'ユーザー表現を保持。H4のリャンカン由来を含めない分類。',
  );
  add(
    'N11',
    'H3',
    'N10',
    '2対子 / 3対子とポン材価値',
    '2対子はポン材として安定、3対子は弱くなるという仮説。',
  );
  add(
    'N12',
    'H3',
    'N10',
    'チートイ・対々和への逃げ',
    '今ポンした牌を含めた代替ルートへレンジが逃げる仮説。',
  );
  add(
    'N13',
    'H4',
    null,
    '初副露 / 2副露目',
    'XXYY246 の一向聴、2副露目の窮屈さ。例は246から2切り→46。「2か4切り」は要確認。',
  );
  add(
    'N14',
    'H4',
    'N13',
    '役牌発進 / 非役牌愚形発進',
    '役牌ZZXXYY246からZ発進。68XXYY246から間7発進など。レンジには相手差がある。',
  );
  add(
    'N15',
    'H4',
    'N13',
    '役牌バック・残る例外',
    '非役牌愚形発進では役牌バックなど限定レンジという仮説。例外を消さない。',
  );
  add(
    'N16',
    'H5',
    null,
    '未分類・未知例外',
    '残余枝の存在は真の確率や網羅性を保証しない。',
  );
  add(
    'N17',
    'H5',
    'N16',
    '観測ミス・相手依存のレンジ差',
    '誤観測、観測機会不足、相手ごとの発進レンジ差を保持する。',
  );
  return parseBoard(board);
}
