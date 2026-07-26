# Architecture

更新日: 2026-07-26

## Goal

Mahjong Reasoning Lab is a local-first web app for structuring mahjong reading knowledge, organizing it by Project / Sheet, and projecting it onto concrete cases.
It intentionally stops before full automatic inference.

## Boundaries

```text
src/app
  AppShell, navigation, manual save/autosave lifecycle, Zustand store

src/domain
  zod schemas, Project / Sheet scope, template catalog, seed data, labels, taxonomy, mapping templates, residual-mass helpers, JSON export transformation, propagation engine, influence analysis, Reasoning Lab calculations

src/infrastructure
  IndexedDB persistence and browser file I/O

src/ui
  Feature screens and small shadcn-like UI primitives
```

The domain layer does not import React. This keeps the JSON schemas and future pruning-ui export reusable outside the current web app.

## Data Flow

1. `AppShell` loads a workspace document from IndexedDB via Dexie.
2. If no local document exists, `seedWorkspace` is used.
3. `normalizeWorkspaceDocument()` validates v1〜v4 input and `normalizeWorkspaceScopes()` guarantees a valid Project / Sheet structure.
4. Project / Sheetがないworkspace v4はDefault Project / Default Sheetへ移行し、未所属のnode / edge / case / rule / saved viewをactive Sheetへ割り当てる。
5. UI screens mutate the Zustand store through typed actions.
6. Store mutations validate the document shape with zod and push undo history where appropriate.
7. Project / Sheet作成時は `src/domain/templateCatalog.ts` が選択テンプレートをidempotentにactive Sheetへ適用する。
8. `scopeMode` は `src/domain/projectSheets.ts` を通じてSheet / Project / Workspaceの表示集合を作る。これは永続documentではなくUI stateである。
9. `AppShell` saves the document to IndexedDB on Ctrl+S or the save button, and also runs configurable interval autosave every 5 minutes by default.
10. JSON import/export uses `src/domain/export.ts`. Workspace exportはProject / Sheet / Global Settingsを含み、subgraph exportは選択範囲またはscope集合から作る。
11. Probability preview uses `src/domain/probability.ts` and only mutates the document after the user applies the preview.
12. Candidate Tree projects the scoped inference graph through `CandidateTreeView`; current tree buttons select an operation and show warnings but do not mutate the workspace.
13. Directional influence views use `src/domain/influence.ts`; influence sign is never read from a node.
14. Mapping Inbox uses `src/domain/mappingTemplates.ts` to create schema-compatible draft nodes from user-selected templates.
15. Domain Lens uses `src/domain/mahjongTaxonomy.ts` to filter the Knowledge Map without changing schema enums.
16. Reasoning Lab uses `src/domain/reasoningLab.ts` to create concentration metrics, pruning simulations, reading utility scores, lock safety estimates, chain replay diffs, and teaching logs.

## Screens

### App Shell and Workspace Scope

`AppShell` owns the six purpose-oriented top-level routes:

- case
- theory
- probability
- validation
- teaching
- data

The shell also owns Project / Sheet selectors, creation modals, Global Settings, scope buttons, undo / redo, manual save, autosave interval, and save status.

Changing the active Project chooses a Sheet in that Project and its first case. Changing the active Sheet updates the active Project and case. Both clear graph selection.

`WorkspaceScopeMode` is `sheet` / `project` / `workspace`. `getScopedWorkspace()` filters nodes, edges, cases, rules, and saved views. An edge is visible only when its id belongs to the scope and both endpoints remain visible.

### Knowledge Map

React Flow renders the graph. The app stores canonical node positions in `KnowledgeNode.position`.

Selection is synchronized as node/edge ids only. React Flow owns its internal visual selection state to avoid update loops.

Knowledge Map is the broad semantic editing surface. It can contain concepts, notes, questions, evidence, and inference nodes, but the full graph is not passed into the propagation engine.

Group support is MVP-level:

- A group is a normal `concept` node with `is_group: true`.
- Child nodes point to it through `group_id`.
- Collapse hides direct children while keeping the group node visible.

Knowledge Map receives the scoped workspace. New nodes, edges, cases, rules, and saved views are associated with the active Sheet through store actions.

### Case Workspace

Cases attach knowledge nodes by id. Each attached node can be assigned to one lane:

- observation
- hypothesis
- condition
- decision

Simple candidate suggestions are based on title/tag text matching and edge proximity to already attached nodes. This is not an inference engine.

Decision Pipeline mode is a derived view over the same attached nodes. It maps nodes to collect, weight, combine, compare, choose, and review columns by node type, tags, lane assignment, and influence edges. It does not add new case lanes to the schema.

Cases from the active Sheet are ordered first. Knowledge candidates receive a scope bonus in this order: active Sheet, active Project, Workspace.

Residual scope destination buttons are currently local panel state. They do not pass a destination into the add/keep handlers; created records continue to use the active Sheet.

### Mapping Inbox and Theory Lenses

Mapping Inbox is a manual structuring aid. It does not call an LLM and does not parse mahjong text automatically. The selected template creates draft nodes using existing fields such as tags, probability role, pruning hints, lock mode, formulas, thresholds, and distribution family.

Hand Value Range Lens and Rescue Rate Lens are UI lenses over existing node/edge fields. They use taxonomy tags and influence edges rather than schema enum expansion.

