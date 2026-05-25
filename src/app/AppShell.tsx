import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  BookOpen,
  Braces,
  Database,
  FlaskConical,
  GitFork,
  Map,
  Redo2,
  Save,
  Settings2,
  Undo2,
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
  { screen: "case", label: "局面で考える", icon: GitFork },
  { screen: "knowledge", label: "知識を作る", icon: Map },
  { screen: "pruning", label: "枝刈りを検証する", icon: FlaskConical },
  { screen: "explanation", label: "読みを説明する", icon: BookOpen },
  { screen: "data", label: "データ管理", icon: Braces },
];

const purposeDescriptions: Record<Screen, string> = {
  case: "実戦局面に観測、仮説、条件、判断を並べ、関連する知識やルールを参照しながら読みを進めます。",
  knowledge:
    "読みの知識、条件、根拠、ルールを作成し、意味・確率・影響・枝刈り・教育の観点で整理します。",
  pruning:
    "候補の確率伝播、指標への影響、枝刈りやロックの前後差分を確認して、残す読みと削る読みを検証します。",
  explanation:
    "集中度、読み筋タイムライン、教育用説明を使い、判断に至る流れと学習向けの説明を組み立てます。",
  data: "ワークスペース全体のJSON入出力、枝刈り画面向けサブグラフ出力、初期化を管理します。",
};

type KnowledgeWorkspaceTab = "map" | "rules";
type PruningWorkspaceTab = "probability" | "influence" | "lab";

const autoSaveIntervalOptions = [1, 5, 10, 15, 30, 60];

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select";
}

function saveErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "ワークスペースの保存に失敗しました。";
}

export function AppShell() {
  const doc = useAppStore((state) => state.doc);
  const activeScreen = useAppStore((state) => state.activeScreen);
  const saveStatus = useAppStore((state) => state.saveStatus);
  const autoSaveIntervalMinutes = useAppStore(
    (state) => state.autoSaveIntervalMinutes,
  );
  const lastSavedAt = useAppStore((state) => state.lastSavedAt);
  const errorMessage = useAppStore((state) => state.errorMessage);
  const undoStack = useAppStore((state) => state.undoStack);
  const redoStack = useAppStore((state) => state.redoStack);
  const hydrate = useAppStore((state) => state.hydrate);
  const setScreen = useAppStore((state) => state.setScreen);
  const setSaveStatus = useAppStore((state) => state.setSaveStatus);
  const markSaved = useAppStore((state) => state.markSaved);
  const setAutoSaveIntervalMinutes = useAppStore(
    (state) => state.setAutoSaveIntervalMinutes,
  );
  const undo = useAppStore((state) => state.undo);
  const redo = useAppStore((state) => state.redo);
  const loaded = useRef(false);
  const saving = useRef(false);
  const docRef = useRef(doc);
  const saveStatusRef = useRef(saveStatus);
  const [knowledgeTab, setKnowledgeTab] =
    useState<KnowledgeWorkspaceTab>("map");
  const [pruningTab, setPruningTab] =
    useState<PruningWorkspaceTab>("probability");

  useEffect(() => {
    docRef.current = doc;
  }, [doc]);

  useEffect(() => {
    saveStatusRef.current = saveStatus;
  }, [saveStatus]);

  const saveCurrentWorkspace = useCallback(async () => {
    if (!loaded.current || saving.current) return;
    saving.current = true;
    setSaveStatus("saving");
    try {
      await saveWorkspace(docRef.current);
      markSaved();
    } catch (error: unknown) {
      setSaveStatus("error", saveErrorMessage(error));
    } finally {
      saving.current = false;
    }
  }, [markSaved, setSaveStatus]);

  useEffect(() => {
    loadWorkspace()
      .then((workspace) => {
        docRef.current = workspace;
        hydrate(workspace);
        loaded.current = true;
      })
      .catch((error: unknown) => {
        loaded.current = true;
        setSaveStatus(
          "error",
          error instanceof Error
            ? error.message
            : "ワークスペースの読み込みに失敗しました。",
        );
      });
  }, [hydrate, setSaveStatus]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();

      if (key === "s") {
        event.preventDefault();
        void saveCurrentWorkspace();
        return;
      }

      if (isEditableTarget(event.target)) return;

      if (key === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
        return;
      }

      if (key === "y") {
        event.preventDefault();
        redo();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [redo, saveCurrentWorkspace, undo]);

  useEffect(() => {
    const intervalMs = autoSaveIntervalMinutes * 60 * 1000;
    const interval = window.setInterval(() => {
      if (
        saveStatusRef.current !== "idle" &&
        saveStatusRef.current !== "error"
      ) {
        return;
      }
      void saveCurrentWorkspace();
    }, intervalMs);

    return () => window.clearInterval(interval);
  }, [autoSaveIntervalMinutes, saveCurrentWorkspace]);

  const saveStatusLabel =
    saveStatus === "loading"
      ? "読み込み中"
      : saveStatus === "saving"
        ? "保存中"
        : saveStatus === "error"
          ? "保存エラー"
          : saveStatus === "idle"
            ? "未保存"
            : lastSavedAt
              ? `保存済み ${new Date(lastSavedAt).toLocaleTimeString()}`
              : "保存済み";

  const autoSaveOptions = useMemo(
    () =>
      autoSaveIntervalOptions.includes(autoSaveIntervalMinutes)
        ? autoSaveIntervalOptions
        : [...autoSaveIntervalOptions, autoSaveIntervalMinutes].sort(
            (left, right) => left - right,
          ),
    [autoSaveIntervalMinutes],
  );

  const handleAutoSaveIntervalChange = (
    event: ChangeEvent<HTMLSelectElement>,
  ) => {
    setAutoSaveIntervalMinutes(Number(event.target.value));
  };

  const activeNavItem =
    navItems.find((item) => item.screen === activeScreen) ?? navItems[0];

  const renderActiveScreen = () => {
    if (activeScreen === "case") {
      return <CaseWorkspace />;
    }

    if (activeScreen === "knowledge") {
      return (
        <KnowledgeWorkspace
          activeTab={knowledgeTab}
          setActiveTab={setKnowledgeTab}
        />
      );
    }

    if (activeScreen === "pruning") {
      return (
        <PruningWorkspace activeTab={pruningTab} setActiveTab={setPruningTab} />
      );
    }

    if (activeScreen === "explanation") {
      return <ReasoningLab initialTab="concentration" scope="explanation" />;
    }

    return <ImportExportPanel />;
  };

  return (
    <div className="flex h-screen min-h-[720px] flex-col bg-stone-100 text-stone-900">
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-stone-300 bg-white px-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-700 bg-cyan-700 text-white">
            <Database className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold leading-5 text-stone-950">
              麻雀思考ラボ
            </h1>
            <p className="truncate text-xs text-stone-500">
              {doc.schema_version}
            </p>
          </div>
        </div>

        <nav className="flex min-w-0 flex-1 items-center justify-center gap-1 overflow-x-auto">
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

        <div className="flex min-w-fit items-center justify-end gap-2 text-xs text-stone-500">
          <Button
            size="icon"
            variant="ghost"
            onClick={undo}
            disabled={undoStack.length === 0}
            title="元に戻す (Ctrl+Z)"
            aria-label="元に戻す"
          >
            <Undo2 className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={redo}
            disabled={redoStack.length === 0}
            title="やり直す (Ctrl+Y)"
            aria-label="やり直す"
          >
            <Redo2 className="h-4 w-4" aria-hidden="true" />
          </Button>
          <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-stone-600">
            <Settings2 className="h-4 w-4" aria-hidden="true" />
            <span>自動保存</span>
            <select
              className="h-8 rounded-md border border-stone-300 bg-white px-2 text-xs text-stone-800 outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
              value={autoSaveIntervalMinutes}
              onChange={handleAutoSaveIntervalChange}
            >
              {autoSaveOptions.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes}分ごと
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={() => void saveCurrentWorkspace()}
            disabled={saveStatus === "loading" || saveStatus === "saving"}
            title="保存 (Ctrl+S)"
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            保存
          </Button>
          <span
            className={cn(
              "min-w-24 text-right",
              saveStatus === "idle" && "text-amber-700",
              saveStatus === "error" && "text-rose-700",
            )}
          >
            {saveStatusLabel}
          </span>
        </div>
      </header>

      {errorMessage ? (
        <div className="border-b border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {errorMessage}
        </div>
      ) : null}

      <PurposeFrame
        title={activeNavItem.label}
        description={purposeDescriptions[activeNavItem.screen]}
      >
        {renderActiveScreen()}
      </PurposeFrame>
    </div>
  );
}

function PurposeFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <section className="border-b border-stone-200 bg-white px-4 py-3">
        <p className="text-xs font-semibold text-cyan-700">
          この画面でできること
        </p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-2">
          <h2 className="text-lg font-semibold leading-6 text-stone-950">
            {title}
          </h2>
          <p className="max-w-4xl text-sm leading-6 text-stone-600">
            {description}
          </p>
        </div>
      </section>
      {children}
    </div>
  );
}

