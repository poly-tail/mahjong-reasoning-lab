import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ComponentType,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Braces,
  ClipboardList,
  Database,
  FilePlus,
  FlaskConical,
  FolderPlus,
  GitFork,
  GraduationCap,
  Map,
  Redo2,
  Save,
  Settings2,
  Undo2,
  X,
} from "lucide-react";
import {
  useAppStore,
  type CreateProjectInput,
  type CreateSheetInput,
  type Screen,
} from "./store";
import { loadWorkspace, saveWorkspace } from "../infrastructure/db";
import { getActiveProject, getActiveSheet } from "../domain/projectSheets";
import { getTemplateCatalog } from "../domain/templateCatalog";
import {
  defaultGlobalSettings,
  emptyTemplateSelectionOptions,
  mergeTemplateSelectionOptions,
  type GlobalSettings,
  type TemplateSelectionOptions,
  type WorkspaceDocument,
  type WorkspaceScopeMode,
} from "../domain/schema";
import { cn } from "../shared/cn";
import { Button } from "../ui/components/button";
import { Field, Input, Select, Textarea } from "../ui/components/form";
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
  case: "観測、仮説、条件、判断を1つの局面に紐づけて整理します。結論だけでなく、途中の重み付けと迷いも残します。",
  theory:
    "手牌価値レンジ4軸、押し引き文脈、卓上動態/他家介入読みなどを、読み整理用の知識ノード・指標・影響・ルールへ変換します。",
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
const templateCatalog = getTemplateCatalog();

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
  const scopeMode = useAppStore((state) => state.scopeMode);
  const setScopeMode = useAppStore((state) => state.setScopeMode);
  const setActiveProject = useAppStore((state) => state.setActiveProject);
  const setActiveSheet = useAppStore((state) => state.setActiveSheet);
  const createProject = useAppStore((state) => state.createProject);
  const createSheet = useAppStore((state) => state.createSheet);
  const updateGlobalSettings = useAppStore(
    (state) => state.updateGlobalSettings,
  );
  const resetGlobalSettings = useAppStore((state) => state.resetGlobalSettings);
  const loaded = useRef(false);
  const saving = useRef(false);
  const docRef = useRef(doc);
  const saveStatusRef = useRef(saveStatus);
  const [theoryTab, setTheoryTab] = useState<TheoryWorkspaceTab>("inbox");
  const [pruningTab, setPruningTab] =
    useState<PruningWorkspaceTab>("probability");
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [sheetDialogOpen, setSheetDialogOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);

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
  const activeProject = getActiveProject(doc);
  const activeSheet = getActiveSheet(doc);

  const renderActiveScreen = () => {
    if (activeScreen === "case") {
      return <CaseWorkspace />;
    }

    if (activeScreen === "theory") {
      return (
        <TheoryWorkspace activeTab={theoryTab} setActiveTab={setTheoryTab} />
      );
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
    <div className="flex h-screen min-h-[720px] flex-col overflow-hidden bg-stone-100 text-stone-900">
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

      <WorkspaceScopeBar
        doc={doc}
        activeProjectId={activeProject?.id}
        activeSheetId={activeSheet?.id}
        scopeMode={scopeMode}
        onProjectChange={setActiveProject}
        onSheetChange={setActiveSheet}
        onScopeChange={setScopeMode}
        onCreateProject={() => setProjectDialogOpen(true)}
        onCreateSheet={() => setSheetDialogOpen(true)}
        onOpenSettings={() => setSettingsDialogOpen(true)}
      />

      <PurposeFrame
        title={activeNavItem.label}
        description={purposeDescriptions[activeNavItem.screen]}
      >
        {renderActiveScreen()}
      </PurposeFrame>

      {projectDialogOpen ? (
        <ProjectDialog
          defaults={doc.global_settings}
          onClose={() => setProjectDialogOpen(false)}
          onCreate={(input) => {
            createProject(input);
            setProjectDialogOpen(false);
          }}
        />
      ) : null}

      {sheetDialogOpen ? (
        <SheetDialog
          doc={doc}
          defaults={doc.global_settings}
          activeProjectId={activeProject?.id}
          onClose={() => setSheetDialogOpen(false)}
          onCreate={(input) => {
            createSheet(input);
            setSheetDialogOpen(false);
          }}
        />
      ) : null}

      {settingsDialogOpen ? (
        <GlobalSettingsDialog
          settings={doc.global_settings}
          onClose={() => setSettingsDialogOpen(false)}
          onSave={(settings) => {
            updateGlobalSettings(settings);
            setSettingsDialogOpen(false);
          }}
          onReset={() => {
            resetGlobalSettings();
            setSettingsDialogOpen(false);
          }}
        />
      ) : null}
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
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <section className="shrink-0 border-b border-stone-200 bg-white px-4 py-3">
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
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

function WorkspaceScopeBar({
  doc,
  activeProjectId,
  activeSheetId,
  scopeMode,
  onProjectChange,
  onSheetChange,
  onScopeChange,
  onCreateProject,
  onCreateSheet,
  onOpenSettings,
}: {
  doc: WorkspaceDocument;
  activeProjectId?: string;
  activeSheetId?: string;
  scopeMode: WorkspaceScopeMode;
  onProjectChange: (projectId: string) => void;
  onSheetChange: (sheetId: string) => void;
  onScopeChange: (mode: WorkspaceScopeMode) => void;
  onCreateProject: () => void;
  onCreateSheet: () => void;
  onOpenSettings: () => void;
}) {
  const projectSheets = doc.sheets.filter(
    (sheet) => sheet.project_id === activeProjectId,
  );
  return (
    <section className="flex min-h-12 flex-wrap items-center gap-2 border-b border-stone-200 bg-stone-50 px-3 py-2 text-sm">
      <label className="flex min-w-48 items-center gap-2">
        <span className="text-xs font-semibold text-stone-500">Project</span>
        <Select
          className="min-w-40"
          value={activeProjectId ?? ""}
          onChange={(event) => onProjectChange(event.target.value)}
        >
          {doc.projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.title}
            </option>
          ))}
        </Select>
      </label>
      <label className="flex min-w-48 items-center gap-2">
        <span className="text-xs font-semibold text-stone-500">Sheet</span>
        <Select
          className="min-w-40"
          value={activeSheetId ?? ""}
          onChange={(event) => onSheetChange(event.target.value)}
          disabled={projectSheets.length === 0}
        >
          {projectSheets.length === 0 ? (
            <option value="">Sheetなし</option>
          ) : null}
          {projectSheets.map((sheet) => (
            <option key={sheet.id} value={sheet.id}>
              {sheet.title}
            </option>
          ))}
        </Select>
      </label>
      <div className="flex items-center gap-1">
        <Button size="sm" onClick={onCreateProject}>
          <FolderPlus className="h-4 w-4" aria-hidden="true" />
          Project
        </Button>
        <Button size="sm" onClick={onCreateSheet} disabled={!activeProjectId}>
          <FilePlus className="h-4 w-4" aria-hidden="true" />
          Sheet
        </Button>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        <span className="mr-1 text-xs font-semibold text-stone-500">
          表示スコープ
        </span>
        {(
          [
            ["sheet", "Sheet"],
            ["project", "Project"],
            ["workspace", "Workspace"],
          ] as const
        ).map(([mode, label]) => (
          <Button
            key={mode}
            size="sm"
            variant={scopeMode === mode ? "primary" : "secondary"}
            onClick={() => onScopeChange(mode)}
            aria-pressed={scopeMode === mode}
          >
            {label}
          </Button>
        ))}
        <Button size="icon" variant="ghost" onClick={onOpenSettings}>
          <Settings2 className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}

