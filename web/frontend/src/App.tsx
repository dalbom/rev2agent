import { AlertTriangle, Archive, Files, FolderOpen, Play, Plus, RefreshCw, Settings, Square, Terminal } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  collectResults,
  archiveProject,
  completeHostOnlySetup,
  continueJob,
  createProjectDraft,
  getSettings,
  interruptJob,
  listArtifacts,
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
  type RunEvent,
  type SettingsStatus,
  type ToolStatus
} from "./api";
import "./styles.css";

type View = "home" | "phase" | "artifacts" | "settings";

const EMPTY_DISCOVERY: ProjectDiscoveryResult = {
  setup_required: false,
  config_exists: false,
  projects: []
};

export default function App() {
  const [discovery, setDiscovery] = useState<ProjectDiscoveryResult>(EMPTY_DISCOVERY);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [view, setView] = useState<View>("home");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
    if (view === "phase" && activeProject) return activeProject.phase_label;
    if (view === "artifacts") return "Artifact Browser";
    return "Project Home";
  }, [activeProject, view]);

  function openProject(project: ProjectSummary) {
    setSelectedProject(project);
    setView("phase");
  }

  async function startNewProject(researchIdea: string) {
    const draft = await createProjectDraft(researchIdea);
    setDiscovery((current) => ({
      ...current,
      projects: [draft, ...current.projects.filter((project) => project.project_dir !== draft.project_dir)]
    }));
    setSelectedProject(draft);
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
            onArtifacts={() => setView("artifacts")}
            onSettings={() => setView("settings")}
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
  onCreate: (researchIdea: string) => Promise<void>;
  onArchive: (project: ProjectSummary) => Promise<void>;
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [researchIdea, setResearchIdea] = useState("");
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
      await onCreate(trimmedIdea);
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
  const match = timestamp.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/);
  return match ? `${match[1]} ${match[2]}` : timestamp;
}

