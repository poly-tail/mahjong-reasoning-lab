# Schema

更新日: 2026-07-26

The schema source of truth is `src/domain/schema.ts`.
All persisted and exported JSON has an explicit `schema_version`.

## Workspace

Version: `mahjong-knowledge-map.workspace.v4`

`mahjong-knowledge-map.workspace.v1`、`v2`、`v3` can be normalized into v4 when loaded. New probability, influence, and Reasoning Lab fields default to non-propagating or empty values.

Top-level fields:

- `schema_version`
- `projects`
- `sheets`
- `active_project_id`
- `active_sheet_id`
- `global_settings`
- `nodes`
- `edges`
- `cases`
- `rules`
- `saved_views`
- `pruning_actions`
- `impact_summaries`
- `reading_utilities`
- `reading_chains`
- `averaging_safety`
- `teaching_logs`
- `active_case_id`
- `updated_at`

Project / Sheet fields are additive defaults inside workspace v4. A v4 document without them is normalized into Default Project / Default Sheet before use.

`scopeMode` is not a top-level field. It is transient Zustand UI state with values `sheet` / `project` / `workspace`.

## Project

Fields:

- `id`
- `title`
- `description`
- `tags`
- `created_at`
- `updated_at`
- `default_sheet_template_options`
- `sheet_ids`
- `archived`

`default_sheet_template_options` has four booleans:

- `tile_efficiency`
- `tile_count`
- `yaku`
- `abstract_reading`

## Sheet

Fields:

- `id`
- `project_id`
- `title`
- `description`
- `tags`
- `created_at`
- `updated_at`
- `node_ids`
- `edge_ids`
- `case_ids`
- `rule_ids`
- `saved_view_ids`
- `reading_drawer_item_ids`
- `exception_node_ids`
- `residual_group_ids`
- `template_source`
- `archived`

The content records remain in the workspace top-level arrays. Sheet arrays are membership indexes; they do not embed copies of nodes, edges, cases, rules, or saved views.

`template_source` is optional and contains:

- `created_from_template`
- `enabled_template_keys`

`enabled_template_keys` uses the same four template keys as `default_sheet_template_options`. It is used to keep normal template application idempotent.

## Global Settings

Fields:

- `project_creation_defaults`
- `sheet_creation_defaults`
- `create_empty_project_by_default`
- `create_empty_sheet_by_default`

Both defaults objects use the four template booleans. All four templates default to `true`; empty creation defaults to `false`.

## Scope Normalization

`normalizeWorkspaceScopes()` guarantees:

- at least one Project and one Sheet when existing content needs a scope
- valid `project_id` references for Sheets
- valid active Project / Sheet ids
- Project `sheet_ids` synchronized with actual Sheets
- orphan node / edge / case / rule / saved view ids assigned to the active or first Sheet

The normalizer does not embed Project / Sheet ownership directly into each content record. Membership remains on Sheet.

## Knowledge Node

Required MVP fields:

- `id`
- `type`
- `title`
- `summary`
- `description`
- `tags`
- `confidence`
- `applicability`
- `stage`
- `actor`
- `source_type`
- `reproducibility`
- `notes`
- `formulas`
- `thresholds`
- `related_rule_ids`
- `created_at`
- `updated_at`

Added MVP fields:

- `position`: React Flow canvas position
- `group_id`: parent section id
- `is_group`: section/group marker
- `collapsed`: hide direct children in Knowledge Map
- `pruning_hints`: future pruning-ui handoff hints
- `reading_utility_ids`: optional links to utility records

Node types:

- `concept`
- `signal`
- `condition`
- `metric`
- `heuristic`
- `exception`
- `scenario`
- `action`
- `evidence`
- `question`
- `hypothesis`
- `branch`
- `choice_group`
- `observation`
- `weight_modifier`
- `lock_controller`
- `distribution_assumption`
- `probability_aggregate`
- `observation_candidate`
- `ambiguity_marker`
- `pruning_suggestion`
- `weight_adjustment_suggestion`

Probability fields:

- `probability_role`: `none` | `prior` | `posterior` | `control`
- `choice_group_id`
- `concentration_group_id`
- `base_weight`
- `dynamic_weight`
- `posterior_probability`
- `prior_probability`
- `lock_mode`: `none` | `hard` | `soft` | `keep_top_k` | `freeze_ratio` | `hard_lock` | `soft_lock` | `freeze_concentration_band`
- `lock_value`
- `lock_rationale`
- `distribution_family`: `categorical` | `interval` | `bimodal` | `multimodal` | `asymmetric_tail` | `mixture`
- `propagation_policy`: `none` | `normalize_siblings` | `multiply_downstream` | `gated`
- `hysteresis_band`
- `pruning_priority`
- `resolves_targets`
- `expected_sign_gain`
- `expected_weight_gain`
- `expected_margin_gain`
- `pruning_safety_change`
- `observation_cost`
- `timeliness`