function WorkspaceModal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-stone-950/30 px-4 py-8">
      <section className="max-h-[calc(100vh-4rem)] w-full max-w-2xl overflow-hidden rounded-lg border border-stone-200 bg-white shadow-xl">
        <div className="flex h-11 items-center justify-between border-b border-stone-200 px-4">
          <h2 className="text-sm font-semibold text-stone-950">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <div className="max-h-[calc(100vh-7rem)] overflow-y-auto overflow-x-hidden p-4">
          {children}
        </div>
      </section>
    </div>
  );
}

function ProjectDialog({
  defaults,
  onCreate,
  onClose,
}: {
  defaults: GlobalSettings;
  onCreate: (input: CreateProjectInput) => void;
  onClose: () => void;
}) {
  const initialEmpty = defaults.create_empty_project_by_default;
  const [title, setTitle] = useState("新規Project");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [createInitialSheet, setCreateInitialSheet] = useState(true);
  const [sheetTitle, setSheetTitle] = useState("Main Sheet");
  const [empty, setEmpty] = useState(initialEmpty);
  const [templateOptions, setTemplateOptions] = useState(
    initialEmpty
      ? emptyTemplateSelectionOptions()
      : mergeTemplateSelectionOptions(defaults.project_creation_defaults),
  );

  const handleEmptyChange = (checked: boolean) => {
    setEmpty(checked);
    setTemplateOptions(
      checked
        ? emptyTemplateSelectionOptions()
        : mergeTemplateSelectionOptions(defaults.project_creation_defaults),
    );
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onCreate({
      title,
      description,
      tags: splitTags(tags),
      createInitialSheet,
      initialSheetTitle: sheetTitle,
      templateOptions,
    });
  };

  return (
    <WorkspaceModal title="Projectを作成" onClose={onClose}>
      <form className="grid gap-3" onSubmit={handleSubmit}>
        <Field label="Project名">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <Field label="説明">
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <Field label="タグ" hint="カンマ区切り">
          <Input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={createInitialSheet}
            onChange={(event) => setCreateInitialSheet(event.target.checked)}
          />
          初期Sheetを作成
        </label>
        {createInitialSheet ? (
          <Field label="初期Sheet名">
            <Input
              value={sheetTitle}
              onChange={(event) => setSheetTitle(event.target.value)}
            />
          </Field>
        ) : null}
        <TemplateOptionsEditor
          title="初期テンプレート"
          empty={empty}
          options={templateOptions}
          onEmptyChange={handleEmptyChange}
          onOptionsChange={setTemplateOptions}
        />
        <DialogActions onClose={onClose} submitLabel="作成" />
      </form>
    </WorkspaceModal>
  );
}

