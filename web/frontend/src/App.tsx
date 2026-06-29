import {
  AlertTriangle,
  Archive,
  Files,
  FolderOpen,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Square,
  Terminal,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  collectResults,
  archiveProject,
  completeHostOnlySetup,
  continueJob,
  createProjectDraft,
  getJob,
  getSettings,
  interruptJob,
  listArtifacts,
  listJobEvents,
  listProjectJobs,
  listProjects,
  readArtifact,
  startPhaseJob,
  submitJobApproval,
  validateManuscript,
  type ArtifactContent,
  type ArtifactRecord,
  type PhaseJobResult,
  type ProjectDiscoveryResult,
  type ProjectSummary,
  type ProjectToolResult,
  type RunEvent,
  type SettingsStatus,
  type ToolStatus,
  TERMINAL_JOB_STATUSES
} from "./api";
import "./styles.css";

type View = "home" | "phase" | "artifacts" | "settings";

const EMPTY_DISCOVERY: ProjectDiscoveryResult = {
  setup_required: false,
  config_exists: false,
  projects: []
};

const TITLE_ACRONYMS = new Map([
  ["api", "API"],
  ["cpu", "CPU"],
  ["gpu", "GPU"],
  ["gui", "GUI"],
  ["lidar", "LiDAR"],
  ["pdf", "PDF"],
  ["qa", "QA"],
  ["sdk", "SDK"]
]);

function formatProjectTitle(project: ProjectSummary) {
  const source = project.project_dir || project.topic || "Project";
  return source
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      const lower = word.toLowerCase();
      return TITLE_ACRONYMS.get(lower) ?? `${lower.charAt(0).toUpperCase()}${lower.slice(1)}`;
    })
    .join(" ");
}

export default function App() {
  const [discovery, setDiscovery] = useState<ProjectDiscoveryResult>(EMPTY_DISCOVERY);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [view, setView] = useState<View>("home");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoStartProjectDir, setAutoStartProjectDir] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    listProjects()
      .then((result) => {
        if (!alive) return;
        setDiscovery(result);
        setView(result.setup_required ? "settings" : "home");
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load projects");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const activeProject = selectedProject ?? discovery.projects[0] ?? null;
  const pageTitle = useMemo(() => {
    if (view === "settings") return "Settings And Safety";
    if (view === "phase" && activeProject) return formatProjectTitle(activeProject);
    if (view === "artifacts") return "Artifact Browser";
    return "Project Home";
  }, [activeProject, view]);

  function openProject(project: ProjectSummary) {
    setSelectedProject(project);
    setAutoStartProjectDir(null);
    setView("phase");
  }

  async function startNewProject(researchIdea: string, projectName?: string) {
    const draft = await createProjectDraft(researchIdea, projectName);
    setDiscovery((current) => ({
      ...current,
      projects: [draft, ...current.projects.filter((project) => project.project_dir !== draft.project_dir)]
    }));
    setSelectedProject(draft);
    setAutoStartProjectDir(draft.project_dir);
    setView("phase");
  }

  function handleSetupComplete(status: SettingsStatus) {
    const configExists = status.repository.config_exists;
    setDiscovery((current) => ({
      ...current,
      config_exists: configExists,
      setup_required: !configExists
    }));
  }

  async function refreshProjects() {
    const previousProjects = discovery.projects;
    try {
      const result = await listProjects();
      const previousDirs = new Set(previousProjects.map((project) => project.project_dir));
      const appeared = result.projects.filter((project) => !previousDirs.has(project.project_dir));
      setDiscovery(result);
      setSelectedProject((current) => {
        if (!current) return current;
        const refreshed = result.projects.find((project) => project.project_dir === current.project_dir);
        // When a draft is finalized into a real folder, jump to the project that just appeared.
        const shouldJumpToNewProject =
          appeared.length > 0 && (!refreshed || current.project_dir.startsWith("_new_project_draft"));
        if (shouldJumpToNewProject) {
          return [...appeared].sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))[0];
        }
        return refreshed ?? current;
      });
    } catch {
      // Keep showing the last known project list if the refresh fails.
    }
  }

  async function archiveExistingProject(project: ProjectSummary) {
    const confirmed = window.confirm(
      `Archive ${project.project_dir}? The project folder and artifacts will stay on disk, but it will be hidden from the active project list.`
    );
    if (!confirmed) return;

    await archiveProject(project);
    setDiscovery((current) => ({
      ...current,
      projects: current.projects.filter((item) => item.project_dir !== project.project_dir)
    }));
    if (selectedProject?.project_dir === project.project_dir) {
      setSelectedProject(null);
      setView("home");
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand">
          <span className="brand-mark">R2</span>
          <div>
            <strong>Rev2Agent</strong>
            <span>Research workspace</span>
          </div>
        </div>
        <nav className="nav-list">
          <button className={view === "home" ? "nav-item active" : "nav-item"} onClick={() => setView("home")}>
            <FolderOpen aria-hidden="true" size={18} />
            Projects
          </button>
          <button
            className={view === "phase" ? "nav-item active" : "nav-item"}
            onClick={() => setView("phase")}
            disabled={!activeProject}
          >
            <Play aria-hidden="true" size={18} />
            Current Step
          </button>
          <button
            className={view === "artifacts" ? "nav-item active" : "nav-item"}
            onClick={() => setView("artifacts")}
            disabled={!activeProject}
          >
            <Files aria-hidden="true" size={18} />
            Files
          </button>
          <button className={view === "settings" ? "nav-item active" : "nav-item"} onClick={() => setView("settings")}>
            <Settings aria-hidden="true" size={18} />
            Settings
          </button>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{pageTitle}</h1>
          </div>
          <StatusChip label={discovery.setup_required ? "setup needed" : "ready"} tone={discovery.setup_required ? "warn" : "ok"} />
        </header>

        {error ? <ErrorBanner message={error} /> : null}
        {loading ? <div className="panel">Loading projects...</div> : null}
        {!loading && view === "home" ? (
          <ProjectHome
            projects={discovery.projects}
            setupRequired={discovery.setup_required}
            onOpen={openProject}
            onCreate={startNewProject}
            onArchive={archiveExistingProject}
          />
        ) : null}
        {!loading && view === "settings" ? (
          <SettingsSafety configExists={discovery.config_exists} onSetupComplete={handleSetupComplete} />
        ) : null}
        {!loading && view === "phase" && activeProject ? (
          <PhaseDashboard
            project={activeProject}
            setupRequired={discovery.setup_required}
            autoStart={autoStartProjectDir === activeProject.project_dir}
            onAutoStartConsumed={() => {
              setAutoStartProjectDir((current) => (current === activeProject.project_dir ? null : current));
            }}
            onArtifacts={() => setView("artifacts")}
            onSettings={() => setView("settings")}
            onProjectRefresh={refreshProjects}
          />
        ) : null}
        {!loading && view === "artifacts" && activeProject ? <ArtifactBrowser project={activeProject} /> : null}
      </section>
    </main>
  );
}

