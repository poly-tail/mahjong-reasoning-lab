# 要件定義 現行版

> 現行版ファイル: `requirements_v2.1.md`

## 現行版

- 版: `v2.1`
- 更新日: `2026-05-10`
- 継承元: `old/requirements_v2.0.md`

## 現在の重点

- 実見え枚数 / 推測見え枚数 / 合わせ打ち の責務を分離する
- `AI TOP3`, `SELF`, 相手パネル、状況表の表示整合を保つ
- プレイヤーパネルの `STATUS` から Nodocchi 鳳凰卓4人打ち成績を確認できるようにする
- 外部成績取得は UI スレッドを止めず、失敗時も外部リンク fallback を残す
- 麻雀ドメイン文書は `docs/mahjong/theory|logic|reference|research` に分けて保守する
- 自家の `2見え以下字牌` 一覧は自河から自副露帯へ視線を流しやすい位置に置く
- ドキュメントグラフ再生成とワークスペース ZIP 化を他環境でも再実行できるようにする

## 関連文書

- 要件本文: [requirements_v2.1.md](./requirements_v2.1.md)
- 仕様書 現行版: [../specs/current.md](../specs/current.md)
- 画面仕様書 現行版: [../screen_specs/current.md](../screen_specs/current.md)
- プロジェクトガイド: [../architecture/project_guide.md](../architecture/project_guide.md)
- Nodocchi 成績連携: [../integrations/nodocchi_status.md](../integrations/nodocchi_status.md)