function SubNavigation<T extends string>({
  label,
  items,
  active,
  onChange,
}: {
  label: string;
  items: { id: T; label: string }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-stone-200 bg-stone-50 px-3 py-2">
      <span className="text-xs font-semibold text-stone-500">{label}</span>
      <div className="flex flex-wrap gap-1" role="toolbar" aria-label={label}>
        {items.map((item) => (
          <Button
            key={item.id}
            size="sm"
            variant={active === item.id ? "primary" : "secondary"}
            onClick={() => onChange(item.id)}
            aria-pressed={active === item.id}
          >
            {item.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

function KnowledgeWorkspace({
  activeTab,
  setActiveTab,
}: {
  activeTab: KnowledgeWorkspaceTab;
  setActiveTab: (tab: KnowledgeWorkspaceTab) => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SubNavigation
        label="作成モード"
        active={activeTab}
        onChange={setActiveTab}
        items={[
          { id: "map", label: "知識マップ" },
          { id: "rules", label: "ルール作成" },
        ]}
      />
      {activeTab === "map" ? <KnowledgeMap /> : <RuleBuilderLite />}
    </div>
  );
}

function PruningWorkspace({
  activeTab,
  setActiveTab,
}: {
  activeTab: PruningWorkspaceTab;
  setActiveTab: (tab: PruningWorkspaceTab) => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SubNavigation
        label="検証モード"
        active={activeTab}
        onChange={setActiveTab}
        items={[
          { id: "probability", label: "確率伝播" },
          { id: "influence", label: "影響モデル" },
          { id: "lab", label: "枝刈りラボ" },
        ]}
      />
      {activeTab === "probability" ? <ProbabilityWorkbench /> : null}
      {activeTab === "influence" ? <InfluenceWorkbench /> : null}
      {activeTab === "lab" ? (
        <ReasoningLab initialTab="pruning" scope="pruning" />
      ) : null}
    </div>
  );
}