Residual mass is represented without a workspace version bump:

- unknown buffer nodes use `type: ambiguity_marker`
- exception candidates use `type: exception`
- tags include `residual_mass`, `unknown_buffer`, `exception`, or `reading_drawer`
- `pruning_hints` can include `must_keep_top_k` to prevent unsafe hard prune

Which nodes hold probability:

- Usually yes: `hypothesis`, `branch`, scenario branches, explicit `observation` inputs, aggregates, and weight/lock control nodes.
- Usually no: `concept`, `signal`, `evidence`, `question`, general notes, and semantic-only rule design nodes.
- `choice_group` normally uses `probability_role: control`; the member candidates hold posterior values.

## Reading Utility residual fields

`reading_utilities` includes the original utility metrics plus defaulted residual fields. Old v4 workspace JSON without these fields is still valid because zod supplies defaults.

- `residual_mass_before`
- `residual_mass_after`
- `residual_reduction`
- `exception_candidates_added`
- `unknown_buffer_remaining`

## Knowledge Edge

Fields:

- `id`
- `source`
- `target`
- `type`
- `label`
- `notes`
- `created_at`
- `updated_at`

Probability and influence edge fields:

- `relation_layer`: `semantic` | `probabilistic` | `influence`
- `conditional_weight`
- `transition_rule`
- `propagate_probability`
- `edge_group_id`
- `sign`: `+` | `-` | `mixed` | `unknown`
- `magnitude`: UI上は「影響ウェイト」。0〜1で保存し、表示は0〜100スコア。
- `confidence`: influence edgeでは「軸確信度」。0〜1で保存し、表示は0〜100スコア。
- `context_gate`
- `combination_mode`: `additive` | `multiplicative` | `override`
- `ambiguity_group_id`
- `evidence_refs`
- `note`

Semantic edges explain knowledge relations. Probabilistic edges are the only edges used by the propagation engine.
Influence edges explain directional effect on a target metric. Directionality is edge-based, not node-based.
`mixed` means the direction is split by context; `unknown` means it cannot be evaluated yet.

Edge types:

- `supports`
- `contradicts`
- `refines`
- `triggers`
- `overrides`
- `applies_to`
- `measured_by`
- `exported_as`
- `influences`
- `resolves`
- `weakens`
- `strengthens`
- `disambiguates`
- `blocks_pruning`
- `enables_pruning`

## Case Data

Required MVP fields:

- `id`
- `title`
- `round`
- `honba`
- `riichi_sticks`
- `turn`
- `scores`
- `dealer`
- `seat`
- `observations`
- `hypotheses`
- `attached_node_ids`
- `selected_rule_ids`
- `decision_note`
- `review_note`
- `created_at`
- `updated_at`

Added MVP fields:

- `riichi_status`
- `melds_summary`
- `discard_notes`
- `lane_assignments`
- `top_k_hypotheses`

`lane_assignments` maps attached node ids to one of:

- `observation`
- `hypothesis`
- `condition`
- `decision`

Decision Pipeline mode does not add schema fields. It derives collect, weight, combine, compare, choose, and review columns from attached nodes, node type, tags, influence edges, and lane assignments.

## Domain Taxonomy Tags

Mahjong-specific taxonomy is stored as tags and lens presets, not as new schema enums.

Examples:

- `hand_value_range`
- `progress_tenpai_axis`
- `value_axis`
- `wait_shape_quality_axis`
- `score_situation_threshold_axis`
- `speed_axis`
- `shape_axis`
- `push_fold`
- `danger_tile`
- `probability_tree`
- `pruning`
- `node_lock`
- `rescue_rate`
- `rank_ev`
- `teaching`
- `review`

`speed_axis`, `shape_axis`, `rank_ev`, `score_context`, and `external_modifier` remain valid alias tags for imported v4 workspaces. New UI labels map hand value work to the canonical four axes: `progress_tenpai_axis`, `value_axis`, `wait_shape_quality_axis`, and `score_situation_threshold_axis`.

Score and threshold factors such as `turn`, `dealer`, `score_context`, `dora`, `honba`, `riichi_sticks`, and `rank_point` are represented as tags under `score_situation_threshold_axis`.