function ProjectHome({
  projects,
  setupRequired,
  onOpen,
  onCreate,
  onArchive
}: {
  projects: ProjectSummary[];
  setupRequired: boolean;
  onOpen: (project: ProjectSummary) => void;
  onCreate: (researchIdea: string, projectName?: string) => Promise<void>;
  onArchive: (project: ProjectSummary) => Promise<void>;
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [researchIdea, setResearchIdea] = useState("");
  const [projectName, setProjectName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [archiveMessage, setArchiveMessage] = useState<string | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (setupRequired) {
      setCreateError("Complete Phase 0 setup in Settings before starting a project.");
      return;
    }
    const trimmedIdea = researchIdea.trim();
    if (!trimmedIdea) {
      setCreateError("Research idea is required.");
      return;
    }

    setCreating(true);
    setCreateError(null);
    try {
      await onCreate(trimmedIdea, projectName.trim());
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  }

  const createForm = showCreateForm ? (
    <form className="create-project-form" onSubmit={submitProject}>
      <label htmlFor="research-idea">Research idea</label>
      <textarea
        id="research-idea"
        value={researchIdea}
        onChange={(event) => {
          setResearchIdea(event.target.value);
          if (createError) setCreateError(null);
        }}
        placeholder="Describe the research direction, dataset, downstream task, and success metric."
        rows={5}
      />
      <label htmlFor="project-name">Project folder name (optional)</label>
      <input
        id="project-name"
        type="text"
        value={projectName}
        onChange={(event) => {
          setProjectName(event.target.value);
          if (createError) setCreateError(null);
        }}
        placeholder="e.g. gui_qa_tiny_sentiment - leave blank to start an unnamed draft"
      />
      {createError ? (
        <p className="warning-text" role="alert">
          {createError}
        </p>
      ) : null}
      <div className="action-row">
        <button className="primary-button" type="submit" disabled={creating || setupRequired}>
          <Plus aria-hidden="true" size={18} />
          Create Project
        </button>
        <button className="secondary-button" type="button" onClick={() => setShowCreateForm(false)} disabled={creating}>
          Cancel
        </button>
      </div>
    </form>
  ) : null;

  if (projects.length === 0) {
    return (
      <section className="panel">
        <h2>No projects yet</h2>
        <p>Start a new research project with the initial idea Rev2Agent should refine in Phase 1.</p>
        {setupRequired ? (
          <p className="warning-text">Complete Phase 0 setup in Settings before starting a project.</p>
        ) : null}
        {archiveMessage ? <p className="job-message">{archiveMessage}</p> : null}
        {archiveError ? (
          <p className="warning-text" role="alert">
            {archiveError}
          </p>
        ) : null}
        <button className="primary-button" onClick={() => setShowCreateForm(true)} disabled={setupRequired}>
          <Plus aria-hidden="true" size={18} />
          Start New Project
        </button>
        {createForm}
      </section>
    );
  }

  return (
    <section className="project-home">
      <div className="section-toolbar">
        <h2>Existing Projects</h2>
        <button className="primary-button" onClick={() => setShowCreateForm(true)} disabled={setupRequired}>
          <Plus aria-hidden="true" size={18} />
          Start New Project
        </button>
      </div>
      {setupRequired ? <p className="warning-text">Complete Phase 0 setup in Settings before starting a project.</p> : null}
      {archiveMessage ? <p className="job-message">{archiveMessage}</p> : null}
      {archiveError ? (
        <p className="warning-text" role="alert">
          {archiveError}
        </p>
      ) : null}
      {createForm ? <section className="panel">{createForm}</section> : null}
      <div className="project-grid" aria-label="Existing research projects">
        {projects.map((project) => (
          <article className="project-card" key={project.project_dir}>
            <div className="project-card-status">
              <StatusChip label={project.phase_status} tone={project.healthy ? "ok" : "warn"} />
            </div>
            <div className="card-head">
              <div className="project-card-title">
                <h2>{project.project_dir}</h2>
                <p>{project.topic || "Topic not set yet"}</p>
              </div>
            </div>
            <div className="phase-row">
              <strong>{project.phase_label}</strong>
              <span>Phase {project.phase ?? "?"}</span>
            </div>
            <dl className="meta-grid">
              <div>
                <dt>Project</dt>
                <dd>{project.project_status}</dd>
              </div>
              <div>
                <dt>Last updated</dt>
                <dd>{formatProjectTimestamp(project.updated_at)}</dd>
              </div>
              <div>
                <dt>Active runs</dt>
                <dd>{project.active_runs}</dd>
              </div>
            </dl>
            {!project.healthy ? <p className="warning-text">{project.health_message}</p> : null}
            <div className="project-card-actions">
              <button className="primary-button" onClick={() => onOpen(project)} aria-label={`Open ${project.project_dir}`}>
                <FolderOpen aria-hidden="true" size={18} />
                Open
              </button>
              <button
                className="secondary-button danger-button"
                onClick={async () => {
                  setArchiveMessage(null);
                  setArchiveError(null);
                  try {
                    await onArchive(project);
                    setArchiveMessage("Project archived.");
                  } catch (err) {
                    setArchiveError(err instanceof Error ? err.message : "Failed to archive project.");
                  }
                }}
                aria-label={`Archive ${project.project_dir}`}
              >
                <Archive aria-hidden="true" size={18} />
                Archive
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function defaultPhasePrompt(project: ProjectSummary) {
  const basePrompt = `Run Rev2Agent ${project.phase_label} for ${project.project_dir}`;
  const topic = project.topic.trim();
  if (project.phase === 1 && topic) {
    return `${basePrompt}. Initial research idea: ${topic}`;
  }
  return basePrompt;
}

function formatProjectTimestamp(timestamp: string | null) {
  if (!timestamp) return "Unknown";
  // Backend timestamps are UTC; treat suffix-less strings as UTC and render local time.
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  const date = new Date(hasTimezone ? timestamp : `${timestamp}Z`);
  if (Number.isNaN(date.getTime())) return timestamp;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`;
}

interface PendingApproval {
  result: PhaseJobResult;
  action: string;
  prompt: string;
}

interface SubmittedPrompt {
  id: number;
  text: string;
}

const WAITING_JOB_STATUSES = ["waiting_for_approval", "waiting_to_continue"];

function jobStatusMessage(status: string) {
  if (status === "queued" || status === "running") return "Rev2Agent is working now.";
  if (status === "completed" || status === "rejected") return "Rev2Agent is waiting for your next prompt.";
  if (status === "interrupted") return "Rev2Agent stopped. You can revise the prompt and run the step again.";
  if (status === "failed") return "Rev2Agent hit an error. Review the latest message and try again.";
  if (status === "cancelled") return "Rev2Agent stopped before finishing.";
  if (WAITING_JOB_STATUSES.includes(status)) {
    return "Rev2Agent is waiting for approval. Press Stop to clear this waiting job, then run the step again.";
  }
  return "Rev2Agent is waiting for your next prompt.";
}

function PhaseDashboard({
  project,
  setupRequired,
  autoStart,
  onAutoStartConsumed,
  onArtifacts,
  onSettings,
  onProjectRefresh
}: {
  project: ProjectSummary;
  setupRequired: boolean;
  autoStart: boolean;
  onAutoStartConsumed: () => void;
  onArtifacts: () => void;
  onSettings: () => void;
  onProjectRefresh: () => Promise<void> | void;
}) {
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobStatus, setActiveJobStatus] = useState<string | null>(null);
  const [jobRunning, setJobRunning] = useState(false);
  const [runToken, setRunToken] = useState(0);
  const [artifactRefreshToken, setArtifactRefreshToken] = useState(0);
  const [launching, setLaunching] = useState(false);
  const launchInFlight = useRef(false);
  const [settings, setSettings] = useState<SettingsStatus | null>(null);
  const [showInstallCommand, setShowInstallCommand] = useState(false);
  const [phaseInstruction, setPhaseInstruction] = useState("");
  const [refreshingSettings, setRefreshingSettings] = useState(false);
  const [submittedPrompt, setSubmittedPrompt] = useState<SubmittedPrompt | null>(null);
  const submittedPromptId = useRef(0);
  const autoStartedProjectDir = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    getSettings()
      .then((status) => {
        if (alive) setSettings(status);
      })
      .catch(() => {
        // Environment checks are advisory; the dashboard still works without them.
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    // Reconcile with the backend: adopt a job that is already active for this
    // project (e.g. after a page reload) so it can be observed and stopped.
    let alive = true;
    setActiveJobId(null);
    setActiveJobStatus(null);
    setJobRunning(false);
    setJobMessage(null);
    setPendingApproval(null);
    if (autoStart) return;
    listProjectJobs(project, true)
      .then((jobs) => {
        if (!alive || jobs.length === 0) return;
        const job = jobs[0];
        setActiveJobId(job.job_id);
        setActiveJobStatus(job.status);
        setRunToken((token) => token + 1);
        if (WAITING_JOB_STATUSES.includes(job.status)) {
          // The original approval prompt is not persisted server-side, so the
          // dialog cannot be restored; guide the user to Stop and rerun.
          setJobRunning(false);
          setJobMessage(jobStatusMessage(job.status));
        } else {
          setJobRunning(!TERMINAL_JOB_STATUSES.includes(job.status));
          setJobMessage(jobStatusMessage(job.status));
        }
      })
      .catch(() => {
        // Reconciliation is best-effort; the dashboard still works without it.
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.project_dir]);

  const needsPhaseSevenLatexChoice = project.phase === 7 && settings?.tools.latex.available === false;

  function refreshProjectOutputs() {
    setArtifactRefreshToken((token) => token + 1);
    void onProjectRefresh();
  }

  function beginTrackingJob(result: PhaseJobResult) {
    setActiveJobId(result.job_id);
    setActiveJobStatus(result.status);
    setJobRunning(!TERMINAL_JOB_STATUSES.includes(result.status));
    setRunToken((token) => token + 1);
    setJobMessage(jobStatusMessage(result.status));
    if (TERMINAL_JOB_STATUSES.includes(result.status)) {
      refreshProjectOutputs();
    }
  }

  function recordSubmittedPrompt(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    submittedPromptId.current += 1;
    setSubmittedPrompt({ id: submittedPromptId.current, text: trimmed });
  }

  async function launch(action: string, prompt?: string, promptEcho?: string) {
    if (launchInFlight.current) return;
    launchInFlight.current = true;
    setLaunching(true);
    setJobMessage(null);
    const userPrompt = phaseInstruction.trim();
    const promptToRun = prompt ?? (userPrompt || defaultPhasePrompt(project));
    const echoText = promptEcho ?? (userPrompt || `Run ${project.phase_label}.`);
    recordSubmittedPrompt(echoText);
    try {
      const result = await startPhaseJob(project, action, promptToRun);
      if (result.requires_approval) {
        setPendingApproval({ result, action, prompt: promptToRun });
      } else {
        setPendingApproval(null);
        setPhaseInstruction("");
        beginTrackingJob(result);
      }
    } catch (err) {
      setJobMessage(err instanceof Error ? err.message : "Failed to start the phase job.");
    } finally {
      launchInFlight.current = false;
      setLaunching(false);
    }
  }

  function sendPrompt() {
    void launch(`Continue ${project.phase_label}`);
  }

  function handlePromptKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || (!event.ctrlKey && !event.metaKey)) return;
    event.preventDefault();
    sendPrompt();
  }

  function handleJobStatus(_statusJobId: string, status: string) {
    setActiveJobStatus(status);
    if (TERMINAL_JOB_STATUSES.includes(status)) {
      setJobRunning(false);
      setJobMessage(jobStatusMessage(status));
      refreshProjectOutputs();
      return;
    }
    if (WAITING_JOB_STATUSES.includes(status)) {
      setJobRunning(false);
      setJobMessage(jobStatusMessage(status));
    }
  }

  async function skipPdfCompile() {
    await launch(
      "Skip PDF Compile",
      `Run Rev2Agent ${project.phase_label} for ${project.project_dir}. Tectonic is not installed, so skip PDF compilation. Draft or update the LaTeX manuscript sources, keep references consistent, and tell the user to install Tectonic before rerunning PDF compilation.`,
      "Skip PDF compilation and continue drafting."
    );
  }

  async function refreshSettingsChecks() {
    setRefreshingSettings(true);
    setJobMessage(null);
    try {
      const status = await getSettings();
      setSettings(status);
    } catch (err) {
      setJobMessage(err instanceof Error ? err.message : "Failed to refresh environment checks.");
    } finally {
      setRefreshingSettings(false);
    }
  }

  async function approveJob() {
    if (!pendingApproval || approvalBusy) return;
    setApprovalBusy(true);
    try {
      await submitJobApproval(pendingApproval.result.job_id, "approved");
      // Continue with the exact action and prompt the user approved.
      const continued = await continueJob(
        pendingApproval.result.job_id,
        pendingApproval.action,
        pendingApproval.prompt
      );
      setPendingApproval(null);
      setPhaseInstruction("");
      beginTrackingJob(continued);
    } catch (err) {
      setJobMessage(err instanceof Error ? err.message : "Failed to approve the job.");
      setPendingApproval(null);
    } finally {
      setApprovalBusy(false);
    }
  }

  async function rejectApproval() {
    if (!pendingApproval || approvalBusy) return;
    setApprovalBusy(true);
    try {
      await submitJobApproval(pendingApproval.result.job_id, "rejected");
      setJobMessage(jobStatusMessage("rejected"));
    } catch (err) {
      setJobMessage(err instanceof Error ? err.message : "Failed to reject the job.");
    } finally {
      setApprovalBusy(false);
      setPendingApproval(null);
    }
  }

  const canStopJob =
    activeJobId !== null && activeJobStatus !== null && !TERMINAL_JOB_STATUSES.includes(activeJobStatus);

  async function interruptActiveJob() {
    if (!activeJobId) return;
    try {
      const result = await interruptJob(activeJobId);
      if (result.interrupted) {
        setActiveJobStatus("interrupted");
        setJobRunning(false);
      }
      setJobMessage(
        result.interrupted
          ? jobStatusMessage("interrupted")
          : "Rev2Agent could not be stopped. It may already have finished."
      );
    } catch (err) {
      setJobMessage(err instanceof Error ? err.message : "Failed to interrupt the job.");
    }
  }

  useEffect(() => {
    if (!autoStart || setupRequired || project.phase !== 1) return;
    if (autoStartedProjectDir.current === project.project_dir) return;
    autoStartedProjectDir.current = project.project_dir;
    onAutoStartConsumed();
    void launch(
      `Continue ${project.phase_label}`,
      undefined,
      project.topic ? `Research idea: ${project.topic}` : `Start ${project.phase_label}.`
    );
    // Auto-start is intentionally tied to the project identity, not to each
    // render of the launch helper.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, setupRequired, project.project_dir, project.phase]);

  return (
    <section className="dashboard">
      <section className="panel phase-panel" aria-label="Current step">
        <div className="phase-title">
          <h2>{project.phase_label}</h2>
          <StatusChip label={project.phase_status} tone="ok" />
        </div>
        {project.topic ? (
          <p className="project-topic">
            <strong>Research idea</strong>
            {project.topic}
          </p>
        ) : null}
        {setupRequired ? (
          <p className="warning-text">Complete Phase 0 setup in Settings before running project steps.</p>
        ) : null}
        <LiveRunConsole
          key={project.project_dir}
          projectDir={project.project_dir}
          jobId={activeJobId}
          runToken={runToken}
          running={jobRunning}
          submittedPrompt={submittedPrompt}
          embedded
          onJobStatus={handleJobStatus}
        />
        <div className="phase-instruction-form">
          <label htmlFor="phase-instruction">Prompt</label>
          <textarea
            id="phase-instruction"
            value={phaseInstruction}
            onChange={(event) => setPhaseInstruction(event.target.value)}
            onKeyDown={handlePromptKeyDown}
            placeholder="Answer Rev2Agent's latest question or add instructions for the next run."
            rows={4}
          />
        </div>
        {needsPhaseSevenLatexChoice ? (
          <div className="dependency-callout" aria-label="Missing PDF compiler options">
            <div>
              <h3>PDF compiler missing</h3>
              <p className="plain-copy">
                Tectonic is needed to compile the Phase 7 manuscript PDF. You can install it now, open Settings for the
                persistent guidance, or continue drafting without a PDF build.
              </p>
            </div>
            <div className="action-row">
              <button className="secondary-button" onClick={() => setShowInstallCommand((current) => !current)}>
                <Terminal aria-hidden="true" size={18} />
                Show Install Command
              </button>
              <button className="secondary-button" onClick={onSettings}>
                <Settings aria-hidden="true" size={18} />
                Open Settings
              </button>
              <button className="primary-button" onClick={skipPdfCompile} disabled={launching || setupRequired}>
                <Play aria-hidden="true" size={18} />
                Skip PDF Compile
              </button>
            </div>
            {showInstallCommand && settings ? (
              <TectonicInstallHelp
                platform={settings.environment.platform}
                repositoryRoot={settings.repository.root}
                embedded
                onRefresh={refreshSettingsChecks}
                refreshing={refreshingSettings}
              />
            ) : null}
          </div>
        ) : null}
        <div className="action-row">
          <button
            className="primary-button"
            onClick={sendPrompt}
            disabled={launching || setupRequired}
          >
            <Play aria-hidden="true" size={18} />
            Send
          </button>
          <button className="secondary-button" onClick={interruptActiveJob} disabled={!canStopJob}>
            <Square aria-hidden="true" size={18} />
            Stop
          </button>
        </div>
        {jobMessage ? <p className="job-message">{jobMessage}</p> : null}
        {pendingApproval ? (
          <ApprovalDialog
            approval={pendingApproval.result}
            busy={approvalBusy}
            onApprove={approveJob}
            onReject={rejectApproval}
          />
        ) : null}
      </section>
      <LatestArtifactPreview project={project} refreshToken={artifactRefreshToken} onArtifacts={onArtifacts} />
    </section>
  );
}

function ApprovalDialog({
  approval,
  busy,
  onApprove,
  onReject
}: {
  approval: PhaseJobResult;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="modal-backdrop">
      <section className="approval-dialog" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <h2 id="approval-title">Approval Required</h2>
        <p>{approval.message}</p>
        <dl className="settings-list">
          <div>
            <dt>Job</dt>
            <dd>{approval.job_id}</dd>
          </div>
          <div>
            <dt>Sandbox</dt>
            <dd>{approval.sandbox}</dd>
          </div>
        </dl>
        <div className="action-row">
          <button className="secondary-button" onClick={onReject} disabled={busy}>
            Reject
          </button>
          <button className="primary-button" onClick={onApprove} disabled={busy}>
            Approve High-Risk Action
          </button>
        </div>
      </section>
    </div>
  );
}

interface ConsoleEvent extends RunEvent {
  isDeltaAccumulator?: boolean;
  displayRole?: "assistant" | "user" | "notice" | "error" | "status";
}

const MAX_CONSOLE_EVENTS = 300;
const CONSOLE_HISTORY_PREFIX = "rev2agent.console.";

function formatElapsedTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function consoleHistoryKey(projectDir: string) {
  return `${CONSOLE_HISTORY_PREFIX}${projectDir}`;
}

function readConsoleHistory(projectDir: string): ConsoleEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(consoleHistoryKey(projectDir));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (event): event is ConsoleEvent =>
          event &&
          typeof event === "object" &&
          typeof event.event_type === "string" &&
          typeof event.summary === "string"
      )
      .slice(-MAX_CONSOLE_EVENTS);
  } catch {
    return [];
  }
}

function writeConsoleHistory(projectDir: string, events: ConsoleEvent[]) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(consoleHistoryKey(projectDir), JSON.stringify(events.slice(-MAX_CONSOLE_EVENTS)));
  } catch {
    // Console history is a convenience; storage failures should not break runs.
  }
}

function isAgentMessageEventType(eventType: string) {
  const compact = eventType.toLowerCase().replace(/[-_/]/g, "");
  return compact.includes("agentmessage") || compact.includes("assistantmessage");
}

function rawPayloadLooksLikeAssistantMessage(event: RunEvent) {
  const rawPayload = event.raw_payload_json?.toLowerCase() ?? "";
  return rawPayload.includes("agentmessagethreaditem") || rawPayload.includes("assistantmessage");
}

function normalizeAssistantText(text: string) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\u2018|\u2019/g, "'")
    .replace(/\u201c|\u201d/g, '"')
    .trim();
}

function isOperationalAssistantLine(line: string) {
  const normalized = normalizeAssistantText(line).toLowerCase();
  return [
    "job completed but the project state did not change",
    "run finished. rev2agent is waiting",
    "using `systematic-debugging`",
    "using systematic-debugging",
    "i'll use the `using-superpowers` skill",
    "i'll use the using-superpowers skill",
    "i found the local phase",
    "i'm updating only",
    "timestamp command used",
    "powershell option not available",
    "i'm editing only the research state",
    "the state update is in place",
    "recorded:",
    "root cause is powershell",
    "no phase transition yet"
  ].some((phrase) => normalized.includes(phrase));
}

function extractUserQuestion(text: string) {
  const lines = normalizeAssistantText(text)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const questionStart = lines.findIndex((line) =>
    /^next\s+(?:phase\s+\d+\s+)?(?:interview\s+)?question\s*:/i.test(line)
  );
  if (questionStart < 0) return null;

  const questionLines: string[] = [];
  for (let index = questionStart; index < lines.length; index += 1) {
    const line = lines[index];
    if (index > questionStart && isOperationalAssistantLine(line)) break;
    questionLines.push(line);
  }
  return questionLines.join("\n").trim() || null;
}

function userFacingAssistantSummary(summary: string) {
  const normalized = normalizeAssistantText(summary);
  const question = extractUserQuestion(normalized);
  if (question) return question;
  if (isOperationalAssistantLine(normalized)) return null;
  if (/^(got it|question|next question)\s*:/i.test(normalized)) return normalized;
  if (/\?\s*$/.test(normalized)) return normalized;
  return normalized;
}

function toDisplayConsoleEvent(event: RunEvent): ConsoleEvent | null {
  const eventType = event.event_type || "";
  const normalizedType = eventType.toLowerCase();
  const isAgentDelta = normalizedType.includes("delta") && isAgentMessageEventType(eventType);
  if (isAgentDelta) {
    return { ...event, displayRole: "assistant", isDeltaAccumulator: true };
  }

  const trimmedSummary = event.summary.trim();
  if (!trimmedSummary) return null;

  if (
    normalizedType === "assistant_message" ||
    (!normalizedType.includes("delta") && isAgentMessageEventType(eventType)) ||
    (normalizedType === "item/completed" && rawPayloadLooksLikeAssistantMessage(event))
  ) {
    const displaySummary = userFacingAssistantSummary(trimmedSummary);
    if (!displaySummary) return null;
    return { ...event, summary: displaySummary, displayRole: "assistant" };
  }

  if (normalizedType === "completion_warning" || normalizedType === "interrupt_note") {
    return null;
  }

  if (["error", "failed", "cancelled", "stream_error"].includes(normalizedType)) {
    return { ...event, summary: trimmedSummary, displayRole: "error" };
  }

  return null;
}

function appendEventToConsole(current: ConsoleEvent[], event: ConsoleEvent) {
  if (event.isDeltaAccumulator) {
    const last = current[current.length - 1];
    if (last?.isDeltaAccumulator) {
      return [...current.slice(0, -1), { ...last, summary: last.summary + event.summary }].slice(-MAX_CONSOLE_EVENTS);
    }
    return [...current, event].slice(-MAX_CONSOLE_EVENTS);
  }

  const last = current[current.length - 1];
  const base = event.displayRole === "assistant" && last?.isDeltaAccumulator ? current.slice(0, -1) : current;
  return [...base, event].slice(-MAX_CONSOLE_EVENTS);
}

function LiveRunConsole({
  projectDir,
  jobId,
  runToken,
  running,
  submittedPrompt,
  embedded = false,
  onJobStatus
}: {
  projectDir: string;
  jobId: string | null;
  runToken: number;
  running: boolean;
  submittedPrompt: SubmittedPrompt | null;
  embedded?: boolean;
  onJobStatus: (jobId: string, status: string) => void;
}) {
  const [events, setEvents] = useState<ConsoleEvent[]>(() => readConsoleHistory(projectDir));
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const listRef = useRef<HTMLOListElement | null>(null);
  const onJobStatusRef = useRef(onJobStatus);
  onJobStatusRef.current = onJobStatus;

  function appendDisplayEvent(event: ConsoleEvent) {
    setEvents((current) => appendEventToConsole(current, event));
  }

  function appendConsoleEvent(parsed: RunEvent) {
    const displayEvent = toDisplayConsoleEvent(parsed);
    if (!displayEvent) return;
    appendDisplayEvent(displayEvent);
  }

  function clearConsole() {
    setEvents([]);
  }

  useEffect(() => {
    setElapsedSeconds(0);
  }, [projectDir]);

  useEffect(() => {
    writeConsoleHistory(projectDir, events);
  }, [events, projectDir]);

  useEffect(() => {
    if (!submittedPrompt) return;
    appendDisplayEvent({
      event_type: "user_prompt",
      summary: `You: ${submittedPrompt.text}`,
      displayRole: "user"
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submittedPrompt?.id]);

  useEffect(() => {
    setElapsedSeconds(0);
    if (!jobId) return;

    const currentJobId = jobId;
    // The browser may reconnect and replay events; track ids so each shows once.
    const seenEventIds = new Set<number>();
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let done = false;
    const startedAt = Date.now();

    const elapsedTimer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    // Poll fallback: if the SSE stream is lost, job completion is still noticed.
    const pollTimer = setInterval(() => {
      getJob(currentJobId)
        .then((job) => {
          if (TERMINAL_JOB_STATUSES.includes(job.status)) finish(job.status);
        })
        .catch(() => {
          // Polling is a fallback; ignore transient failures and retry next tick.
        });
    }, 5000);

    function finish(status: string) {
      if (done) return;
      done = true;
      source?.close();
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      clearInterval(pollTimer);
      clearInterval(elapsedTimer);
      void drainTailEventsThenNotify(status);
    }

    async function drainTailEventsThenNotify(status: string) {
      try {
        // Tail events (completion_warning, interrupt_note, error) can be
        // written during finalization after the stream closes; fetch and
        // render any the stream missed before reporting the final status.
        const remaining = await listJobEvents(currentJobId);
        for (const event of remaining) {
          if (typeof event.event_id === "number") {
            if (seenEventIds.has(event.event_id)) continue;
            seenEventIds.add(event.event_id);
          }
          appendConsoleEvent(event);
        }
      } catch {
        // The drain is best-effort; the status notification must still fire.
      }
      onJobStatusRef.current(currentJobId, status);
    }

    function connect() {
      if (done) return;
      const nextSource = new EventSource(`/api/jobs/${encodeURIComponent(currentJobId)}/events/stream`);
      source = nextSource;
      nextSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as RunEvent;
          if (parsed.event_type === "job_status") {
            if (parsed.status) {
              finish(parsed.status);
            } else {
              nextSource.close();
            }
            return;
          }
          if (typeof parsed.event_id === "number") {
            if (seenEventIds.has(parsed.event_id)) return;
            seenEventIds.add(parsed.event_id);
          }
          appendConsoleEvent(parsed);
        } catch {
          appendDisplayEvent({
            event_type: "stream_error",
            summary: "A job event could not be displayed.",
            displayRole: "error"
          });
        }
      };
      nextSource.onerror = () => {
        // The dev-server proxy answers 502 while the backend restarts; the browser
        // EventSource then gives up permanently, so reconnect manually.
        if (nextSource.readyState === EventSource.CLOSED) {
          nextSource.close();
          reconnectTimer = setTimeout(connect, 2000);
        }
      };
    }
    connect();

    return () => {
      done = true;
      source?.close();
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      clearInterval(pollTimer);
      clearInterval(elapsedTimer);
    };
  }, [jobId, runToken]);

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [events]);

  return (
    <section
      className={embedded ? "console-panel embedded-console-panel" : "panel console-panel"}
      aria-label="Live run console"
    >
      <div className="section-toolbar console-toolbar">
        <div className="panel-heading">
          <Terminal aria-hidden="true" size={18} />
          <h2>Live Run Console</h2>
          {running ? <span className="elapsed-label">{formatElapsedTime(elapsedSeconds)}</span> : null}
        </div>
        <button className="secondary-button compact-button" type="button" onClick={clearConsole} disabled={events.length === 0}>
          <Trash2 aria-hidden="true" size={16} />
          Clear
        </button>
      </div>
      <ol className="event-list" ref={listRef}>
        {events.length > 0 ? (
          events.map((event, index) => (
            <li className={event.displayRole ? `console-event ${event.displayRole}` : "console-event"} key={`${event.event_id ?? event.event_type}-${index}`}>
              <span className="event-dot" />
              {event.summary}
            </li>
          ))
        ) : (
          <li>
            <span className="event-dot" />
            {jobId ? "Listening for job events." : "No conversation yet. Run a step to start."}
          </li>
        )}
      </ol>
    </section>
  );
}

function LatestArtifactPreview({
  project,
  refreshToken,
  onArtifacts
}: {
  project: ProjectSummary;
  refreshToken: number;
  onArtifacts: () => void;
}) {
  const [latestArtifact, setLatestArtifact] = useState<ArtifactRecord | null>(null);
  const [preview, setPreview] = useState<ArtifactContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setLatestArtifact(null);
    setPreview(null);

    listArtifacts(project)
      .then(async (items) => {
        if (!alive) return;
        const latest = [...items].sort((a, b) => b.artifact_id - a.artifact_id)[0] ?? null;
        setLatestArtifact(latest);
        if (!latest) return;

        const content = await readArtifact(project, latest.artifact_id);
        if (alive) setPreview(content);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "Failed to load the latest artifact.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [project, refreshToken]);

  return (
    <section className="panel latest-artifact-panel" aria-label="Latest artifact preview">
      <div className="section-toolbar">
        <div className="panel-heading">
          <Files aria-hidden="true" size={18} />
          <h2>Latest Artifact</h2>
        </div>
        <button className="secondary-button" onClick={onArtifacts}>
          <Files aria-hidden="true" size={18} />
          Open Files
        </button>
      </div>
      {loading ? <p className="plain-copy">Loading latest artifact...</p> : null}
      {!loading && error ? (
        <p className="warning-text" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && !error && !latestArtifact ? <p className="plain-copy">No artifacts yet.</p> : null}
      {latestArtifact ? (
        <>
          <div className="latest-artifact-meta">
            <strong>{latestArtifact.title}</strong>
            <span>{latestArtifact.path}</span>
          </div>
          <div className="artifact-preview latest-artifact-preview" aria-label="Latest artifact content">
            {preview ? <ArtifactPreviewContent preview={preview} /> : <p className="plain-copy">Loading preview...</p>}
          </div>
        </>
      ) : null}
    </section>
  );
}

function ArtifactBrowser({ project }: { project: ProjectSummary }) {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [preview, setPreview] = useState<ArtifactContent | null>(null);
  const [toolMessage, setToolMessage] = useState<string | null>(null);
  const [loadingArtifacts, setLoadingArtifacts] = useState(true);
  const [activeTab, setActiveTab] = useState<(typeof ARTIFACT_TABS)[number]["label"]>("Summaries");

  useEffect(() => {
    let alive = true;
    setLoadingArtifacts(true);
    listArtifacts(project)
      .then((items) => {
        if (alive) setArtifacts(items);
      })
      .catch((err: unknown) => {
        if (alive) setToolMessage(err instanceof Error ? err.message : "Failed to load artifacts.");
      })
      .finally(() => {
        if (alive) setLoadingArtifacts(false);
      });
    return () => {
      alive = false;
    };
  }, [project]);

  async function openArtifact(artifact: ArtifactRecord) {
    try {
      setPreview(await readArtifact(project, artifact.artifact_id));
    } catch (err) {
      setToolMessage(err instanceof Error ? err.message : "Failed to read the artifact.");
    }
  }

  function selectArtifactTab(tab: (typeof ARTIFACT_TABS)[number]["label"]) {
    setActiveTab(tab);
    setPreview(null);
  }

  function describeToolResult(label: string, result: ProjectToolResult) {
    if (result.status !== "failed") return `${label} ${result.status}`;
    const detail = (result.stderr || result.stdout || "").trim().slice(0, 400);
    return detail ? `${label} failed: ${detail}` : `${label} failed`;
  }

  async function runCollectResults() {
    try {
      const result = await collectResults(project);
      if (result.artifacts) setArtifacts(result.artifacts);
      setToolMessage(describeToolResult("Result collection", result));
    } catch (err) {
      setToolMessage(err instanceof Error ? err.message : "Failed to collect results.");
    }
  }

  async function runValidateManuscript() {
    try {
      const result = await validateManuscript(project);
      if (result.artifacts) setArtifacts(result.artifacts);
      setToolMessage(describeToolResult("Manuscript validation", result));
    } catch (err) {
      setToolMessage(err instanceof Error ? err.message : "Failed to validate the manuscript.");
    }
  }

  const activeTabConfig = ARTIFACT_TABS.find((tab) => tab.label === activeTab) ?? ARTIFACT_TABS[0];
  const filteredArtifacts = artifacts.filter((artifact) =>
    (activeTabConfig.types as readonly string[]).includes(artifact.artifact_type)
  );

  return (
    <section className="panel">
      <div className="section-toolbar">
        <div className="panel-heading">
          <Files aria-hidden="true" size={18} />
          <h2>Artifact Browser</h2>
        </div>
        <div className="action-row">
          <button className="secondary-button" onClick={runCollectResults}>
            Collect Results
          </button>
          <button className="secondary-button" onClick={runValidateManuscript}>
            Validate Manuscript
          </button>
        </div>
      </div>
      {toolMessage ? <p className="job-message">{toolMessage}</p> : null}
      <div className="tab-row" role="tablist" aria-label="Artifact categories">
        {ARTIFACT_TABS.map((tab) => (
          <button
            className="tab-button"
            key={tab.label}
            role="tab"
            aria-selected={tab.label === activeTab}
            onClick={() => selectArtifactTab(tab.label)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {loadingArtifacts ? <p className="plain-copy">Loading artifacts for {project.project_dir}...</p> : null}
      {!loadingArtifacts ? (
        <div className="artifact-layout">
          <ul className="artifact-list" aria-label="Artifacts">
            {filteredArtifacts.map((artifact) => (
              <li key={artifact.artifact_id}>
                <div>
                  <strong>{artifact.title}</strong>
                  <span>{artifact.path}</span>
                </div>
                <button className="secondary-button" onClick={() => openArtifact(artifact)} aria-label={`Open ${artifact.title}`}>
                  Open
                </button>
              </li>
            ))}
            {filteredArtifacts.length === 0 ? (
              <li className="empty-artifact-row">No {activeTab.toLowerCase()} artifacts yet.</li>
            ) : null}
          </ul>
          <div className="artifact-preview" aria-label="Artifact preview">
            <ArtifactPreviewContent preview={preview} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ArtifactPreviewContent({ preview }: { preview: ArtifactContent | null }) {
  const [mode, setMode] = useState<"markdown" | "raw">("markdown");

  useEffect(() => {
    setMode("markdown");
  }, [preview?.artifact_id]);

  if (!preview) {
    return <p className="plain-copy">Select an artifact to preview safe content.</p>;
  }

  if (preview.kind === "binary") {
    return <p>Binary preview: {preview.mime_type}</p>;
  }

  const content = preview.content ?? "";
  if (!isMarkdownPreview(preview)) {
    return <pre>{content}</pre>;
  }

  return (
    <div className="artifact-preview-content">
      <div className="preview-mode-toggle" role="group" aria-label="Preview mode">
        <button
          className={mode === "markdown" ? "toggle-button active" : "toggle-button"}
          onClick={() => setMode("markdown")}
          type="button"
        >
          Markdown
        </button>
        <button className={mode === "raw" ? "toggle-button active" : "toggle-button"} onClick={() => setMode("raw")} type="button">
          Raw
        </button>
      </div>
      {mode === "markdown" ? (
        <div className="markdown-preview">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      ) : (
        <pre>{content}</pre>
      )}
    </div>
  );
}

function isMarkdownPreview(preview: ArtifactContent) {
  return preview.mime_type === "text/markdown" || preview.mime_type === "text/x-markdown";
}

const ARTIFACT_TABS = [
  { label: "Summaries", types: ["summary"] },
  { label: "Literature", types: ["literature"] },
  { label: "Experiments", types: ["experiment_config", "log"] },
  { label: "Results", types: ["result"] },
  { label: "Manuscript", types: ["manuscript", "pdf", "table"] },
  { label: "Figures", types: ["figure"] }
] as const;

function SettingsSafety({
  configExists,
  onSetupComplete
}: {
  configExists: boolean;
  onSetupComplete: (status: SettingsStatus) => void;
}) {
  const [settings, setSettings] = useState<SettingsStatus | null>(null);
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [refreshingChecks, setRefreshingChecks] = useState(false);

  useEffect(() => {
    let alive = true;
    getSettings()
      .then((status) => {
        if (alive) setSettings(status);
      })
      .catch((err: unknown) => {
        if (alive) setSetupError(err instanceof Error ? err.message : "Failed to load environment checks.");
      });
    return () => {
      alive = false;
    };
  }, []);

  const effectiveConfigExists = settings?.repository.config_exists ?? configExists;

  async function completeSetup() {
    setSetupBusy(true);
    setSetupError(null);
    try {
      const status = await completeHostOnlySetup();
      setSettings(status);
      onSetupComplete(status);
    } catch (err) {
      setSetupError(err instanceof Error ? err.message : "Failed to complete Phase 0 setup.");
    } finally {
      setSetupBusy(false);
    }
  }

  async function refreshToolChecks() {
    setRefreshingChecks(true);
    setSetupError(null);
    try {
      const status = await getSettings();
      setSettings(status);
      onSetupComplete(status);
    } catch (err) {
      setSetupError(err instanceof Error ? err.message : "Failed to refresh environment checks.");
    } finally {
      setRefreshingChecks(false);
    }
  }

  return (
    <section className="settings-layout">
      <div className="panel">
        <div className="panel-heading">
          <Settings aria-hidden="true" size={18} />
          <h2>Environment Checks</h2>
        </div>
        <dl className="settings-list">
          <div>
            <dt>Rev2Agent config</dt>
            <dd>{effectiveConfigExists ? ".rev2agent_config.json found" : ".rev2agent_config.json is missing"}</dd>
          </div>
          <div>
            <dt>Codex authentication</dt>
            <dd>{settings?.codex_sdk.message ?? "Checked by backend before SDK jobs start"}</dd>
          </div>
          <div>
            <dt>LaTeX compiler</dt>
            <dd>{settings ? toolStatusText(settings.tools.latex) : "Checking tectonic..."}</dd>
          </div>
          <div>
            <dt>Python environment</dt>
            <dd>{settings ? `Python ${settings.tools.python.version}` : "Checking Python..."}</dd>
          </div>
          <div>
            <dt>Package manager</dt>
            <dd>{settings ? toolStatusText(settings.tools.package_manager) : "Checking pnpm..."}</dd>
          </div>
          <div>
            <dt>Sandbox policy</dt>
            <dd>High-risk actions require explicit GUI approval</dd>
          </div>
        </dl>
        {!effectiveConfigExists ? (
          <div className="setup-actions">
            <p className="plain-copy">
              Complete host-only Phase 0 setup to create local Rev2Agent config without external model providers.
            </p>
            <button className="primary-button" onClick={completeSetup} disabled={setupBusy}>
              <Settings aria-hidden="true" size={18} />
              {setupBusy ? "Completing Phase 0..." : "Complete Phase 0 Setup"}
            </button>
            {setupError ? (
              <p className="warning-text" role="alert">
                {setupError}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
      {settings && !settings.tools.latex.available ? (
        <TectonicInstallHelp
          platform={settings.environment.platform}
          repositoryRoot={settings.repository.root}
          onRefresh={refreshToolChecks}
          refreshing={refreshingChecks}
        />
      ) : null}
    </section>
  );
}

function TectonicInstallHelp({
  platform,
  repositoryRoot,
  embedded = false,
  onRefresh,
  refreshing = false
}: {
  platform: string;
  repositoryRoot?: string;
  embedded?: boolean;
  onRefresh?: () => void | Promise<void>;
  refreshing?: boolean;
}) {
  const installCommand = tectonicInstallCommand(platform, repositoryRoot);
  const isWindows = platform.toLowerCase().startsWith("win");

  return (
    <div className={embedded ? "install-help embedded-install-help" : "panel install-help"}>
      <div className="panel-heading">
        <Terminal aria-hidden="true" size={18} />
        <h2>Install Tectonic</h2>
      </div>
      <p className="plain-copy">
        Needed for Phase 7 manuscript PDF compilation. Phase 0 can detect this dependency, but installation should be a
        user-run terminal step.
      </p>
      <pre className="command-block">
        <code>{installCommand}</code>
      </pre>
      <p className="plain-copy">
        {isWindows
          ? "Run this in PowerShell, then move tectonic.exe to a folder on PATH so Rev2Agent can find it."
          : "Run this in a terminal, then move tectonic to a folder on PATH so Rev2Agent can find it."}
      </p>
      <div className="action-row">
        {onRefresh ? (
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={refreshing}>
            <RefreshCw aria-hidden="true" size={18} />
            {refreshing ? "Refreshing..." : "Refresh Checks"}
          </button>
        ) : null}
        <a className="text-link" href="https://tectonic-typesetting.github.io/en-US/install.html" target="_blank" rel="noreferrer">
          Official install docs
        </a>
      </div>
    </div>
  );
}

function tectonicInstallCommand(platform: string, repositoryRoot?: string) {
  if (platform.toLowerCase().startsWith("win")) {
    return [
      ...(repositoryRoot ? [`cd ${quotePowerShellPath(repositoryRoot)}`] : []),
      "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072",
      "iex ((New-Object System.Net.WebClient).DownloadString('https://drop-ps1.fullyjustified.net'))"
    ].join("\n");
  }
  return [repositoryRoot ? `cd ${quoteShellPath(repositoryRoot)}` : null, "curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh"]
    .filter(Boolean)
    .join("\n");
}

function quotePowerShellPath(path: string) {
  return `'${path.replace(/'/g, "''")}'`;
}

function quoteShellPath(path: string) {
  return `'${path.replace(/'/g, "'\\''")}'`;
}

function toolStatusText(tool: ToolStatus) {
  return tool.available && tool.path ? `${tool.name} found at ${tool.path}` : `${tool.name} not found`;
}

function StatusChip({ label, tone }: { label: string; tone: "ok" | "warn" }) {
  return <span className={`status-chip ${tone}`}>{label}</span>;
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="error-banner" role="alert">
      <AlertTriangle aria-hidden="true" size={18} />
      {message}
    </div>
  );
}
