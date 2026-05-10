import { useEffect, useRef, type ComponentType } from "react";
import {
  Braces,
  Database,
  FlaskConical,
  GitFork,
  Map,
  Network,
  Route,
  Save,
  Settings2,
} from "lucide-react";
import { useAppStore, type Screen } from "./store";
import { loadWorkspace, saveWorkspace } from "../infrastructure/db";
import { cn } from "../shared/cn";
import { Button } from "../ui/components/button";
import { CaseWorkspace } from "../ui/case/CaseWorkspace";
import { ImportExportPanel } from "../ui/io/ImportExportPanel";
import { InfluenceWorkbench } from "../ui/influence/InfluenceWorkbench";
import { KnowledgeMap } from "../ui/knowledge/KnowledgeMap";
import { ProbabilityWorkbench } from "../ui/probability/ProbabilityWorkbench";
import { ReasoningLab } from "../ui/lab/ReasoningLab";
import { RuleBuilderLite } from "../ui/rules/RuleBuilderLite";

const navItems: {
  screen: Screen;
  label: string;
  icon: ComponentType<{ className?: string }>;
}[] = [
  { screen: "knowledge", label: "Knowledge Map", icon: Map },
  { screen: "case", label: "Case Workspace", icon: GitFork },
  { screen: "rules", label: "Rule Builder", icon: Settings2 },
  { screen: "probability", label: "Probability", icon: Network },
  { screen: "influence", label: "Influence", icon: Route },
  { screen: "lab", label: "Reasoning Lab", icon: FlaskConical },
  { screen: "io", label: "JSON I/O", icon: Braces },
];

export function AppShell() {
  const doc = useAppStore((state) => state.doc);
  const activeScreen = useAppStore((state) => state.activeScreen);
  const saveStatus = useAppStore((state) => state.saveStatus);
  const lastSavedAt = useAppStore((state) => state.lastSavedAt);
  const errorMessage = useAppStore((state) => state.errorMessage);
  const hydrate = useAppStore((state) => state.hydrate);
  const setScreen = useAppStore((state) => state.setScreen);
  const setSaveStatus = useAppStore((state) => state.setSaveStatus);
  const markSaved = useAppStore((state) => state.markSaved);
  const loaded = useRef(false);

  useEffect(() => {
    loadWorkspace()
      .then((workspace) => {
        hydrate(workspace);
        loaded.current = true;
      })
      .catch((error: unknown) => {
        loaded.current = true;
        setSaveStatus(
          "error",
          error instanceof Error ? error.message : "Failed to load workspace.",
        );
      });
  }, [hydrate, setSaveStatus]);

  useEffect(() => {
    if (!loaded.current) return;
    setSaveStatus("saving");
    const timeout = window.setTimeout(() => {
      saveWorkspace(doc)
        .then(() => markSaved())
        .catch((error: unknown) => {
          setSaveStatus(
            "error",
            error instanceof Error
              ? error.message
              : "Failed to save workspace.",
          );
        });
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [doc, markSaved, setSaveStatus]);

  return (
    <div className="flex h-screen min-h-[720px] flex-col bg-stone-100 text-stone-900">
      <header className="flex min-h-14 items-center justify-between border-b border-stone-300 bg-white px-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-700 bg-cyan-700 text-white">
            <Database className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold leading-5 text-stone-950">
              Mahjong Reasoning Lab
            </h1>
            <p className="truncate text-xs text-stone-500">
              {doc.schema_version}
            </p>
          </div>
        </div>

        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Button
                key={item.screen}
                variant={activeScreen === item.screen ? "primary" : "ghost"}
                onClick={() => setScreen(item.screen)}
                className={cn(activeScreen === item.screen && "shadow-sm")}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Button>
            );
          })}
        </nav>

        <div className="flex min-w-48 items-center justify-end gap-2 text-xs text-stone-500">
          <Save className="h-4 w-4" aria-hidden="true" />
          <span>
            {saveStatus === "loading"
              ? "loading"
              : saveStatus === "saving"
                ? "saving"
                : saveStatus === "error"
                  ? "save error"
                  : lastSavedAt
                    ? `saved ${new Date(lastSavedAt).toLocaleTimeString()}`
                    : "local"}
          </span>
        </div>
      </header>

      {errorMessage ? (
        <div className="border-b border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {errorMessage}
        </div>
      ) : null}

      {activeScreen === "knowledge" ? <KnowledgeMap /> : null}
      {activeScreen === "case" ? <CaseWorkspace /> : null}
      {activeScreen === "rules" ? <RuleBuilderLite /> : null}
      {activeScreen === "probability" ? <ProbabilityWorkbench /> : null}
      {activeScreen === "influence" ? <InfluenceWorkbench /> : null}
      {activeScreen === "lab" ? <ReasoningLab /> : null}
      {activeScreen === "io" ? <ImportExportPanel /> : null}
    </div>
  );
}
