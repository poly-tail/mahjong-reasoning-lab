# Future Integration

## Purpose

This project owns the knowledge map, case workspace, and a small explainable probabilistic propagation layer.
A separate pruning-ui / probability-tree editor can consume selected subgraphs later.

The boundary is JSON, not direct runtime coupling.

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
- `magnitude` describes effect size
- `confidence` describes confidence in that directional assessment
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

Create a small pruning-ui importer that accepts `pruning-ui.subgraph.v4`, shows `choice_groups`, `locks`, `weights`, `distributions`, `influence_model`, and `reasoning_lab`, then lets the user edit weights before any automatic pruning behavior is added.
