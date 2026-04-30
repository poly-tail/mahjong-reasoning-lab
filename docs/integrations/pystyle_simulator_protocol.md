# pystyle 何切るシミュレータ通信仕様

この文書は `https://pystyle.info/apps/mahjong-nanikiru-simulator/` の request / response / UI 描画責務を混同しないための実装メモです。  
可視化ツール側の連携コードは [hand_recommendation_service.py](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/app/hand_recommendation_service.py) と [pystyle_simulator_protocol.py](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/app/pystyle_simulator_protocol.py) を参照します。

## 確定事項
- フロントの `calculate()` は JSON を作り、`localhost` なら `http://localhost:50000`、本番相当では `/apps/mahjong-cpp_0.9.1/post.py` に POST する。
- `post.py` 自体は計算本体ではなく、stdin の JSON を受けて `REMOTE_ADDR` を `ip` として追加し、`http://localhost:8888` に転送するだけのプロキシである。
- request payload の主要キーは `enable_reddora` / `enable_uradora` / `enable_shanten_down` / `enable_tegawari` / `enable_riichi` / `round_wind` / `dora_indicators` / `hand` / `melds` / `seat_wind` / `wall` / `version` である。
- `turn` は POST payload には含まれない。巡目は frontend 側の表示・ソート文脈で使われる。
- result 画面は少なくとも `success` / `request` / `response` / `response.config` / `response.shanten` / `response.stats` を前提に描画している。
- `wall` は牌山順ではなく、37種の残存枚数ベクトルである。
- 牌 ID は `0..8=1m..9m` `9..17=1p..9p` `18..26=1s..9s` `27..33=東南西北白發中` `34..36=赤5m,赤5p,赤5s` と高確度で整合する。
- `usedTileCounts` の初期状態は `34種 x 4枚 + 赤3種 x 1枚` で、通常 5m/5p/5s は 3 枚に補正される。
- request 生成時は通常 5 の `wall` スロットへ赤 5 の残存枚数を加算してから送る。`enable_reddora=false` のときは赤 5 スロットを `0` にする。
- meld request には少なくとも `type` / `tiles` / `discardedTile` / `from` が存在する。

## 推定事項
- frontend は巡目ごとの `exp_score` / `win_prob` / `tenpai_prob` 配列を受け取り、現在の巡目インデックスで候補牌の順位を描画している。
- 現在の tool 連携では、`turn` は request payload に入れず、局面から見積もった山残枚数で巡目インデックスを決めている。
- 山残枚数は `70 - 打牌総数 + チー/ポン回数 - 未打牌ターン数 - カン回数` とし、巡目インデックスは `ceil(18 - 山残枚数 / 4)` で求める。
- `melds[].type` の数値 enum は存在するが、今回の範囲では `Pon=0` らしいこと以外は backend 側まで未検証である。

## 未確認事項
- `MeldType` の完全な enum 値と backend 側の正規仕様。
- backend `localhost:8888` が返す response の完全 schema。現在は frontend が参照している subset のみ検証済み。
- frontend が実際に使う巡目ソース。UI の slider / local state / response.config からの導出関係はまだ固定していない。

## 具体例
- 牌姿: `334445m r567p 345s 白白`
- 局情報: `東一局 / 東家 / ドラ表示牌 東`
- request:
  - `round_wind = 27 -> 東`
  - `seat_wind = 27 -> 東家`
  - `dora_indicators = [27] -> 東`
  - `hand = [2,2,3,3,3,4,35,14,15,20,21,22,31,31]`
- wall ベクトルの例:
  - `index 2 (3m) = 2` は 3m を 2 枚使っていることと整合する。
  - `index 3 (4m) = 1` は 4m を 3 枚使っていることと整合する。
  - `index 27 (東) = 3` はドラ表示牌で東を 1 枚使っていることと整合する。
  - `index 31 (白) = 2` は白を 2 枚使っていることと整合する。
  - `index 35 (赤5p) = 0` は赤5p を手牌で使っていることと整合する。
  - `index 4 / 13 / 22` の通常 5 スロットは赤 5 残数が加算済みなので、通常 5 単独の残数とは一致しない場合がある。

## デバッグログ設計
- `request_payload`: POST 直前の JSON。`turn` を絶対に混ぜない。
- `response_body`: HTTP response の生 JSON。`success` / `err_msg` / `request` / `response` をここで分ける。
- `render_context`: frontend 側の表示に使った `turn_index`、その出所、採用した top3 候補。
- `discard_fact.pystyle_top1..3_*`: `AI TOP3` パネルが visible の間に取得できた top3 を、自家打牌の pre-discard hand snapshot と対応づけて保存する列。
- `TODO`: backend 未確認事項をログのメタデータとして明示する。

## 2026-04-10 Addendum
- Frontend request now always forwards current self melds as `melds[]` when they can be represented in simulator tile IDs.
- Request timing no longer depends on raw physical meld tile count. The frontend uses `concealed tile count + effective meld count`, where each meld contributes `3`, to decide whether the hand is at the `14-tile pre-discard` point.
- The visible `AI TOP3` panel keeps pystyle's raw expected-value text. Local `SELF` alert logic is downstream-only and may derive an alert-only EV by applying `0.8` when any current self meld is open.
- Current local alert thresholds are: red `LOW EV` = adjusted EV `< 600`, yellow `EV<800` = raw EV `< 800`, green `HIGH EV` = raw EV `>= 3000`.

## TODO
- 捨て牌、副露、ドラ表示を request 側の `wall` 残枚数にも反映する。
- meld request を GUI 側から渡せるようになったら `melds[]` validator と formatter を拡張する。
- `response.stats[*].extras` に現れる未使用キーを実観測し、必要なら schema を拡張する。
