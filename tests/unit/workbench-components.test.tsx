import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useAppStore } from "../../src/app/store";
import { edgeTypes, type EdgeType } from "../../src/domain/schema";
import { seedWorkspace } from "../../src/domain/seed";
import { CaseWorkspace } from "../../src/ui/case/CaseWorkspace";
import { Inspector } from "../../src/ui/knowledge/Inspector";
import { LegendPanel } from "../../src/ui/knowledge/LegendPanel";
import { MappingInbox } from "../../src/ui/mapping/MappingInbox";
import { QuickReadingInputPanel } from "../../src/ui/reading/QuickReadingInputPanel";
import { HandValueRangeLens } from "../../src/ui/theory/HandValueRangeLens";
import { RescueRateLens } from "../../src/ui/theory/RescueRateLens";

const edgeColors = Object.fromEntries(
  edgeTypes.map((type) => [type, "#0e7490"]),
) as Record<EdgeType, string>;

describe("workbench components", () => {
  beforeEach(() => {
    useAppStore.setState({
      doc: seedWorkspace,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      search: "",
      tagFilter: [],
      nodeTypeFilter: [],
      scopeMode: "sheet",
    });
  });

  it("creates draft nodes from Mapping Inbox", async () => {
    const user = userEvent.setup();
    render(<MappingInbox />);

    await user.type(
      screen.getByLabelText("考察メモを貼り付け"),
      "一巡以内の脇救済率を上限レンジで見る。",
    );
    await user.selectOptions(
      screen.getByLabelText("テンプレート"),
      "rescue_rate",
    );

    expect(
      screen.getAllByText("卓上動態 / 他家介入読み").length,
    ).toBeGreaterThan(0);
    await user.click(
      screen.getByRole("button", { name: "ケースに紐づけて作成" }),
    );

    expect(
      useAppStore
        .getState()
        .doc.nodes.some((node) => node.title === "卓上動態 / 他家介入読み"),
    ).toBe(true);
  });

  it("shows numeric hints in Mapping Inbox", async () => {
    const user = userEvent.setup();
    render(<MappingInbox />);

    await user.type(
      screen.getByLabelText("考察メモを貼り付け"),
      "染め本線 p=60% confidence=0.65 打点+0.25 keep_top_k=3",
    );

    expect(screen.getByText("数値ヒント")).toBeVisible();
    expect(screen.getByText(/posterior 60%/)).toBeVisible();
    expect(screen.getByText("keep_top_k")).toBeVisible();
  });

  it("previews and applies a quick numeric reading", async () => {
    const user = userEvent.setup();
    render(<QuickReadingInputPanel />);

    expect(
      screen.getByText(/4軸の合計を100にする必要はありません/),
    ).toBeVisible();
    expect(screen.getByText("影響ウェイト 10/100")).toBeVisible();
    expect(screen.getAllByText("軸確信度 55/100").length).toBeGreaterThan(0);
    expect(screen.queryByText("影響ウェイト 10%")).not.toBeInTheDocument();
    expect(screen.getByText("候補合計 85%")).toBeVisible();
    expect(screen.getByText("未配分 15%")).toBeVisible();

    const impactWeightInputs = screen.getAllByLabelText("影響ウェイト number");
    const axisConfidenceInputs = screen.getAllByLabelText("軸確信度 number");
    await user.clear(impactWeightInputs[0]);
    await user.type(impactWeightInputs[0], "70");
    await user.clear(axisConfidenceInputs[0]);
    await user.type(axisConfidenceInputs[0], "40");
    expect(
      screen.getByText(
        "影響ウェイトが高い一方で軸確信度が低いです。過大反映の可能性があります。",
      ),
    ).toBeVisible();
    await user.clear(axisConfidenceInputs[0]);
    await user.type(axisConfidenceInputs[0], "80");
    expect(screen.getByText("影響ウェイト 70/100")).toBeVisible();
    expect(screen.getByText("軸確信度 80/100")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "候補を提案" }));
    expect(screen.getByText("候補提案")).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "候補に追加" })[0]);
    expect(screen.getByText("未配分 7%")).toBeVisible();

    await user.clear(screen.getByLabelText("読みタイトル"));
    await user.type(
      screen.getByLabelText("読みタイトル"),
      "染め本線の数値読み",
    );
    await user.click(screen.getAllByRole("button", { name: "プレビュー" })[0]);

    expect(screen.getByText(/作成予定ノード/)).toBeVisible();
    expect(screen.getByText("choice group確率")).toBeVisible();

    await user.click(
      screen.getAllByRole("button", { name: "active caseに反映" })[0],
    );

    const state = useAppStore.getState();
    const readingNode = state.doc.nodes.find(
      (node) => node.title === "染め本線の数値読み",
    );
    expect(readingNode).toBeDefined();
    expect(
      state.doc.edges.some(
        (edge) =>
          edge.source === readingNode?.id &&
          edge.relation_layer === "influence" &&
          edge.magnitude === 0.7 &&
          edge.confidence === 0.8,
      ),
    ).toBe(true);
    expect(
      state.doc.cases
        .find((caseItem) => caseItem.id === state.doc.active_case_id)
        ?.attached_node_ids.some((id) =>
          state.doc.nodes.find(
            (node) => node.id === id && node.title === "染め本線の数値読み",
          ),
        ),
    ).toBe(true);
  });

  it("switches Case Workspace between lane and decision pipeline modes", async () => {
    const user = userEvent.setup();
    render(<CaseWorkspace />);

    await user.click(screen.getByRole("button", { name: /判断プロセス/ }));

    expect(screen.getByText("洗い出し")).toBeVisible();
    expect(screen.getByText("この局面で足りない要素")).toBeVisible();
  });

  it("shows hand value metrics and influence signs", () => {
    render(<HandValueRangeLens />);

    expect(screen.getAllByText("進行度・聴牌率").length).toBeGreaterThan(0);
    expect(screen.getAllByText("打点").length).toBeGreaterThan(0);
    expect(screen.getAllByText("待ち・形の良さ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("点数状況・行動閾値").length).toBeGreaterThan(0);
  });

  it("estimates rescue rate from event probabilities and warns on overestimation", async () => {
    const user = userEvent.setup();
    render(<RescueRateLens />);

    const inputs = screen.getAllByRole("spinbutton");
    await user.type(inputs[0], "0.2");
    await user.type(inputs[1], "0.2");

    expect(screen.getByText(/36%/)).toBeVisible();
    expect(screen.getByText(/高く見積もりすぎ/)).toBeVisible();
  });

  it("renders knowledge map legend details", () => {
    render(
      <LegendPanel
        collapsed={false}
        onToggle={() => undefined}
        edgeColors={edgeColors}
      />,
    );

    expect(screen.getByText("意味関係")).toBeVisible();
    expect(screen.getByText("確率伝播対象")).toBeVisible();
    expect(screen.getByText("pruning hints")).toBeVisible();
  });

  it("edits influence edge numeric fields in Inspector", async () => {
    const user = userEvent.setup();
    useAppStore.setState({
      selectedNodeIds: [],
      selectedEdgeIds: ["edge_hand_value_speed"],
    });
    render(<Inspector />);

    await user.selectOptions(screen.getByLabelText("sign"), "+");
    await user.clear(screen.getByLabelText("影響ウェイト number"));
    await user.type(screen.getByLabelText("影響ウェイト number"), "70");

    const edge = useAppStore
      .getState()
      .doc.edges.find((item) => item.id === "edge_hand_value_speed");
    expect(edge?.sign).toBe("+");
    expect(edge?.magnitude).toBe(0.7);
  });
});