`mappingTemplates.ts` structures pasted notes. `templateCatalog.ts` seeds a new Project / Sheet with the four catalog keys `tile_efficiency`, `tile_count`, `yaku`, and `abstract_reading`. These are separate responsibilities.

### Rule Builder Lite

Rules are form-based records. The UI intentionally separates:

- Hard gate
- Soft score
- Override
- Fallback

This mirrors the future pruning-ui handoff without implementing a full visual condition tree editor.

### Probabilistic Propagation Layer

The probabilistic layer is separate from the semantic knowledge graph.

Semantic graph:

- owns concepts, notes, sources, explanations, and general relations
- default node role is `probability_role: none`
- default edge layer is `relation_layer: semantic`
- is not automatically normalized or propagated

Probabilistic inference layer:

- contains nodes where `probability_role` is `prior`, `posterior`, or `control`
- contains edges where `relation_layer` is `probabilistic` or `propagate_probability` is true
- is treated as an inference subgraph
- supports choice-group normalization and a DAG-style downstream multiplication pass

The MVP propagation order is:

1. observation update
2. gate prune
3. weight modifier apply
4. lock apply
5. sibling normalization
6. downstream propagation
7. hysteresis / keep-top-k adjust

The engine does not solve general cyclic probabilistic graphs. If a probabilistic cycle is found, the preview emits a warning and falls back to document order.

Choice groups are represented by shared `choice_group_id` values on candidate nodes. The `choice_group` node type is a control/label node, not the only source of group membership.

Lock behavior:

- hard lock fixes a candidate probability and redistributes siblings
- soft lock enforces a minimum retained probability
- keep top-k collapses lower-ranked siblings after propagation
- freeze ratio blends the computed posterior with the previous posterior

Pruning and lock are kept separate in the UI. Pruning removes or weakens candidates; lock fixes a distribution or ratio while keeping candidates visible. A hard prune sets the target probability mass to zero for the simulation, but it is not presented as a node-lock operation.

### Candidate Tree Projection

Candidate Tree is the default view inside Probability Workbench. It projects the scoped inference subgraph, residual groups, exceptions, and template branches into a tree-shaped presentation without changing the graph schema.

The current tree surface supports branch selection, operation-label selection, and warnings for mixed / unknown influence, residual branches, keep-top-k, fixed branches, and low confidence.

The tree surface does not dispatch workspace mutations from its `反映前確認`, `反映する`, `元に戻す`, residual destination, exception destination, or drawer buttons. Persistent probability updates remain in the detailed Probability editor and Reasoning Lab.

This boundary prevents documentation from treating visible scaffold controls as completed mutation workflows.

### Directional Influence Layer

Directional influence is a third layer alongside semantic and probabilistic data.

Core rules:

- directionality is edge-based, not node-based
- influence edges use `relation_layer: influence`
- edge `sign` is one of `+`, `-`, `mixed`, `unknown`
- the same source node may influence different metrics in different directions
- the same source/metric pair may have multiple context-gated edges

`mixed` and `unknown` are intentionally different:

- `mixed` means direction is split by context and should not be collapsed
- `unknown` means the direction is not evaluable yet

Pruning safety uses:

- directional dominance
- edge confidence
- unresolved ambiguity
- top-k keep constraints

If unresolved ambiguity is high, the UI blocks or warns against pruning and recommends observation or downweighting instead.

### Reasoning Lab Layer

Reasoning Lab is a derived analysis layer on top of the existing graph layers. It does not replace Knowledge Map, Probability, or Influence screens.

It adds:

- Concentration Lens: entropy, top-k mass, peak mass, HHI
- Pruning Impact Simulator: before/after distribution and impact summaries
- Lock Analysis: hard/soft/top-k/freeze controls plus averaging safety
- Reading Utility Evaluator: selective pruning, global impact, ambiguity reduction, margin gain, cost
- Reading Chain Timeline: replayable multi-step reading sequences
- Educational Explanation Panel: teaching logs tied to action diffs

The layer keeps snapshot/diff records rather than silently mutating every result. Important operations can be saved as `pruning_actions` and `impact_summaries`.

MVP constraints still apply:

- choice-group tree + DAG subset only
- no general cyclic probability graph solution
- no full Bayesian network semantics
- no automatic mahjong inference engine

## Persistence

The app stores one primary normalized workspace document in IndexedDB:

- Database: `mahjongKnowledgeMapWorkspace`
- Table: `workspaces`
- Record id: `primary`

The persisted document includes `projects`, `sheets`, `active_project_id`, `active_sheet_id`, `global_settings`, and the existing top-level content arrays.

`scopeMode`, selected node / edge ids, open tabs, modal visibility, and candidate-tree selection are UI state and are not part of `WorkspaceDocument`.

The autosave interval is separate localStorage state.

There is no backend, auth, multi-user sync, or server-side DB.

## Undo / Redo

Undo history stores workspace document snapshots in memory, capped at 50 entries.
Drag position updates are committed on drag stop, not continuously during drag.
Ctrl+Z, Ctrl+Y, and the header undo/redo buttons use the same history stack.

## Save Lifecycle

The app does not persist every edit immediately. Store mutations mark the document as unsaved, manual save writes the current document to IndexedDB, and interval autosave retries unsaved or failed states every configured interval.
The interval is stored in localStorage and defaults to 5 minutes.

## Technology Notes

`@xyflow/react` is used as the current React Flow package. It is documented in the README as the React Flow implementation choice.

UI primitives are local components rather than generated shadcn files. This keeps the MVP small and still preserves the same composition style.