function SheetDialog({
  doc,
  defaults,
  activeProjectId,
  onCreate,
  onClose,
}: {
  doc: WorkspaceDocument;
  defaults: GlobalSettings;
  activeProjectId?: string;
  onCreate: (input: CreateSheetInput) => void;
  onClose: () => void;
}) {
  const initialEmpty = defaults.create_empty_sheet_by_default;
  const [projectId, setProjectId] = useState(
    activeProjectId ?? doc.projects[0]?.id ?? "",
  );
  const [title, setTitle] = useState("新規Sheet");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [empty, setEmpty] = useState(initialEmpty);
  const [templateOptions, setTemplateOptions] = useState(
    initialEmpty
      ? emptyTemplateSelectionOptions()
      : mergeTemplateSelectionOptions(defaults.sheet_creation_defaults),
  );

  const handleEmptyChange = (checked: boolean) => {
    setEmpty(checked);
    setTemplateOptions(
      checked
        ? emptyTemplateSelectionOptions()
        : mergeTemplateSelectionOptions(defaults.sheet_creation_defaults),
    );
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!projectId) return;
    onCreate({
      projectId,
      title,
      description,
      tags: splitTags(tags),
      templateOptions,
    });
  };

  return (
    <WorkspaceModal title="Sheetを作成" onClose={onClose}>
      <form className="grid gap-3" onSubmit={handleSubmit}>
        <Field label="Project">
          <Select
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            {doc.projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Sheet名">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <Field label="説明">
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <Field label="タグ" hint="カンマ区切り">
          <Input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
          />
        </Field>
        <TemplateOptionsEditor
          title="初期テンプレート"
          empty={empty}
          options={templateOptions}
          onEmptyChange={handleEmptyChange}
          onOptionsChange={setTemplateOptions}
        />
        <DialogActions
          onClose={onClose}
          submitLabel="作成"
          disabled={!projectId}
        />
      </form>
    </WorkspaceModal>
  );
}

