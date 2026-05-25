import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useAppStore } from "../../src/app/store";
import { edgeTypes, type EdgeType } from "../../src/domain/schema";
import { seedWorkspace } from "../../src/domain/seed";
import { CaseWorkspace } from "../../src/ui/case/CaseWorkspace";
import { LegendPanel } from "../../src/ui/knowledge/LegendPanel";
import { MappingInbox } from "../../src/ui/mapping/MappingInbox";
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
    });
  });

  it("creates draft nodes from Mapping Inbox", async () => {
    const user = userEvent.setup();
    render(<MappingInbox />);

    await user.type(
      screen.getByLabelText("考察メモを貼り付け"),
      "一巡以内の脇救済率を上限レンジで見る。",
    );
    await user.selectOptions(screen.getByLabelText("テンプレート"), "rescue_rate");

    expect(screen.getAllByText("脇救済率").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "ケースに紐づけて作成" }));

    expect(
      useAppStore.getState().doc.nodes.some((node) => node.title === "脇救済率"),
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
});
