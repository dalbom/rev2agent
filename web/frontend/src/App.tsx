import { AlertTriangle, Files, FolderOpen, Play, Plus, Settings, Square, Terminal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  collectResults,
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

  async function startNewProject() {
    const draft = await createProjectDraft();
    setDiscovery((current) => ({
      ...current,
      projects: [draft, ...current.projects.filter((project) => project.project_dir !== draft.project_dir)]
    }));
    setSelectedProject(draft);
    setView("phase");
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
            <p className="eyebrow">Local browser GUI</p>
            <h1>{pageTitle}</h1>
          </div>
          <StatusChip label={discovery.setup_required ? "setup needed" : "ready"} tone={discovery.setup_required ? "warn" : "ok"} />
        </header>

        {error ? <ErrorBanner message={error} /> : null}
        {loading ? <div className="panel">Loading projects...</div> : null}
        {!loading && view === "home" ? (
          <ProjectHome projects={discovery.projects} onOpen={openProject} onCreate={startNewProject} />
        ) : null}
        {!loading && view === "settings" ? <SettingsSafety configExists={discovery.config_exists} /> : null}
        {!loading && view === "phase" && activeProject ? <PhaseDashboard project={activeProject} onArtifacts={() => setView("artifacts")} /> : null}
        {!loading && view === "artifacts" && activeProject ? <ArtifactBrowser project={activeProject} /> : null}
      </section>
    </main>
  );
}

function ProjectHome({
  projects,
  onOpen,
  onCreate
}: {
  projects: ProjectSummary[];
  onOpen: (project: ProjectSummary) => void;
  onCreate: () => void;
}) {
  if (projects.length === 0) {
    return (
      <section className="panel">
        <h2>No projects yet</h2>
        <p>Start a new research project from Setup after Codex authentication and repository checks are complete.</p>
        <button className="primary-button" onClick={onCreate}>
          <Plus aria-hidden="true" size={18} />
          Start New Project
        </button>
      </section>
    );
  }

  return (
    <section className="project-home">
      <div className="section-toolbar">
        <h2>Existing Projects</h2>
        <button className="primary-button" onClick={onCreate}>
          <Plus aria-hidden="true" size={18} />
          Start New Project
        </button>
      </div>
      <div className="project-grid" aria-label="Existing research projects">
        {projects.map((project) => (
          <article className="project-card" key={project.project_dir}>
            <div className="card-head">
              <div>
                <h2>{project.project_dir}</h2>
                <p>{project.topic || "Topic not set yet"}</p>
              </div>
              <StatusChip label={project.phase_status} tone={project.healthy ? "ok" : "warn"} />
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
                <dd>{project.updated_at ?? "Unknown"}</dd>
              </div>
              <div>
                <dt>Active runs</dt>
                <dd>{project.active_runs}</dd>
              </div>
            </dl>
            {!project.healthy ? <p className="warning-text">{project.health_message}</p> : null}
            <button className="primary-button" onClick={() => onOpen(project)} aria-label={`Open ${project.project_dir}`}>
              <FolderOpen aria-hidden="true" size={18} />
              Open
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function PhaseDashboard({ project, onArtifacts }: { project: ProjectSummary; onArtifacts: () => void }) {
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [approval, setApproval] = useState<PhaseJobResult | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);

  async function launch(action: string) {
    setLaunching(true);
    setJobMessage(null);
    try {
      const result = await startPhaseJob(
        project,
        action,
        `Run Rev2Agent ${project.phase_label} for ${project.project_dir}`
      );
      setActiveJobId(result.job_id);
      if (result.requires_approval) {
        setApproval(result);
      } else {
        setJobMessage(`Job ${result.job_id} ${result.status}`);
      }
    } finally {
      setLaunching(false);
    }
  }

  async function approveJob(result: PhaseJobResult) {
    await submitJobApproval(result.job_id, "approved");
    const continued = await continueJob(
      result.job_id,
      "Run experiment scripts",
      `Approved high-risk action for ${project.project_dir}`
    );
    setActiveJobId(continued.job_id);
    setApproval(null);
    setJobMessage(`Job ${continued.job_id} ${continued.status}`);
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
        <div className="action-row">
          <button className="primary-button" onClick={() => launch(`Continue ${project.phase_label}`)} disabled={launching}>
            <Play aria-hidden="true" size={18} />
            Run Next Step
          </button>
          <button className="secondary-button" onClick={() => launch("Run experiment scripts")} disabled={launching}>
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
          <ApprovalDialog approval={approval} onApprove={() => approveJob(approval)} onReject={() => setApproval(null)} />
        ) : null}
      </div>
      <LiveRunConsole jobId={activeJobId} />
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
        setEvents((current) => [...current, JSON.parse(event.data) as RunEvent]);
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

function ArtifactBrowser({ project }: { project: ProjectSummary }) {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [preview, setPreview] = useState<ArtifactContent | null>(null);
  const [toolMessage, setToolMessage] = useState<string | null>(null);
  const [loadingArtifacts, setLoadingArtifacts] = useState(true);

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
        {["Summaries", "Literature", "Experiments", "Results", "Manuscript", "Figures"].map((tab) => (
          <button className="tab-button" key={tab} role="tab" aria-selected={tab === "Summaries"}>
            {tab}
          </button>
        ))}
      </div>
      {loadingArtifacts ? <p className="plain-copy">Loading artifacts for {project.project_dir}...</p> : null}
      {!loadingArtifacts ? (
        <div className="artifact-layout">
          <ul className="artifact-list" aria-label="Artifacts">
            {artifacts.map((artifact) => (
              <li key={artifact.artifact_id}>
                <div>
                  <strong>{artifact.title}</strong>
                  <span>{artifact.artifact_type}</span>
                </div>
                <button className="secondary-button" onClick={() => openArtifact(artifact)} aria-label={`Open ${artifact.title}`}>
                  Open
                </button>
              </li>
            ))}
          </ul>
          <div className="artifact-preview" aria-label="Artifact preview">
            {preview?.kind === "text" ? <pre>{preview.content}</pre> : null}
            {preview?.kind === "binary" ? <p>Binary preview: {preview.mime_type}</p> : null}
            {!preview ? <p className="plain-copy">Select an artifact to preview safe content.</p> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function SettingsSafety({ configExists }: { configExists: boolean }) {
  const [settings, setSettings] = useState<SettingsStatus | null>(null);

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
      </div>
    </section>
  );
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
