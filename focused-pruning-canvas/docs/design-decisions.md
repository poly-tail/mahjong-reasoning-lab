# 設計判断

- 既存アプリを保全し、このディレクトリを独立したパッケージとして扱う。専用 Storage キーを用いる。
- 利用可能な Node v22.19.0 / npm 11.5.2 と既存 node_modules の実パッケージの engines / peerDependencies を照合し、互換性のある実在バージョンを固定。選択した正確なバージョンは package.json と lockfile が正本。既存アプリの依存は変更しない。
- 通常 CSS とシステムフォント。React Flow は表示モデルのみ。説明 Note はスコアに入れない。
- 純粋な評価器と境界検証、単一 command 経路、snapshot/cursor を採用。ID と時刻は application で注入。
- 保存は同期 Result port。UI は Storage 実体を取得しない。デバウンスせず確定操作一回に一保存。
- 任意条件木 GUI は作らず、プリセットと読み取り可能な三値評価木、厳密な import を用いる。
- 次版候補と非対象は spec.md 第16節が正本。既存4軸は将来の影響先であり、本試作に評価器は持たせない。

## 実装上の具体化

- App は約220行だが、画面の組立・選択・確認ダイアログとペイン切替が責務。計算・履歴・保存・各編集フォームは外部へ分離した。store は約220行、主要画面部品は約320行以下。
- CSSもbase / layout / canvas / inspector / tokensに分け、app.cssはimport入口にした。
- 要素配列の文書順をレーン順として使用し、Noteだけorderと親を持つ。配分が変わってもソートしない。
- 同根mean/maxAbsの異符号検証は、その時点の有効候補を仮説別に集計して行う。未適用は分母に含めない。
- 説明上位3件はscore単位に揃えてdomainで並べ、画面とMarkdownが同じ規則を使用する。
- 根拠信頼度と適用信頼度を併せて下げるフォーム操作では、理由を説明Noteとして同じコマンドで残す。
- 通常のJSON exportは整形するが5MiBを超える場合は同じ内容をcompactにする。Markdown埋込JSONは常にcompact。どちらも内容を削らない。
- 原文の全角空白・表記はcode blockとseed文字列で保全し、改行コード差を除いた一致をunit testで確認する。

## 依存の確認

既存の実パッケージから React 19.2.5 / React DOM 19.2.5、TypeScript 6.0.3、Vite 8.0.10、Zustand 5.0.13、Zod 4.4.3、@xyflow/react 12.10.2、Vitest 4.1.5、Playwright 1.59.1 を確認し固定した。ESLint 10.3.0、typescript-eslint 8.59.2 はTypeScript 6.0を許容するpeer条件を確認済み。Nodeの互換範囲は主要依存の共通部分に合わせた。

ネットワークのオフライン設定は変更せず、利用可能な親のnode_modulesを使って検証した。既存lockのpackage情報を基に本パッケージのroot metadataを新設し、npmのoffline package-lock-only処理で不要な依存を整理した。独立環境ではREADMEに記載のnpm ciを使用する。
