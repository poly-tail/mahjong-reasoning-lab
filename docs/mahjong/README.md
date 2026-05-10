# 麻雀ドメイン文書

このフォルダは、麻雀そのもののルール、判断理論、実装ロジック、研究メモをまとめる親フォルダです。UI 仕様、外部連携、DB スキーマの正本はここに置かず、それぞれ `docs/screen_specs/`、`docs/integrations/`、`docs/reference/` に置きます。

## 棲み分け

- [theory/](theory/README.md): 牌効率・手組み・鳴き効率など、学習用に体系化したセオリー。
- [logic/](logic/README.md): このツールの判定・推定ロジックとして実装に接続する麻雀ロジック。
- [reference/](reference/README.md): 麻雀ルール、鳴き可否、手牌分析用語など、基礎参照。
- [research/](research/README.md): 会話ログ由来の研究整理、v7/v8 研究ノート、ベタオリ・読み・ポーカー転用メモ。

## 使い分けの基準

- 「人間が牌効率を学ぶ」ための内容は `theory/`。
- 「コードが何を判定するか」の正本は `logic/`。
- 「前提ルールや用語の定義」は `reference/`。
- 「まだ実装正本ではない仮説、研究、長い整理メモ」は `research/`。

## 主要導線

- 牌効率を学ぶ: [theory/README.md](theory/README.md)
- 実戦判断フローを見る: [theory/decision-flow.md](theory/decision-flow.md)
- 危険度ロジックを見る: [logic/mahjong_danger.md](logic/mahjong_danger.md)
- シャンテン・待ち牌ロジックを見る: [logic/hand_analysis.md](logic/hand_analysis.md)
- 鳴き可否とラグ判定を見る: [reference/mahjong_call_rules.md](reference/mahjong_call_rules.md)
- 研究メモの全体像を見る: [research/README.md](research/README.md)

## 配置ルール

新しい文書を追加するときは、まず「学習セオリー」「実装ロジック」「基礎参照」「研究メモ」のどれかを決めます。複数にまたがる場合は、正本を 1 つに決め、他フォルダからはリンクで参照します。
