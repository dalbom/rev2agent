export interface ProjectSummary {
  project_dir: string;
  phase: number | null;
  phase_label: string;
  phase_status: string;
  project_status: string;
  topic: string;
  updated_at: string | null;
  active_runs: number;
  healthy: boolean;
  health_message?: string | null;
}

export interface ProjectDiscoveryResult {
  setup_required: boolean;
  config_exists: boolean;
  projects: ProjectSummary[];
}

export interface PhaseJobResult {
  job_id: string;
  requires_approval: boolean;
  status: string;
  sandbox: string;
  message?: string;
}

export interface ApprovalResult {
  approval_id: number;
  user_action: "approved" | "rejected";
  final_status: string;
}

export interface ArtifactRecord {
  artifact_id: number;
  artifact_type: string;
  title: string;
  path: string;
  validation_status: string;
}

export interface ArtifactContent {
  artifact_id: number;
  kind: "text" | "binary";
  mime_type: string;
  size_bytes: number;
  content: string | null;
}

export interface InterruptResult {
  job_id: string;
  interrupted: boolean;
}

export interface RunEvent {
  event_id?: number;
  event_type: string;
  summary: string;
  timestamp?: string;
  status?: string;
  job_id?: string;
  raw_payload_json?: string | null;
}

export interface JobRecord {
  job_id: string;
  project_dir: string;
  phase: number;
  status: string;
  approval_state: string;
  sandbox: string;
  started_at?: string | null;
  completed_at?: string | null;
  last_error: string | null;
}

export interface ProjectToolResult {
  status: "passed" | "failed";
  return_code: number;
  stdout?: string;
  stderr?: string;
  output_md?: string;
  output_json?: string;
  report?: string;
  artifacts?: ArtifactRecord[];
}

export interface SettingsStatus {
  codex_sdk: {
    available: boolean;
    version: string | null;
    message: string;
  };
  repository: {
    root: string;
    config_exists: boolean;
  };
  environment: {
    platform: string;
  };
  tools: {
    latex: ToolStatus;
    python: {
      available: boolean;
      version: string;
    };
    package_manager: ToolStatus;
  };
}

export interface ToolStatus {
  name: string;
  available: boolean;
  path: string | null;
}

export const TERMINAL_JOB_STATUSES = ["completed", "failed", "interrupted", "cancelled", "rejected"];

async function requestJson<T>(failureMessage: string, input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail = "";
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Body was not JSON; fall back to the status code.
    }
    throw new Error(detail ? `${failureMessage}: ${detail}` : `${failureMessage}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function projectPath(project: ProjectSummary): string {
  return encodeURIComponent(project.project_dir);
}

export async function listProjects(): Promise<ProjectDiscoveryResult> {
  return requestJson("Failed to load projects", "/api/projects");
}

export async function createProjectDraft(researchIdea: string, projectName?: string): Promise<ProjectSummary> {
  return requestJson("Failed to start project", "/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ research_idea: researchIdea, project_name: projectName ?? "" })
  });
}

export async function archiveProject(project: ProjectSummary): Promise<ProjectSummary> {
  return requestJson("Failed to archive project", `/api/projects/${projectPath(project)}/archive`, {
    method: "POST"
  });
}

export async function listProjectJobs(project: ProjectSummary, activeOnly: boolean): Promise<JobRecord[]> {
  return requestJson(
    "Failed to load project jobs",
    `/api/projects/${projectPath(project)}/jobs?active=${activeOnly ? "true" : "false"}`
  );
}

export async function startPhaseJob(
  project: ProjectSummary,
  action: string,
  prompt: string
): Promise<PhaseJobResult> {
  if (project.phase === null) {
    throw new Error("Project phase is unknown; refresh the project list before starting jobs.");
  }
  return requestJson(
    "Failed to start phase job",
    `/api/projects/${projectPath(project)}/phase/${project.phase}/jobs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, prompt })
    }
  );
}

export async function getJob(jobId: string): Promise<JobRecord> {
  return requestJson("Failed to load job", `/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function listJobEvents(jobId: string): Promise<RunEvent[]> {
  return requestJson("Failed to load job events", `/api/jobs/${encodeURIComponent(jobId)}/events`);
}

export async function submitJobApproval(
  jobId: string,
  userAction: "approved" | "rejected"
): Promise<ApprovalResult> {
  return requestJson("Failed to submit approval", `/api/jobs/${encodeURIComponent(jobId)}/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_action: userAction })
  });
}

export async function continueJob(jobId: string, action: string, prompt: string): Promise<PhaseJobResult> {
  return requestJson("Failed to continue job", `/api/jobs/${encodeURIComponent(jobId)}/continue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, prompt })
  });
}

export async function interruptJob(jobId: string): Promise<InterruptResult> {
  return requestJson("Failed to interrupt job", `/api/jobs/${encodeURIComponent(jobId)}/interrupt`, {
    method: "POST"
  });
}

export async function listArtifacts(project: ProjectSummary): Promise<ArtifactRecord[]> {
  return requestJson("Failed to load artifacts", `/api/projects/${projectPath(project)}/artifacts`);
}

export async function readArtifact(project: ProjectSummary, artifactId: number): Promise<ArtifactContent> {
  return requestJson(
    "Failed to read artifact",
    `/api/projects/${projectPath(project)}/artifacts/${artifactId}`
  );
}

export async function collectResults(project: ProjectSummary): Promise<ProjectToolResult> {
  return requestJson("Failed to collect results", `/api/projects/${projectPath(project)}/collect-results`, {
    method: "POST"
  });
}

export async function validateManuscript(project: ProjectSummary): Promise<ProjectToolResult> {
  return requestJson(
    "Failed to validate manuscript",
    `/api/projects/${projectPath(project)}/validate-manuscript`,
    { method: "POST" }
  );
}

export async function getSettings(): Promise<SettingsStatus> {
  return requestJson("Failed to load settings", "/api/settings");
}

export async function completeHostOnlySetup(): Promise<SettingsStatus> {
  return requestJson("Failed to complete Phase 0 setup", "/api/setup/host-only", { method: "POST" });
}
