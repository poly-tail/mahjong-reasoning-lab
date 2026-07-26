# Future Integration

更新日: 2026-07-26

## Purpose

This project owns the knowledge map, case workspace, and a small explainable probabilistic propagation layer.
A separate pruning-ui / probability-tree editor can consume selected subgraphs later.

The boundary is JSON, not direct runtime coupling.

## Current UI Integration Boundary

The current Candidate Tree is a scoped projection over the existing graph. It selects a branch, selects a `PruningActionType` label, and shows warnings. It does not dispatch workspace mutations from the tree's `反映前確認`, `反映する`, `元に戻す`, residual destination, exception destination, or drawer buttons.

Persistent operations currently remain in:

- Probability Workbench detailed editor
- propagation preview apply
- Reasoning Lab pruning and lock records

The Residual Mass panel also exposes active Sheet / Project / Global / unknown destination choices as local UI state. Those choices are not passed to the add or keep-unknown handlers. Created records continue to use active Sheet membership.

Future integration must reuse store/domain actions rather than adding a second mutation path inside the presentation components. Candidate Tree preview should be generated from the same domain operation that will later be applied.

## Export Contract

Current export version:

```text
pruning-ui.subgraph.v4
```

Export includes:

- selected nodes
- selected edges
- node metadata
- rules related to selected nodes
- pruning hints
- weight placeholders
- inference subgraph
- choice groups
- locks
- weights
- distributions
- propagation order
- frozen nodes
- top-k constraints
- influence model
- reasoning lab metrics and logs
- schema version

The export is produced by `createPruningSubgraphExport()` in `src/domain/export.ts`.

## Intended pruning-ui Mapping

| Knowledge Mapper field      | pruning-ui use                                                    |
| --------------------------- | ----------------------------------------------------------------- |
| `selected_nodes`            | source nodes and explanatory metadata                             |
| `selected_edges`            | source relations and provenance                                   |
| `rules.hard_gates`          | hard pruning branches                                             |
| `rules.soft_score_terms`    | weighted scoring terms                                            |
| `rules.override_conditions` | exception layer                                                   |
| `rules.fallback_behavior`   | default policy when branches conflict                             |
| `pruning_hints`             | editor hints for UI grouping                                      |
| `weight_placeholders`       | initial editable weights                                          |
| `inference_subgraph`        | probability-bearing nodes and probabilistic edges only            |
| `choice_groups`             | exclusive candidate groups for normalization                      |
| `locks`                     | hard/soft/top-k/freeze instructions                               |
| `weights`                   | prior/posterior/base/dynamic handoff                              |
| `distributions`             | distribution assumptions and pruning priority                     |
| `propagation_order`         | MVP DAG order for previewable propagation                         |
| `frozen_nodes`              | nodes that should not be freely renormalized                      |
| `top_k_constraints`         | choice-group retention constraints                                |
| `influence_model`           | signed metric effects, ambiguity, observation and pruning support |
| `reasoning_lab`             | concentration, impact, utility, lock safety, chain, teaching data |

## Semantic vs Probabilistic Import

pruning-ui should not import the full semantic graph as an inference model.

Semantic graph data is useful for:

- explanations
- notes
- source context
- rule rationale
- review UI

Probabilistic graph data is useful for:

- weighted candidate management
- choice-group normalization
- downstream probability multiplication
- lock-aware pruning
- distribution-aware visual controls

The current export separates these by `relation_layer` and `probability_role`.

## Directional Influence Handoff

Directional influence is not stored on nodes. It is stored on `source -> target metric` edges.

- `sign` describes direction: `+`, `-`, `mixed`, `unknown`
- `magnitude` is the internal 0-1 field for UI "影響ウェイト" and is displayed as a 0-100 score
- `confidence` is the internal 0-1 field for UI "軸確信度" and is displayed as a 0-100 score
- `context_gate` describes when the direction applies
- `combination_mode` describes how multiple influences compose

`mixed` and `unknown` must not be merged:

- `mixed`: direction is split by context
- `unknown`: direction is not evaluable yet

pruning-ui should block or warn on pruning when unresolved ambiguity is high. If pruning is unsafe but the branch is still weak, importers can use weight adjustment suggestions instead.

Observation candidates indicate which additional observation is expected to reduce sign ambiguity, with expected gain/cost values for planning.

## Hard Gate / Soft Score / Override / Fallback

The knowledge map keeps these categories separate because future pruning interfaces should not collapse every decision into a single `if` chain.

- Hard gate removes candidates or branches.
- Soft score ranks candidates without removing them.
- Override can supersede a general rule.
- Fallback handles uncertainty, missing information, or rule conflict.

## Top-k Hypotheses

Top-k is represented in three places:

- Knowledge nodes can carry `must_keep_top_k`.
- Cases have `top_k_hypotheses`.
- Probability nodes can use `lock_mode: keep_top_k` and `lock_value: k`.

Future pruning-ui can treat these as instructions to retain multiple candidate hypotheses even when one has the highest score.

## Reasoning Lab Handoff

`reasoning_lab` contains:

- `concentration_metrics`: where probability mass is concentrated
- `pruning_actions`: simulated or saved prune/downweight/lock operations
- `impact_summaries`: before/after delta records
- `reading_utilities`: utility score and rationale components for readings/observations
- `reading_chains`: replayable multi-step reading timelines
- `averaging_safety`: safe/caution/unsafe estimates for approximation
- `teaching_logs`: explanation records for training and review

pruning-ui should treat these as explainability and review inputs, not as irreversible automatic pruning commands.

## Propagation Constraints

The MVP propagation engine supports:

- choice-group local normalization
- hard lock sibling redistribution
- soft lock minimum retention
- keep-top-k collapse
- freeze-ratio stabilization
- simple gate prune
- DAG-style downstream multiplication

It does not support:

- general cyclic probabilistic graph inference
- full Bayesian network semantics
- continuous distribution fitting
- formula DSL parsing
- hidden-state learning

## Future Issue: Cross-view Reallocation To Unexpanded And Exception Mass

Current Phase1 keeps tile-efficiency readings, tile-count readings, yaku readings, and abstract readings as separate candidate trees with separate 100% spaces. Their input probabilities, residual probabilities, exception candidates, unknown buffers, and four-axis influence scores must not be merged automatically.

Future pruning-ui / probability-tree editors may introduce cross-view correction. A reading in one view can strongly change the candidate distribution in another view. For example, an abstract reading can make yaku A thinner and yaku B denser. Even then, the probability mass removed from yaku A should not always be redistributed fully to existing yaku B.

When existing candidates have weak explanatory power, only a few strong candidates exist, unresolved `mixed` / `unknown` remains, partial tile-pattern matching is insufficient, the abstract reading is strong but concrete tile-efficiency or yaku candidates are still undefined, or low-frequency high-loss exceptions should be retained, future tools may need to increase the mass of `未展開の枝`, `例外の枝置き場`, or `未知バッファ`.

This is not implemented in Phase1. Phase1 must not automatically increase or decrease unexpanded or exception probability via cross-view correction. It must not overwrite input probabilities with cross-corrected distributions. It must not cut existing candidates aggressively from abstract readings alone. It must not treat cross-view integration as a fixed result without tile-pattern validation. Four-axis influence scores are not candidate probabilities and must not be mixed into a 100% candidate-probability space.

Future design work should consider:

- A mechanism to increase or decrease unexpanded, exception, and unknown-buffer mass after cross-view correction.
- UI choice between redistributing mass to existing candidates and returning it to unexpanded or exception branches.
- Reallocation rules based on candidate count, explanatory power, axis confidence, unresolved `mixed` / `unknown`, and residual rate.
- A preview that distinguishes "move candidate A's lost mass to candidate B" from "return candidate A's lost mass to unexpanded or exception mass".
- Confidence per cross-view correction rule and an impact log for the integrated distribution.
- Validation through partial tile-pattern matching.
- Separate display of input probability, tile-count-adjusted weight, cross-corrected weight, computation probability, and unexpanded/exception probability.

## Open Design Questions

- Should pruning-ui import be append-only or replace the current probability tree?
- Should node ids remain stable across projects, or should import assign project-local ids with a source id map?
- How should conflicting `overrides` edges be ordered when multiple exceptions fire?
- Should soft score weights be normalized inside this project or only inside pruning-ui?
- How should confidence and reproducibility affect pruning thresholds?

## Non-goals For This Repo

- Real-time Tenhou/Majsoul connection
- Full hand parser and automatic reading engine
- General cyclic probabilistic inference engine
- Multi-user collaboration
- Cloud sync

## Suggested Next Step

Before adding automatic pruning behavior:

1. Connect Candidate Tree preview to the existing probability / Reasoning Lab domain operations.
2. Connect apply and undo to the same Zustand history path used by other workspace mutations.
3. Pass residual destination scope into domain actions and persist active Sheet / Project / Global ownership explicitly.
4. Add tests proving that preview is non-mutating and apply changes only the intended scoped records.
5. Keep hard-prune warnings blocking or explicit when residual, mixed / unknown, low-confidence, or fixed branches remain.

After that boundary is stable, create a small pruning-ui importer that accepts `pruning-ui.subgraph.v4`, shows `choice_groups`, `locks`, `weights`, `distributions`, `influence_model`, and `reasoning_lab`, then lets the user edit weights before any automatic pruning behavior is added.
