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
  Braces,
  ClipboardList,
  Database,
  FlaskConical,
  GitFork,
  GraduationCap,
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
import { MappingInbox } from "../ui/mapping/MappingInbox";
import { RuleBuilderLite } from "../ui/rules/RuleBuilderLite";
import { HandValueRangeLens } from "../ui/theory/HandValueRangeLens";
import { RescueRateLens } from "../ui/theory/RescueRateLens";

const navItems: {
  screen: Screen;
  label: string;
  icon: ComponentType<{ className?: string }>;
}[] = [
  { screen: "case", label: "局面で考える", icon: GitFork },
  { screen: "theory", label: "理論を整理する", icon: Map },
  { screen: "probability", label: "確率と枝刈り", icon: FlaskConical },
  { screen: "validation", label: "読みを検証する", icon: ClipboardList },
  { screen: "teaching", label: "教材化する", icon: GraduationCap },
  { screen: "data", label: "データ管理", icon: Braces },
];

const purposeDescriptions: Record<Screen, string> = {
  case:
    "観測、仮説、条件、判断を1つの局面に紐づけて整理します。結論だけでなく、途中の重み付けと迷いも残します。",
  theory:
    "手牌価値レンジ理論、押し引き、脇救済率などの抽象概念を、知識ノード・指標・影響・ルールへ変換します。",
  probability:
    "choice group、全体100%制約、枝刈り、ロックを分けて確認します。候補を削る操作と分布を固定する操作を混同しないための作業場です。",
  validation:
    "読みが選択肢比較、枝刈り、曖昧性解消、追加観測にどれだけ効いたかを検証します。",
  teaching:
    "判断がどう変化したか、まだ曖昧な点、次に見るべき情報を教材向けの説明として整理します。",
  data: "ワークスペース全体のJSON入出力、枝刈り画面向けサブグラフ出力、初期化を管理します。",
};

type TheoryWorkspaceTab = "inbox" | "map" | "hand" | "rescue" | "rules";
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
  const [theoryTab, setTheoryTab] = useState<TheoryWorkspaceTab>("inbox");
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

    if (activeScreen === "theory") {
      return <TheoryWorkspace activeTab={theoryTab} setActiveTab={setTheoryTab} />;
    }

    if (activeScreen === "probability") {
      return (
        <PruningWorkspace activeTab={pruningTab} setActiveTab={setPruningTab} />
      );
    }

    if (activeScreen === "validation") {
      return (
        <ReasoningLab
          key="validation-reasoning"
          initialTab="concentration"
          scope="all"
        />
      );
    }

    if (activeScreen === "teaching") {
      return (
        <ReasoningLab
          key="teaching-reasoning"
          initialTab="education"
          scope="explanation"
        />
      );
    }

    return <ImportExportPanel />;
  };

  return (
    <div className="flex h-screen min-h-[720px] flex-col bg-stone-100 text-stone-900">
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-stone-300 bg-white px-3">
        <div className="flex shrink-0 items-center gap-3">
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

        <nav className="flex min-w-0 flex-1 items-center justify-start gap-1 overflow-x-auto px-1">
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

        <div className="flex min-w-fit shrink-0 items-center justify-end gap-2 text-xs text-stone-500">
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

function TheoryWorkspace({
  activeTab,
  setActiveTab,
}: {
  activeTab: TheoryWorkspaceTab;
  setActiveTab: (tab: TheoryWorkspaceTab) => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SubNavigation
        label="整理モード"
        active={activeTab}
        onChange={setActiveTab}
        items={[
          { id: "inbox", label: "Mapping Inbox" },
          { id: "map", label: "知識マップ" },
          { id: "hand", label: "手牌価値" },
          { id: "rescue", label: "脇救済率" },
          { id: "rules", label: "ルール作成" },
        ]}
      />
      {activeTab === "inbox" ? <MappingInbox /> : null}
      {activeTab === "map" ? <KnowledgeMap /> : null}
      {activeTab === "hand" ? <HandValueRangeLens /> : null}
      {activeTab === "rescue" ? <RescueRateLens /> : null}
      {activeTab === "rules" ? <RuleBuilderLite /> : null}
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
