"use client";

import { useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock3,
  File,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Globe2,
  History,
  LayoutGrid,
  LoaderCircle,
  Menu,
  Paperclip,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Square,
  Terminal,
  X,
} from "lucide-react";
import { useWorkspace } from "../lib/use-workspace";
import {
  activeStates,
  bytesLabel,
  RunEvent,
  safeUrl,
  statusLabel,
  StoredFile,
  taskLabel,
} from "../lib/types";
import { ChartView, FileViewer, ReportView } from "../components/report-view";
import {
  ConversationHistory,
  FollowUpComposer,
} from "../components/conversation";

const starters = [
  {
    title: "Analyze a CSV",
    icon: BarChart3,
    goal: "Analyze this sales CSV by category and generate a chart, spreadsheet, and report. Define the ranking metric explicitly.",
  },
  {
    title: "Research a topic",
    icon: Globe2,
    goal: "Research recent trends in online retail. Create a cited report that separates source evidence from hypotheses.",
  },
  {
    title: "Read a document",
    icon: FileText,
    goal: "Read the attached document and create a report summarizing the key findings and open questions.",
  },
  {
    title: "Extract a webpage",
    icon: ArrowUpRight,
    goal: "Browse https://example.com, extract its main information, and create a short report with sources.",
  },
];
const tools: Record<string, { title: string; icon: typeof FileText }> = {
  ingest: { title: "Read input", icon: FileText },
  analyze_csv: { title: "Analyze categories", icon: BarChart3 },
  search: { title: "Research context", icon: Globe2 },
  browse: { title: "Read webpage", icon: Globe2 },
  python: { title: "Run Python", icon: Terminal },
  report: { title: "Write report", icon: FileText },
  finish: { title: "Complete task", icon: Check },
};
function FileIcon({ file }: { file: StoredFile }) {
  return file.mime.includes("sheet") || file.mime === "text/csv" ? (
    <FileSpreadsheet size={20} />
  ) : file.mime.startsWith("image/") ? (
    <BarChart3 size={20} />
  ) : (
    <FileText size={20} />
  );
}
function Status({ status }: { status: string }) {
  return (
    <span className={`task-status status-${status}`}>
      <span />
      {statusLabel(status)}
    </span>
  );
}
function timeLabel(value: number) {
  return new Date(value * 1000).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

function ExecutionLog({
  events,
  status,
  compact = false,
}: {
  events: RunEvent[];
  status?: string;
  compact?: boolean;
}) {
  const actions = events
    .filter((event) => event.kind === "action")
    .map((event) => {
      const index = events.indexOf(event);
      let result: RunEvent | undefined;
      for (let i = index + 1; i < events.length; i++) {
        if (events[i].kind === "action") break;
        if (
          events[i].kind === "result" &&
          events[i].payload.tool === event.payload.tool
        ) {
          result = events[i];
          break;
        }
      }
      return { event, result };
    });
  if (!actions.length)
    return (
      <div className="log-waiting">
        <Clock3 size={17} />
        <p>
          {status === "queued"
            ? "Queued for the worker."
            : "Waiting for execution events."}
        </p>
        <span>Progress is saved automatically.</span>
      </div>
    );
  return (
    <div
      className={compact ? "execution-log compact" : "execution-log"}
      aria-live="polite"
      aria-relevant="additions"
    >
      {actions.map(({ event, result }, index) => {
        const tool = tools[event.payload.tool || ""] || {
          title: event.payload.tool || "Action",
          icon: Terminal,
        };
        const output = result?.payload.output;
        const failed = !!output?.error;
        const Icon = tool.icon;
        let detail = event.payload.summary || "";
        if (output?.error) detail = String(output.error);
        else if (typeof output?.rows === "number")
          detail = `${output.rows.toLocaleString()} rows${typeof output.excluded_rows === "number" ? ` · ${output.excluded_rows} excluded` : ""}`;
        else if (Array.isArray(output?.sources))
          detail = `${output.sources.length} source${output.sources.length === 1 ? "" : "s"} saved`;
        else if (result && event.payload.tool === "report")
          detail = "Report and PDF saved";
        else if (result && event.payload.tool === "finish")
          detail = "Outputs ready";
        const pending =
          !result && (status === "running" || status === "queued");
        return (
          <article
            className={`log-step ${failed ? "log-error" : result ? "log-done" : ""}`}
            key={event.id}
          >
            <span className="log-marker">
              {pending ? (
                <LoaderCircle size={15} className="spin" />
              ) : failed ? (
                <X size={15} />
              ) : result ? (
                <Check size={14} />
              ) : (
                <Icon size={15} />
              )}
            </span>
            <div>
              <div className="log-step-heading">
                <strong>{tool.title}</strong>
                <span>{String(index + 1).padStart(2, "0")}</span>
              </div>
              <p>{detail}</p>
              {!compact && (
                <details>
                  <summary>Action details</summary>
                  <pre>
                    {JSON.stringify(
                      { action: event.payload, result: output || null },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

export default function Workspace() {
  const { goalInput, uploadInput, ...w } = useWorkspace();
  const [view, setView] = useState<"workspace" | "history">("workspace");
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [tab, setTab] = useState<"overview" | "activity" | "files" | "sources">(
    "overview",
  );
  const [navOpen, setNavOpen] = useState(false);
  const [tokenDraft, setTokenDraft] = useState("");
  const [viewingFile, setViewingFile] = useState<StoredFile | null>(null);
  const settingsDialog = useRef<HTMLDialogElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const artifacts = w.task?.files?.filter((f) => f.kind === "artifact") || [];
  const inputs = w.task?.files?.filter((f) => f.kind === "upload") || [];
  const sources = w.task?.sources || [];
  const currentArtifacts = artifacts.filter(
    (f) => !w.task?.current_file_ids || w.task.current_file_ids.includes(f.id),
  );
  const report = [...currentArtifacts]
    .reverse()
    .find((f) => f.mime === "text/markdown");
  const pdf = [...currentArtifacts]
    .reverse()
    .find((f) => f.mime === "application/pdf");
  const charts = currentArtifacts.filter((f) => f.mime.startsWith("image/"));
  const recent = w.tasks.slice(0, 20);
  const pending = w.tasks.filter((task) => activeStates.includes(task.status));
  const displayedTasks = (view === "history" ? w.tasks : recent).filter(
    (task) =>
      task.goal.toLowerCase().includes(filter.toLowerCase()) &&
      (statusFilter === "all" ||
        (statusFilter === "active"
          ? activeStates.includes(task.status)
          : task.status === statusFilter)),
  );
  const lastMessage = w.events.findLastIndex((e) => e.kind === "message");
  const finishedSummary = [...w.events.slice(lastMessage + 1)]
    .reverse()
    .find((e) => e.payload.tool === "finish" && e.kind === "result")?.payload
    .output?.summary;
  function choose(id: string | null) {
    w.choose(id);
    setTab("overview");
    setViewingFile(null);
    setNavOpen(false);
  }
  function home() {
    setView("workspace");
    setFilter("");
    setStatusFilter("all");
    choose(null);
  }
  function history() {
    setView("history");
    choose(null);
  }
  function showSettings() {
    setNavOpen(false);
    settingsDialog.current?.showModal();
  }

  return (
    <div
      className="app-shell"
      onKeyDown={(event) => {
        if (event.key === "Escape" && navOpen) {
          setNavOpen(false);
          requestAnimationFrame(() =>
            document.querySelector<HTMLButtonElement>(".mobile-menu")?.focus(),
          );
        }
      }}
    >
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {navOpen && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      )}
      <aside className={`sidebar ${navOpen ? "is-open" : ""}`}>
        <button className="brand" onClick={home} aria-label="AutoAgent home">
          <span className="brand-mark">
            a<span>↗</span>
          </span>
          <span>AutoAgent</span>
        </button>
        <button className="new-task-button" onClick={home}>
          <Plus size={17} /> New task <span className="key-hint">↗</span>
        </button>
        <nav className="main-nav" aria-label="Workspace navigation">
          <button
            className={!w.selected && view === "workspace" ? "active" : ""}
            onClick={home}
          >
            <LayoutGrid size={17} /> Workspace
          </button>
          <button
            className={!w.selected && view === "history" ? "active" : ""}
            onClick={history}
          >
            <History size={17} /> All tasks <span>{w.tasks.length}</span>
          </button>
        </nav>
        <div className="recent-heading">
          Recent{" "}
          <button
            className="icon-button"
            aria-label="Search tasks"
            onClick={() => {
              history();
              setTimeout(() => searchInput.current?.focus(), 0);
            }}
          >
            <Search size={15} />
          </button>
        </div>
        <nav className="recent-nav" aria-label="Task history">
          {recent.length ? (
            recent.map((task) => (
              <button
                key={task.id}
                className={w.selected === task.id ? "selected" : ""}
                onClick={() => choose(task.id)}
              >
                <span className={`history-dot ${task.status}`} />
                <span>{taskLabel(task.goal)}</span>
              </button>
            ))
          ) : (
            <p className="nav-empty">Your tasks will appear here.</p>
          )}
        </nav>
        <div className="sidebar-bottom">
          <button className="settings-button" onClick={showSettings}>
            <Settings2 size={17} /> Settings
          </button>
          <div className="identity">
            <span className="identity-avatar">
              {w.config?.mode === "live" ? "A" : "L"}
            </span>
            <div>
              <strong>
                {w.config?.mode === "live"
                  ? "Live workspace"
                  : "Local workspace"}
              </strong>
              <span>
                {w.config?.mode === "demo"
                  ? "Fixture-backed demo"
                  : w.config?.model || "Connecting to service"}
              </span>
            </div>
            <span
              className={`connection-dot ${w.connection}`}
              title={w.connection}
            />
          </div>
        </div>
      </aside>
      <div className="app-content" inert={navOpen}>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => {
                setNavOpen(true);
                requestAnimationFrame(() =>
                  document
                    .querySelector<HTMLButtonElement>(".sidebar .brand")
                    ?.focus(),
                );
              }}
            >
              <Menu size={20} />
            </button>
            <span className="workspace-icon">
              <LayoutGrid size={14} />
            </span>
            <button onClick={home}>Workspace</button>
            {(w.selected || view === "history") && (
              <>
                <ChevronRight size={13} />
                <span>{w.selected ? "Task" : "All tasks"}</span>
              </>
            )}
          </div>
          <div className="topbar-right">
            <button
              className={`mode-label mode-${w.config?.mode || "unknown"}`}
              aria-label="Show workspace information"
              onClick={showSettings}
            >
              <span />
              {w.config?.mode === "demo"
                ? "Demo mode"
                : w.config?.mode === "live"
                  ? "Live mode"
                  : "Not connected"}
              <ChevronDown size={13} />
            </button>
            <span className="topbar-rule" />
            <button
              className="icon-button"
              aria-label="Workspace settings"
              onClick={showSettings}
            >
              <Settings2 size={17} />
            </button>
          </div>
        </header>
        <main
          id="main-content"
          className={w.selected ? "main task-main" : "main"}
        >
          {w.connection !== "online" && (
            <div className={`connection-notice ${w.connection}`} role="status">
              <CircleAlert size={16} />
              <span>
                {w.connection === "connecting"
                  ? "Connecting to the workspace…"
                  : w.connection === "unauthorized"
                    ? "Add your access token to open this live workspace."
                    : "Connection lost. Saved work will return when the service reconnects."}
              </span>
              <button
                onClick={
                  w.connection === "unauthorized"
                    ? showSettings
                    : () => void w.refresh()
                }
              >
                {w.connection === "unauthorized"
                  ? "Open settings"
                  : "Reconnect"}
                <ArrowRight size={14} />
              </button>
            </div>
          )}
          {w.error && (
            <div className="error-notice" role="alert">
              <CircleAlert size={17} />
              <span>{w.error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => w.setError("")}
              >
                <X size={17} />
              </button>
            </div>
          )}
          {!w.selected ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>{view === "history" ? "All tasks" : "Workspace"}</h1>
                  <p>
                    {view === "history"
                      ? "Your saved work, from start to finish."
                      : "Research, analysis, and the files that come out of it."}
                  </p>
                </div>
                {view === "history" ? (
                  <button className="button primary" onClick={home}>
                    <Plus size={16} /> New task
                  </button>
                ) : (
                  <div className="workspace-count">
                    <span className="online-dot" />
                    {pending.length
                      ? `${pending.length} active ${pending.length === 1 ? "task" : "tasks"}`
                      : "Ready for a task"}
                  </div>
                )}
              </div>
              {view === "workspace" && (
                <>
                  <form
                    className="composer"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void w.submit();
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      void w.attach(e.dataTransfer.files);
                    }}
                  >
                    <label className="composer-label" htmlFor="task-goal">
                      New task
                    </label>
                    <textarea
                      id="task-goal"
                      ref={goalInput}
                      aria-label="Your goal"
                      value={w.goal}
                      onChange={(e) => w.setGoal(e.target.value)}
                      maxLength={8000}
                      placeholder="Describe the work you want done…"
                      onKeyDown={(e) => {
                        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                          e.preventDefault();
                          void w.submit();
                        }
                      }}
                    />
                    {!!w.uploads.length && (
                      <div className="upload-chips">
                        {w.uploads.map((file) => (
                          <span key={file.id}>
                            <FileSpreadsheet size={15} />
                            {file.name}
                            <small>{bytesLabel(file.size)}</small>
                            <button
                              type="button"
                              aria-label={`Remove ${file.name}`}
                              onClick={() =>
                                w.setUploads((old) =>
                                  old.filter((f) => f.id !== file.id),
                                )
                              }
                            >
                              <X size={14} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="composer-toolbar">
                      <button
                        className="attach-button"
                        type="button"
                        disabled={w.busy}
                        onClick={() => uploadInput.current?.click()}
                      >
                        <Paperclip size={17} /> Attach files
                      </button>
                      <span className="upload-support">CSV, PDF, or text</span>
                      <button
                        className="run-button"
                        type="submit"
                        disabled={
                          w.busy ||
                          w.connection !== "online" ||
                          w.goal.trim().length < 3
                        }
                      >
                        {w.busy && <LoaderCircle size={16} className="spin" />}
                        <span>Run task</span>
                        <ArrowUpRight size={18} />
                      </button>
                    </div>
                    <input
                      ref={uploadInput}
                      type="file"
                      accept=".csv,.pdf,.txt,.md"
                      multiple
                      hidden
                      onChange={(e) => void w.attach(e.target.files)}
                    />
                  </form>
                  <div className="starter-row">
                    <span>Start with</span>
                    {starters.map(({ title, icon: Icon, goal }) => (
                      <button
                        key={title}
                        onClick={() => {
                          w.setGoal(goal);
                          goalInput.current?.focus();
                        }}
                      >
                        <Icon size={15} />
                        {title}
                      </button>
                    ))}
                  </div>
                  {w.config?.mode === "demo" && (
                    <div className="sample-strip">
                      <div className="sample-file">
                        <FileSpreadsheet size={22} />
                      </div>
                      <div>
                        <strong>Sample sales analysis</strong>
                        <p>
                          12 rows · 6 categories · chart, spreadsheet, and
                          report.
                        </p>
                      </div>
                      <button
                        className="button secondary"
                        disabled={w.busy}
                        onClick={() => void w.loadSample()}
                      >
                        Load example
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  )}
                </>
              )}
              <section className="recent-work">
                <div className="section-heading">
                  <div>
                    <h2>
                      {view === "history" ? "Task history" : "Recent work"}
                    </h2>
                    <span>
                      {view === "history" ? w.tasks.length : recent.length}
                    </span>
                  </div>
                  {view === "workspace" ? (
                    <button className="text-button" onClick={history}>
                      View all
                      <ArrowRight size={15} />
                    </button>
                  ) : (
                    <label className="task-search">
                      <Search size={16} />
                      <input
                        ref={searchInput}
                        aria-label="Search task history"
                        placeholder="Search tasks"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                      />
                      {filter && (
                        <button
                          aria-label="Clear search"
                          onClick={() => setFilter("")}
                        >
                          <X size={14} />
                        </button>
                      )}
                    </label>
                  )}
                </div>
                {view === "history" && (
                  <div className="filter-row" aria-label="Filter task status">
                    {[
                      ["all", "All tasks"],
                      ["active", "In progress"],
                      ["completed", "Completed"],
                      ["failed", "Failed"],
                    ].map(([value, label]) => (
                      <button
                        aria-pressed={statusFilter === value}
                        key={value}
                        onClick={() => setStatusFilter(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
                {displayedTasks.length ? (
                  <div className="task-table">
                    <div className="task-table-head">
                      <span>Task</span>
                      <span>Status</span>
                      <span>Files</span>
                      <span>Created</span>
                      <span />
                    </div>
                    {displayedTasks.map((task) => (
                      <button
                        className="task-row"
                        key={task.id}
                        onClick={() => choose(task.id)}
                      >
                        <span className="task-row-title">
                          <span className="task-type-icon">
                            {/csv|sales|data|chart/i.test(task.goal) ? (
                              <BarChart3 size={18} />
                            ) : /research|browse|web/i.test(task.goal) ? (
                              <Globe2 size={18} />
                            ) : (
                              <FileText size={18} />
                            )}
                          </span>
                          <span>
                            <strong>{taskLabel(task.goal)}</strong>
                            <small>
                              {task.mode === "demo" ? "Demo" : "Live"}
                              <span>·</span>
                              {task.id.slice(0, 8)}
                            </small>
                          </span>
                        </span>
                        <Status status={task.status} />
                        <span className="task-files-count">
                          <File size={13} />
                          {task.artifact_count ?? "—"}
                        </span>
                        <span className="task-created">
                          {timeLabel(task.created)}
                        </span>
                        <ArrowUpRight size={16} className="row-arrow" />
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="empty-work">
                    <span>
                      <FolderOpen size={22} />
                    </span>
                    <div>
                      <h3>
                        {filter || statusFilter !== "all"
                          ? "No matching tasks"
                          : "No tasks yet"}
                      </h3>
                      <p>
                        {filter || statusFilter !== "all"
                          ? "Try another search or status."
                          : "Run your first task above. Its progress and files will be saved here."}
                      </p>
                    </div>
                  </div>
                )}
              </section>
              <div className="workspace-footnote">
                <span>
                  <ShieldCheck size={14} /> Python execution requires approval.
                </span>
                <span>
                  {w.config?.mode === "demo"
                    ? "Demo research uses labeled fixtures."
                    : "Sources stay attached to the work."}
                </span>
              </div>
            </>
          ) : (
            <>
              <button className="back-link" onClick={home}>
                <ArrowLeft size={15} /> Workspace
              </button>
              <div className="task-heading">
                <div className="task-heading-meta">
                  <span className="task-reference">
                    TASK {w.selected.slice(0, 8)}
                  </span>
                  {w.task && <Status status={w.task.status} />}
                </div>
                <h1>{w.task ? taskLabel(w.task.goal) : "Opening task…"}</h1>
                <details className="task-brief">
                  <summary>
                    View full brief
                    <ChevronDown size={13} />
                  </summary>
                  <p>{w.task?.goal}</p>
                </details>
                <div className="task-heading-bottom">
                  <span>
                    <Clock3 size={14} />
                    {Math.round(w.task?.usage?.elapsed || 0)}s elapsed
                  </span>
                  <span>
                    {w.task?.mode === "demo"
                      ? "Fixture-backed run"
                      : w.config?.model || "Live run"}
                  </span>
                  <div>
                    {w.task && activeStates.includes(w.task.status) && (
                      <button
                        className="button secondary small"
                        disabled={w.busy}
                        onClick={() => void w.control("cancel")}
                      >
                        <Square size={13} /> Cancel
                      </button>
                    )}
                    {w.task &&
                      ["failed", "canceled"].includes(w.task.status) && (
                        <button
                          className="button secondary small"
                          disabled={w.busy}
                          onClick={() => void w.control("resume")}
                        >
                          Resume
                          <ArrowRight size={14} />
                        </button>
                      )}
                    {pdf && (
                      <button
                        className="button primary small"
                        onClick={() => void w.download(pdf)}
                      >
                        <ArrowDownToLine size={15} /> Download report
                      </button>
                    )}
                  </div>
                </div>
              </div>
              {w.task?.error && (
                <div className="task-failure" role="alert">
                  <CircleAlert size={20} />
                  <div>
                    <h2>This task needs attention</h2>
                    <p>{w.task.error}</p>
                    <span>Any finished files remain available below.</span>
                  </div>
                </div>
              )}
              {w.task?.status === "awaiting_approval" && w.task.approval && (
                <section className="approval-panel">
                  <div className="approval-heading">
                    <ShieldCheck size={21} />
                    <div>
                      <h2>Review the next action</h2>
                      <p>{w.task.approval.reason}</p>
                    </div>
                  </div>
                  <pre>{JSON.stringify(w.task.approval.decision, null, 2)}</pre>
                  <footer>
                    <span>
                      The approval applies only to this code and these files.
                    </span>
                    <button
                      className="button secondary"
                      disabled={w.busy}
                      onClick={() =>
                        void w.control("approve", {
                          digest: w.task!.approval!.digest,
                          approved: false,
                        })
                      }
                    >
                      Deny
                    </button>
                    <button
                      className="button primary"
                      disabled={w.busy}
                      onClick={() =>
                        void w.control("approve", {
                          digest: w.task!.approval!.digest,
                          approved: true,
                        })
                      }
                    >
                      Approve action
                      <ArrowRight size={15} />
                    </button>
                  </footer>
                </section>
              )}
              <div className="task-tabs" role="tablist" aria-label="Task views">
                {(["overview", "activity", "files", "sources"] as const).map(
                  (value, index) => (
                    <button
                      key={value}
                      id={`tab-${value}`}
                      role="tab"
                      aria-selected={tab === value}
                      aria-controls="task-panel"
                      tabIndex={tab === value ? 0 : -1}
                      onClick={() => {
                        setTab(value);
                        setViewingFile(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight")
                          return;
                        e.preventDefault();
                        const tabs = [
                          "overview",
                          "activity",
                          "files",
                          "sources",
                        ] as const;
                        const next =
                          (index + (e.key === "ArrowRight" ? 1 : 3)) % 4;
                        setTab(tabs[next]);
                        document.getElementById(`tab-${tabs[next]}`)?.focus();
                      }}
                    >
                      {value === "activity"
                        ? "Activity"
                        : value === "overview"
                          ? "Overview"
                          : value === "files"
                            ? "Files"
                            : "Sources"}
                      {value === "files" && <span>{artifacts.length}</span>}
                      {value === "sources" && <span>{sources.length}</span>}
                    </button>
                  ),
                )}
              </div>
              <div
                id="task-panel"
                role="tabpanel"
                aria-labelledby={`tab-${tab}`}
              >
                {tab === "overview" && (
                  <div className="result-layout">
                    <div className="result-main">
                      {w.task && (
                        <ConversationHistory
                          task={w.task}
                          api={w.api}
                          download={w.download}
                        />
                      )}
                      {!!charts.length && (
                        <section className="result-card">
                          <header>
                            <div>
                              <BarChart3 size={17} />
                              <h2>Analysis</h2>
                            </div>
                            <span>From uploaded data</span>
                          </header>
                          {charts.map((file) => (
                            <ChartView key={file.id} file={file} api={w.api} />
                          ))}
                        </section>
                      )}
                      {report ? (
                        <section className="result-card report-card">
                          <header>
                            <div>
                              <FileText size={17} />
                              <h2>Report</h2>
                            </div>
                            <button
                              className="icon-button"
                              aria-label={`Download ${report.name}`}
                              onClick={() => void w.download(report)}
                            >
                              <ArrowDownToLine size={16} />
                            </button>
                          </header>
                          <ReportView file={report} api={w.api} />
                        </section>
                      ) : (
                        <section className="result-pending">
                          <span
                            className={
                              w.task?.status === "running"
                                ? "pending-icon"
                                : "pending-icon neutral"
                            }
                          >
                            {w.task?.status === "running" ? (
                              <LoaderCircle className="spin" size={23} />
                            ) : w.task?.status === "completed" ? (
                              <CircleCheck size={25} />
                            ) : (
                              <FileText size={25} />
                            )}
                          </span>
                          <h2>
                            {w.task?.status === "completed"
                              ? "Task completed"
                              : w.task?.status === "failed" ||
                                  w.task?.status === "canceled"
                                ? "Partial work is saved"
                                : w.task?.status === "awaiting_approval"
                                  ? "Waiting for your approval"
                                  : "The work is underway"}
                          </h2>
                          <p>
                            {finishedSummary
                              ? String(finishedSummary)
                              : w.task?.status === "queued"
                                ? "The worker will pick up this task shortly."
                                : "Reports and charts will appear here as they are created."}
                          </p>
                          {!!inputs.length && (
                            <div className="input-summary">
                              {inputs.map((file) => (
                                <span key={file.id}>
                                  <FileIcon file={file} />
                                  {file.name}
                                </span>
                              ))}
                            </div>
                          )}
                        </section>
                      )}
                    </div>
                    {w.task && (
                      <div className="conversation-composer-slot">
                        <FollowUpComposer
                          key={w.task.id}
                          task={w.task}
                          busy={w.busy}
                          send={w.followUp}
                        />
                      </div>
                    )}
                    <aside className="task-rail">
                      <section className="execution-panel">
                        <div className="rail-heading">
                          <h2>Execution</h2>
                          <span>{w.task?.usage?.steps || 0} steps</span>
                        </div>
                        <ExecutionLog
                          events={w.events}
                          status={w.task?.status}
                          compact
                        />
                        <button
                          className="text-button"
                          onClick={() => setTab("activity")}
                        >
                          Full activity
                          <ArrowRight size={14} />
                        </button>
                      </section>
                      <section className="deliverables-panel">
                        <div className="rail-heading">
                          <h2>Files</h2>
                          <span>{artifacts.length}</span>
                        </div>
                        {artifacts.length ? (
                          artifacts.map((file) => (
                            <div className="deliverable" key={file.id}>
                              <button
                                onClick={() => {
                                  setTab("files");
                                  setViewingFile(file);
                                }}
                              >
                                <FileIcon file={file} />
                                <span>
                                  <strong>{file.name}</strong>
                                  <small>{bytesLabel(file.size)}</small>
                                </span>
                              </button>
                              <button
                                className="icon-button"
                                aria-label={`Download ${file.name}`}
                                onClick={() => void w.download(file)}
                              >
                                <ArrowDownToLine size={15} />
                              </button>
                            </div>
                          ))
                        ) : (
                          <p className="muted-copy">No files generated yet.</p>
                        )}
                      </section>
                      <section className="usage-panel">
                        <h2>Run details</h2>
                        <dl>
                          <dt>Accounted tokens</dt>
                          <dd>
                            {w.task?.usage?.tokens.toLocaleString() || "0"}
                          </dd>
                          <dt>Estimated cost</dt>
                          <dd>${(w.task?.usage?.cost || 0).toFixed(4)}</dd>
                          <dt>Step budget</dt>
                          <dd>
                            {w.task?.usage?.steps || 0} /{" "}
                            {w.config?.limits.steps || "—"}
                          </dd>
                        </dl>
                        <p>
                          {w.task?.accounting_note ||
                            (w.task?.mode === "demo"
                              ? "No model calls in demo mode."
                              : "Cost uses the configured token rate.")}
                        </p>
                      </section>
                    </aside>
                  </div>
                )}
                {tab === "activity" && (
                  <section className="activity-view">
                    <div className="section-heading">
                      <div>
                        <h2>Execution timeline</h2>
                        <span>{w.events.length} events</span>
                      </div>
                      <span className="saved-label">
                        <Check size={13} /> Saved
                      </span>
                    </div>
                    <ExecutionLog events={w.events} status={w.task?.status} />
                    <details className="raw-events">
                      <summary>View all saved events</summary>
                      <pre>{JSON.stringify(w.events, null, 2)}</pre>
                    </details>
                  </section>
                )}
                {tab === "files" && (
                  <section className="files-view">
                    <div className="section-heading">
                      <div>
                        <h2>Generated files</h2>
                        <span>{artifacts.length}</span>
                      </div>
                    </div>
                    {artifacts.length ? (
                      <div className="file-grid">
                        {artifacts.map((file) => (
                          <article className="file-card" key={file.id}>
                            <button
                              className="file-card-open"
                              onClick={() => setViewingFile(file)}
                            >
                              <span
                                className={`file-format ${file.name.endsWith(".pdf") ? "pdf" : file.mime.includes("sheet") ? "sheet" : ""}`}
                              >
                                <FileIcon file={file} />
                              </span>
                              <strong>{file.name}</strong>
                              <span>
                                {file.name.split(".").pop()?.toUpperCase()}
                                <span>·</span>
                                {bytesLabel(file.size)}
                              </span>
                            </button>
                            <button
                              className="file-card-download"
                              aria-label={`Download ${file.name}`}
                              onClick={() => void w.download(file)}
                            >
                              Download
                              <ArrowDownToLine size={15} />
                            </button>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-work">
                        <FolderOpen size={23} />
                        <div>
                          <h3>No generated files yet</h3>
                          <p>Completed outputs will be saved here.</p>
                        </div>
                      </div>
                    )}
                    {viewingFile &&
                      w.task?.files?.some(
                        (file) => file.id === viewingFile.id,
                      ) && (
                        <FileViewer
                          key={viewingFile.id}
                          file={viewingFile}
                          api={w.api}
                          onClose={() => setViewingFile(null)}
                          download={w.download}
                        />
                      )}{" "}
                    {!!inputs.length && (
                      <div className="uploaded-files">
                        <h3>Input files</h3>
                        {inputs.map((file) => (
                          <button
                            key={file.id}
                            onClick={() => setViewingFile(file)}
                          >
                            <FileIcon file={file} />
                            <strong>{file.name}</strong>
                            <span>{bytesLabel(file.size)}</span>
                            <ArrowUpRight size={15} />
                          </button>
                        ))}
                      </div>
                    )}
                  </section>
                )}
                {tab === "sources" && (
                  <section className="sources-view">
                    <div className="section-heading">
                      <div>
                        <h2>Sources</h2>
                        <span>{sources.length}</span>
                      </div>
                      <span className="muted-copy">
                        Excerpts saved with this task
                      </span>
                    </div>
                    {sources.length ? (
                      sources.map((source, index) => (
                        <article className="source-card" key={source.id}>
                          <span className="source-number">
                            {String(index + 1).padStart(2, "0")}
                          </span>
                          <div>
                            <div className="source-origin">
                              <Globe2 size={13} />
                              <span>
                                {safeUrl(source.url)
                                  ? new URL(source.url).hostname
                                  : "Source"}
                              </span>
                              {source.fixture && (
                                <span className="fixture-label">
                                  Demo fixture
                                </span>
                              )}
                            </div>
                            <a
                              href={safeUrl(source.url)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <h3>
                                {source.title.replace(/ · DEMO FIXTURE$/, "")}
                              </h3>
                              <ArrowUpRight size={17} />
                            </a>
                            <blockquote>{source.excerpt}</blockquote>
                            <details>
                              <summary>Source reference</summary>
                              <code>{source.id}</code>
                            </details>
                          </div>
                        </article>
                      ))
                    ) : (
                      <div className="empty-work">
                        <Globe2 size={24} />
                        <div>
                          <h3>No external sources</h3>
                          <p>
                            Sources appear after research or webpage extraction.
                          </p>
                        </div>
                      </div>
                    )}
                  </section>
                )}
              </div>
            </>
          )}
        </main>
      </div>
      <dialog
        ref={settingsDialog}
        className="settings-dialog"
        aria-labelledby="settings-title"
        onClick={(e) => {
          if (e.target === e.currentTarget) settingsDialog.current?.close();
        }}
      >
        <div className="dialog-inner">
          <header>
            <div>
              <Settings2 size={19} />
              <h2 id="settings-title">Workspace settings</h2>
            </div>
            <button
              className="icon-button"
              aria-label="Close settings"
              onClick={() => settingsDialog.current?.close()}
            >
              <X size={20} />
            </button>
          </header>
          <section>
            <div className="settings-section-title">Connection</div>
            <dl>
              <dt>Mode</dt>
              <dd>
                {w.config?.mode === "demo"
                  ? "Demo · fixture-backed"
                  : w.config?.mode === "live"
                    ? "Live"
                    : "Unavailable"}
              </dd>
              <dt>Planner</dt>
              <dd>{w.config?.model || "Connect to view"}</dd>
              <dt>Live search</dt>
              <dd>
                {w.config
                  ? w.config.search_configured
                    ? "Configured"
                    : "Not configured"
                  : "Unavailable"}
              </dd>
            </dl>
            {w.config?.mode === "demo" && (
              <p className="settings-note">
                File analysis runs on your data. Research and browser results
                use clearly labeled fixtures.
              </p>
            )}
          </section>
          <section>
            <div className="settings-section-title">Execution limits</div>
            <div className="limit-grid">
              <div>
                <strong>{w.config?.limits.steps ?? "—"}</strong>
                <span>tool steps</span>
              </div>
              <div>
                <strong>
                  {w.config ? Math.round(w.config.limits.seconds / 60) : "—"}
                </strong>
                <span>minutes</span>
              </div>
              <div>
                <strong>${w.config?.limits.cost ?? "—"}</strong>
                <span>cost cap</span>
              </div>
            </div>
            <p className="settings-note">
              Limits and provider keys are configured on the server.
            </p>
          </section>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              w.applyToken(tokenDraft);
              setTokenDraft("");
              settingsDialog.current?.close();
            }}
          >
            <label htmlFor="access-token">Live access token</label>
            <input
              id="access-token"
              type="password"
              autoComplete="off"
              value={tokenDraft}
              onChange={(e) => setTokenDraft(e.target.value)}
              placeholder="Paste a server-issued token"
            />
            <p className="settings-note">
              Kept in memory for this session. It is cleared when you reload.
            </p>
            <div className="dialog-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  w.applyToken("");
                  setTokenDraft("");
                  settingsDialog.current?.close();
                }}
              >
                Clear session
              </button>
              <button
                className="button primary"
                type="submit"
                disabled={!tokenDraft.trim()}
              >
                Apply token
                <ArrowRight size={15} />
              </button>
            </div>
          </form>
        </div>
      </dialog>
    </div>
  );
}