function PhaseDashboard({
  project,
  setupRequired,
  onArtifacts,
  onSettings
}: {
  project: ProjectSummary;
  setupRequired: boolean;
  onArtifacts: () => void;
  onSettings: () => void;
}) {
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [approval, setApproval] = useState<PhaseJobResult | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);
  const [settings, setSettings] = useState<SettingsStatus | null>(null);
  const [showInstallCommand, setShowInstallCommand] = useState(false);
  const [phaseInstruction, setPhaseInstruction] = useState("");
  const [pendingApprovalPrompt, setPendingApprovalPrompt] = useState<string | null>(null);
  const [refreshingSettings, setRefreshingSettings] = useState(false);

  useEffect(() => {
    let alive = true;
    getSettings().then((status) => {
      if (alive) setSettings(status);
    });
    return () => {
      alive = false;
    };
  }, []);

  const needsPhaseSevenLatexChoice = project.phase === 7 && settings?.tools.latex.available === false;
  const canRunExperimentScripts = project.phase === 5 && !setupRequired;

  async function launch(action: string, prompt?: string) {
    setLaunching(true);
    setJobMessage(null);
    const promptToRun = prompt ?? (phaseInstruction.trim() || defaultPhasePrompt(project));
    try {
      const result = await startPhaseJob(project, action, promptToRun);
      setActiveJobId(result.job_id);
      if (result.requires_approval) {
        setPendingApprovalPrompt(promptToRun);
        setApproval(result);
      } else {
        setPendingApprovalPrompt(null);
        setPhaseInstruction("");
        setJobMessage(`Job ${result.job_id} ${result.status}`);
      }
    } finally {
      setLaunching(false);
    }
  }

  async function skipPdfCompile() {
    await launch(
      "Skip PDF Compile",
      `Run Rev2Agent ${project.phase_label} for ${project.project_dir}. Tectonic is not installed, so skip PDF compilation. Draft or update the LaTeX manuscript sources, keep references consistent, and tell the user to install Tectonic before rerunning PDF compilation.`
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

  async function approveJob(result: PhaseJobResult) {
    await submitJobApproval(result.job_id, "approved");
    const continued = await continueJob(
      result.job_id,
      "Run experiment scripts",
      pendingApprovalPrompt ?? `Approved high-risk action for ${project.project_dir}`
    );
    setActiveJobId(continued.job_id);
    setApproval(null);
    setPendingApprovalPrompt(null);
    setPhaseInstruction("");
    setJobMessage(`Job ${continued.job_id} ${continued.status}`);
  }

  function rejectApproval() {
    setApproval(null);
    setPendingApprovalPrompt(null);
  }

  async function interruptActiveJob() {
    if (!activeJobId) return;
    const result = await interruptJob(activeJobId);
    setJobMessage(`Job ${result.job_id} ${result.interrupted ? "interrupted" : "could not be interrupted"}`);
  }

  return (
    <section className="dashboard">
      <div className="panel phase-panel">
        <div className="phase-title">
          <div>
            <p className="eyebrow">{project.project_dir}</p>
            <h2>Step Details</h2>
          </div>
          <StatusChip label={project.phase_status} tone="ok" />
        </div>
        <p className="plain-copy">
          Rev2Agent will run this step through a Codex SDK phase thread and preserve project state in the project folder.
        </p>
        {project.topic ? (
          <p className="project-topic">
            <strong>Research idea</strong>
            {project.topic}
          </p>
        ) : null}
        {setupRequired ? (
          <p className="warning-text">Complete Phase 0 setup in Settings before running project steps.</p>
        ) : null}
        <div className="phase-instruction-form">
          <label htmlFor="phase-instruction">Phase instruction</label>
          <textarea
            id="phase-instruction"
            value={phaseInstruction}
            onChange={(event) => setPhaseInstruction(event.target.value)}
            placeholder="Optional: add a specific instruction for this run, such as a short smoke experiment or a user answer."
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
            onClick={() => launch(`Continue ${project.phase_label}`)}
            disabled={launching || setupRequired}
          >
            <Play aria-hidden="true" size={18} />
            Run Next Step
          </button>
          <button
            className="secondary-button"
            onClick={() => launch("Run experiment scripts")}
            disabled={launching || !canRunExperimentScripts}
          >
            <Play aria-hidden="true" size={18} />
            Run Experiment Scripts
          </button>
          <button className="secondary-button" onClick={interruptActiveJob} disabled={!activeJobId || launching}>
            <Square aria-hidden="true" size={18} />
            Stop
          </button>
          <button className="secondary-button" onClick={onArtifacts}>
            <Files aria-hidden="true" size={18} />
            View Files
          </button>
        </div>
        {jobMessage ? <p className="job-message">{jobMessage}</p> : null}
        {approval ? (
          <ApprovalDialog approval={approval} onApprove={() => approveJob(approval)} onReject={rejectApproval} />
        ) : null}
      </div>
      <LiveRunConsole jobId={activeJobId} />
      <LatestArtifactPreview project={project} onArtifacts={onArtifacts} />
    </section>
  );
}

function ApprovalDialog({
  approval,
  onApprove,
  onReject
}: {
  approval: PhaseJobResult;
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
          <button className="secondary-button" onClick={onReject}>
            Reject
          </button>
          <button className="primary-button" onClick={onApprove}>
            Approve High-Risk Action
          </button>
        </div>
      </section>
    </div>
  );
}

function LiveRunConsole({ jobId }: { jobId: string | null }) {
  const [events, setEvents] = useState<RunEvent[]>([]);

  useEffect(() => {
    if (!jobId) {
      setEvents([]);
      return;
    }

    setEvents([]);
    const source = new EventSource(`/api/jobs/${jobId}/events/stream`);
    const addEvent = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as RunEvent;
        setEvents((current) => [...current, parsed]);
      } catch {
        setEvents((current) => [
          ...current,
          { event_type: "stream_error", summary: "A job event could not be displayed." }
        ]);
      }
    };

    [
      "message",
      "job_started",
      "thread_started",
      "turn_completed",
      "job_completed",
      "approval_required",
      "approval_approved",
      "job_interrupted",
      "error"
    ].forEach((eventName) => source.addEventListener(eventName, addEvent));

    return () => source.close();
  }, [jobId]);

  return (
    <section className="panel console-panel" aria-label="Live run console">
      <div className="panel-heading">
        <Terminal aria-hidden="true" size={18} />
        <h2>Live Run Console</h2>
      </div>
      <ol className="event-list">
        {events.length > 0 ? (
          events.map((event, index) => (
            <li key={`${event.event_id ?? event.event_type}-${index}`}>
              <span className="event-dot" />
              {event.summary}
            </li>
          ))
        ) : (
          <li>
            <span className="event-dot" />
            {jobId ? "Listening for job events." : "Waiting for a phase job to start."}
          </li>
        )}
      </ol>
    </section>
  );
}

function LatestArtifactPreview({
  project,
  onArtifacts
}: {
  project: ProjectSummary;
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
  }, [project]);

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
      .finally(() => {
        if (alive) setLoadingArtifacts(false);
      });
    return () => {
      alive = false;
    };
  }, [project]);

  async function openArtifact(artifact: ArtifactRecord) {
    setPreview(await readArtifact(project, artifact.artifact_id));
  }

  function selectArtifactTab(tab: (typeof ARTIFACT_TABS)[number]["label"]) {
    setActiveTab(tab);
    setPreview(null);
  }

  async function runCollectResults() {
    const result = await collectResults(project);
    if (result.artifacts) setArtifacts(result.artifacts);
    setToolMessage(`Result collection ${result.status}`);
  }

  async function runValidateManuscript() {
    const result = await validateManuscript(project);
    if (result.artifacts) setArtifacts(result.artifacts);
    setToolMessage(`Manuscript validation ${result.status}`);
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
    getSettings().then((status) => {
      if (alive) setSettings(status);
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
