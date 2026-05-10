# Architecture

## Goal

Mahjong Knowledge Mapper is a local-first web app for structuring mahjong reading knowledge and projecting it onto concrete cases.
It intentionally stops before full automatic inference.

## Boundaries

```text
src/app
  AppShell, navigation, autosave lifecycle, Zustand store

src/domain
  zod schemas, seed data, labels, factories, JSON export transformation, propagation engine, influence analysis, Reasoning Lab calculations

src/infrastructure
  IndexedDB persistence and browser file I/O

src/ui
  Feature screens and small shadcn-like UI primitives
```

The domain layer does not import React. This keeps the JSON schemas and future pruning-ui export reusable outside the current web app.

## Data Flow

1. `AppShell` loads a workspace document from IndexedDB via Dexie.
2. If no local document exists, `seedWorkspace` is used.
3. UI screens mutate the Zustand store through typed actions.
4. Store mutations validate the document shape with zod and push undo history where appropriate.
5. `AppShell` autosaves the document to IndexedDB with a short debounce.
6. JSON import/export uses `src/domain/export.ts`.
7. Probability preview uses `src/domain/probability.ts` and only mutates the document after the user applies the preview.
8. Directional influence views use `src/domain/influence.ts`; influence sign is never read from a node.
9. Reasoning Lab uses `src/domain/reasoningLab.ts` to create concentration metrics, pruning simulations, reading utility scores, lock safety estimates, chain replay diffs, and teaching logs.

## Screens

### Knowledge Map

React Flow renders the graph. The app stores canonical node positions in `KnowledgeNode.position`.

Selection is synchronized as node/edge ids only. React Flow owns its internal visual selection state to avoid update loops.

Knowledge Map is the broad semantic editing surface. It can contain concepts, notes, questions, evidence, and inference nodes, but the full graph is not passed into the propagation engine.

Group support is MVP-level:

- A group is a normal `concept` node with `is_group: true`.
- Child nodes point to it through `group_id`.
- Collapse hides direct children while keeping the group node visible.

### Case Workspace

Cases attach knowledge nodes by id. Each attached node can be assigned to one lane:

- observation
- hypothesis
- condition
- decision

Simple candidate suggestions are based on title/tag text matching and edge proximity to already attached nodes. This is not an inference engine.

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

The app stores one primary workspace document in IndexedDB:

- Database: `mahjongKnowledgeMapWorkspace`
- Table: `workspaces`
- Record id: `primary`

There is no backend, auth, multi-user sync, or server-side DB.

## Undo / Redo

Undo history stores workspace document snapshots in memory, capped at 50 entries.
Drag position updates are committed on drag stop, not continuously during drag.

## Technology Notes

`@xyflow/react` is used as the current React Flow package. It is documented in the README as the React Flow implementation choice.

UI primitives are local components rather than generated shadcn files. This keeps the MVP small and still preserves the same composition style.