function GlobalSettingsDialog({
  settings,
  onSave,
  onReset,
  onClose,
}: {
  settings: GlobalSettings;
  onSave: (settings: GlobalSettings) => void;
  onReset: () => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<GlobalSettings>(settings);
  const updateDraft = (patch: Partial<GlobalSettings>) =>
    setDraft((current) => ({ ...current, ...patch }));

  return (
    <WorkspaceModal title="Global Settings" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(draft);
        }}
      >
        <TemplateOptionsEditor
          title="新規Projectの既定テンプレート"
          empty={draft.create_empty_project_by_default}
          options={draft.project_creation_defaults}
          onEmptyChange={(checked) =>
            updateDraft({
              create_empty_project_by_default: checked,
              project_creation_defaults: checked
                ? emptyTemplateSelectionOptions()
                : mergeTemplateSelectionOptions(
                    defaultGlobalSettings.project_creation_defaults,
                  ),
            })
          }
          onOptionsChange={(options) =>
            updateDraft({ project_creation_defaults: options })
          }
        />
        <TemplateOptionsEditor
          title="新規Sheetの既定テンプレート"
          empty={draft.create_empty_sheet_by_default}
          options={draft.sheet_creation_defaults}
          onEmptyChange={(checked) =>
            updateDraft({
              create_empty_sheet_by_default: checked,
              sheet_creation_defaults: checked
                ? emptyTemplateSelectionOptions()
                : mergeTemplateSelectionOptions(
                    defaultGlobalSettings.sheet_creation_defaults,
                  ),
            })
          }
          onOptionsChange={(options) =>
            updateDraft({ sheet_creation_defaults: options })
          }
        />
        <div className="flex flex-wrap justify-between gap-2 border-t border-stone-200 pt-3">
          <Button type="button" variant="ghost" onClick={onReset}>
            既定値に戻す
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              キャンセル
            </Button>
            <Button type="submit" variant="primary">
              保存
            </Button>
          </div>
        </div>
      </form>
    </WorkspaceModal>
  );
}

function TemplateOptionsEditor({
  title,
  empty,
  options,
  onEmptyChange,
  onOptionsChange,
}: {
  title: string;
  empty: boolean;
  options: TemplateSelectionOptions;
  onEmptyChange: (checked: boolean) => void;
  onOptionsChange: (options: TemplateSelectionOptions) => void;
}) {
  const updateOption = (
    key: keyof TemplateSelectionOptions,
    checked: boolean,
  ) => {
    onOptionsChange({ ...options, [key]: checked });
  };

  return (
    <section className="grid gap-2 rounded-md border border-stone-200 bg-stone-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-stone-950">{title}</div>
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={empty}
            onChange={(event) => onEmptyChange(event.target.checked)}
          />
          空で作成
        </label>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {templateCatalog.map((template) => (
          <label
            key={template.key}
            className="flex items-start gap-2 rounded-md border border-stone-200 bg-white p-2 text-sm text-stone-700"
          >
            <input
              className="mt-1"
              type="checkbox"
              checked={options[template.key]}
              disabled={empty}
              onChange={(event) =>
                updateOption(template.key, event.target.checked)
              }
            />
            <span>
              <span className="block font-semibold text-stone-900">
                {template.label}
              </span>
              <span className="text-xs leading-5 text-stone-500">
                {template.description}
              </span>
            </span>
          </label>
        ))}
      </div>
    </section>
  );
}

function DialogActions({
  onClose,
  submitLabel,
  disabled,
}: {
  onClose: () => void;
  submitLabel: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex justify-end gap-2 border-t border-stone-200 pt-3">
      <Button type="button" variant="ghost" onClick={onClose}>
        キャンセル
      </Button>
      <Button type="submit" variant="primary" disabled={disabled}>
        {submitLabel}
      </Button>
    </div>
  );
}

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
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
