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

export async function listProjects(): Promise<ProjectDiscoveryResult> {
  const response = await fetch("/api/projects");
  if (!response.ok) {
    throw new Error(`Failed to load projects: ${response.status}`);
  }
  return response.json();
}

export async function createProjectDraft(): Promise<ProjectSummary> {
  const response = await fetch("/api/projects", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to start project: ${response.status}`);
  }
  return response.json();
}

export async function startPhaseJob(
  project: ProjectSummary,
  action: string,
  prompt: string,
  approved = false
): Promise<PhaseJobResult> {
  const response = await fetch(`/api/projects/${project.project_dir}/phase/${project.phase}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, prompt, approved })
  });
  if (!response.ok) {
    throw new Error(`Failed to start phase job: ${response.status}`);
  }
  return response.json();
}

export async function submitJobApproval(
  jobId: string,
  userAction: "approved" | "rejected"
): Promise<ApprovalResult> {
  const response = await fetch(`/api/jobs/${jobId}/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_action: userAction })
  });
  if (!response.ok) {
    throw new Error(`Failed to submit approval: ${response.status}`);
  }
  return response.json();
}

export async function continueJob(jobId: string, action: string, prompt: string): Promise<PhaseJobResult> {
  const response = await fetch(`/api/jobs/${jobId}/continue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, prompt })
  });
  if (!response.ok) {
    throw new Error(`Failed to continue job: ${response.status}`);
  }
  return response.json();
}

export async function interruptJob(jobId: string): Promise<InterruptResult> {
  const response = await fetch(`/api/jobs/${jobId}/interrupt`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to interrupt job: ${response.status}`);
  }
  return response.json();
}

export async function listArtifacts(project: ProjectSummary): Promise<ArtifactRecord[]> {
  const response = await fetch(`/api/projects/${project.project_dir}/artifacts`);
  if (!response.ok) {
    throw new Error(`Failed to load artifacts: ${response.status}`);
  }
  return response.json();
}

export async function readArtifact(project: ProjectSummary, artifactId: number): Promise<ArtifactContent> {
  const response = await fetch(`/api/projects/${project.project_dir}/artifacts/${artifactId}`);
  if (!response.ok) {
    throw new Error(`Failed to read artifact: ${response.status}`);
  }
  return response.json();
}

export async function collectResults(project: ProjectSummary): Promise<ProjectToolResult> {
  const response = await fetch(`/api/projects/${project.project_dir}/collect-results`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to collect results: ${response.status}`);
  }
  return response.json();
}

export async function validateManuscript(project: ProjectSummary): Promise<ProjectToolResult> {
  const response = await fetch(`/api/projects/${project.project_dir}/validate-manuscript`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to validate manuscript: ${response.status}`);
  }
  return response.json();
}

export async function getSettings(): Promise<SettingsStatus> {
  const response = await fetch("/api/settings");
  if (!response.ok) {
    throw new Error(`Failed to load settings: ${response.status}`);
  }
  return response.json();
}