## Rule Definition

Fields:

- `id`
- `name`
- `category`
- `target_node_ids`
- `hard_gates`
- `soft_score_terms`
- `override_conditions`
- `fallback_behavior`
- `note`
- `created_at`
- `updated_at`

Rule categories:

- `hard_gate`
- `soft_score`
- `override`
- `fallback`
- `mixed`

`soft_score_terms` uses:

- `id`
- `label`
- `weight`
- `note`

## Saved View

Fields:

- `id`
- `name`
- `search`
- `tag_filter`
- `node_type_filter`
- `created_at`

## Reasoning Lab Schemas

`concentration_metrics`:

- `entropy`
- `top_k_mass`
- `peak_mass`
- `hhi`
- `dispersion_note`

`pruning_action`:

- `id`
- `action_type`: `hard_prune` | `soft_downweight` | `hard_lock` | `soft_lock` | `keep_top_k` | `freeze_ratio` | `freeze_concentration_band`
- `target_ids`
- `strength`
- `rationale`
- `created_at`

`impact_summary`:

- `before_snapshot_id`
- `after_snapshot_id`
- `delta_mass`
- `changed_node_count`
- `dominant_branch_change`
- `ambiguity_change`
- `margin_change`
- `vector_delta_by_metric`
- `notes`

`reading_utility`:

- `target_id`
- `selective_pruning_ratio`
- `global_impact_score`
- `concentration_shift`
- `ambiguity_reduction`
- `resolution_gain`
- `projected_margin_gain`
- `cost_estimate`
- `utility_score`

`reading_chain`:

- `id`
- `case_id`
- `steps`
- `summary`
- `created_at`
- `updated_at`

`reading_chain_step`:

- `id`
- `step_type`: `observation` | `hypothesis_split` | `lock` | `pruning` | `weight_update` | `direction_update` | `observation_request` | `fallback` | `compare`
- `source_ids`
- `target_ids`
- `before_snapshot_id`
- `after_snapshot_id`
- `rationale`
- `note`

`averaging_safety`:

- `target_id`
- `score`
- `label`: `safe` | `caution` | `unsafe`
- `reasons`

`teaching_log`:

- `case_id`
- `action_id`
- `explanation_short`
- `explanation_full`
- `key_terms`
- `created_at`

## Pruning Export

Version: `pruning-ui.subgraph.v4`

Fields:

- `schema_version`
- `exported_at`
- `source_workspace_schema_version`
- `selected_nodes`
- `selected_edges`
- `node_metadata`
- `rules`
- `pruning_hints`
- `weight_placeholders`
- `inference_subgraph`
- `choice_groups`
- `locks`
- `weights`
- `distributions`
- `propagation_order`
- `frozen_nodes`
- `top_k_constraints`
- `reasoning_lab`
- `influence_model`

`selected_nodes` includes explicitly selected nodes plus endpoints of explicitly selected edges.

`selected_edges` includes explicitly selected edges and edges whose source/target are both selected.

`rules` includes rules whose `target_node_ids` overlap selected nodes, plus rules referenced by selected node metadata.

Pruning hints:

- `can_prune`
- `must_keep_top_k`
- `hard_gate_candidate`
- `score_only`
- `override_only`

`weight_placeholders` are not learned weights. They are initial editable values derived from node confidence.

`inference_subgraph` includes only probability-bearing nodes and probabilistic edges from the selected subgraph.

`choice_groups` are derived from `choice_group_id` membership and include local normalized totals.

`locks`, `weights`, and `distributions` are direct handoff records for pruning-ui.

`propagation_order` is the MVP topological order for DAG-style propagation.

`frozen_nodes` contains hard-lock and freeze-ratio nodes.

`top_k_constraints` maps choice group ids to retained k values.

`influence_model` includes metrics, influence edges, ambiguity groups, observation candidates, and pruning/weight adjustment suggestions derived from signed influence.

`reasoning_lab` includes concentration metrics, pruning action logs, impact summaries, reading utilities, reading chains, averaging safety estimates, and teaching logs.

## Compatibility Policy

For the current MVP, import accepts `mahjong-knowledge-map.workspace.v4` and normalizes v1/v2/v3.

Workspace v4 allows additive fields with zod defaults. This is how Project / Sheet / Global Settings remain compatible with older v4 documents.

A change that removes fields, changes field meaning, or cannot be reconstructed with a default must introduce a new version string and an explicit migration.

All IndexedDB loads, workspace imports, and exports pass through zod validation and scope normalization.
