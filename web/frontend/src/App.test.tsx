import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close = vi.fn();

  emit(data: unknown) {
    const payload = data === undefined ? undefined : JSON.stringify(data);
    this.onmessage?.({ data: payload } as unknown as MessageEvent);
  }
}

function expectedLocalTimestamp(isoTimestamp: string) {
  // Same Date math the app uses, so the expectation is timezone-independent.
  const date = new Date(isoTimestamp);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`;
}

const projectsResponse = {
  setup_required: false,
  config_exists: true,
  projects: [
    {
      project_dir: "synthetic_segmentation",
      phase: 4,
      phase_label: "Design Experiments",
      phase_status: "waiting_for_user",
      project_status: "active",
      topic: "Synthetic data for segmentation",
      updated_at: "2026-06-02T10:00:00Z",
      active_runs: 0,
      healthy: true
    }
  ]
};

const phaseSevenProjectsResponse = {
  setup_required: false,
  config_exists: true,
  projects: [
    {
      project_dir: "manuscript_project",
      phase: 7,
      phase_label: "Write Manuscript",
      phase_status: "waiting_for_user",
      project_status: "active",
      topic: "Synthetic data for segmentation",
      updated_at: "2026-06-02T12:00:00Z",
      active_runs: 0,
      healthy: true
    }
  ]
};

const phaseFiveProjectsResponse = {
  setup_required: false,
  config_exists: true,
  projects: [
    {
      project_dir: "experiment_project",
      phase: 5,
      phase_label: "Run Experiments",
      phase_status: "waiting_for_user",
      project_status: "active",
      topic: "Closed-loop synthetic data generation",
      updated_at: "2026-06-02T12:10:00Z",
      active_runs: 0,
      healthy: true
    }
  ]
};

const phaseOneProjectsResponse = {
  setup_required: false,
  config_exists: true,
  projects: [
    {
      project_dir: "_new_project_draft",
      phase: 1,
      phase_label: "Choose Topic",
      phase_status: "in_progress",
      project_status: "active",
      topic:
        "Closed-loop synthetic data generation: train a downstream task on existing data, generate synthetic data to improve performance, retrain, evaluate, and repeat.",
      updated_at: "2026-06-02T12:30:00Z",
      active_runs: 0,
      healthy: true
    }
  ]
};

const settingsResponse = {
  codex_sdk: {
    available: true,
    version: "0.1.0b2",
    message: "openai_codex is installed."
  },
  repository: {
    root: "C:/dev/rev2agent/rev2agent-repo",
    config_exists: true
  },
  environment: {
    platform: "Windows"
  },
  tools: {
    latex: {
      name: "tectonic",
      available: true,
      path: "C:/tools/tectonic.exe"
    },
    python: {
      available: true,
      version: "3.11.14"
    },
    package_manager: {
      name: "pnpm",
      available: true,
      path: "C:/tools/pnpm.cmd"
    }
  }
};

const missingTectonicSettingsResponse = {
  ...settingsResponse,
  tools: {
    ...settingsResponse.tools,
    latex: {
      name: "tectonic",
      available: false,
      path: null
    }
  }
};

describe("App", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    window.sessionStorage.clear();
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/projects" && init?.method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          return {
            ok: true,
            json: async () => ({
              project_dir: "_new_project_draft",
              phase: 1,
              phase_label: "Choose Topic",
              phase_status: "in_progress",
              project_status: "active",
              topic: body.research_idea ?? "",
              updated_at: "2026-06-02T11:00:00Z",
              active_runs: 0,
              healthy: true
            })
          };
        }
        if (String(input).includes("/jobs?active=")) {
          return {
            ok: true,
            json: async () => []
          };
        }
        if (/\/api\/jobs\/[^/]+\/events$/.test(String(input))) {
          return {
            ok: true,
            json: async () => []
          };
        }
        if (String(input) === "/api/settings") {
          return {
            ok: true,
            json: async () => settingsResponse
          };
        }
        if (String(input) === "/api/setup/host-only") {
          return {
            ok: true,
            json: async () => settingsResponse
          };
        }
        if (String(input).includes("/phase/1/jobs")) {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-phase1",
              requires_approval: false,
              status: "running",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input).includes("/phase/4/jobs")) {
          const body = JSON.parse(String(init?.body ?? "{}"));
          if (body.action.includes("Run experiment")) {
            return {
              ok: true,
              json: async () => ({
                job_id: "job-risk",
                requires_approval: true,
                status: "waiting_for_approval",
                sandbox: "workspace_write",
                message: "This starts a long-running experiment or training job."
              })
            };
          }
          return {
            ok: true,
            json: async () => ({
              job_id: "job-1",
              requires_approval: false,
              status: "running",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input).includes("/phase/5/jobs")) {
          const body = JSON.parse(String(init?.body ?? "{}"));
          if (body.action.includes("Run experiment")) {
            return {
              ok: true,
              json: async () => ({
                job_id: "job-risk",
                requires_approval: true,
                status: "waiting_for_approval",
                sandbox: "workspace_write",
                message: "This starts a long-running experiment or training job."
              })
            };
          }
          return {
            ok: true,
            json: async () => ({
              job_id: "job-phase5",
              requires_approval: false,
              status: "running",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input) === "/api/jobs/job-risk/approval") {
          return {
            ok: true,
            json: async () => ({ approval_id: 1, user_action: "approved", final_status: "approved" })
          };
        }
        if (String(input) === "/api/jobs/job-risk/continue") {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: false,
              status: "completed",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input) === "/api/jobs/job-1/interrupt") {
          return {
            ok: true,
            json: async () => ({ job_id: "job-1", interrupted: true })
          };
        }
        if (String(input) === "/api/projects/synthetic_segmentation/collect-results") {
          return {
            ok: true,
            json: async () => ({
              status: "passed",
              return_code: 0,
              output_md: "synthetic_segmentation/experiment/results/comparison.md",
              output_json: "synthetic_segmentation/experiment/results/comparison.json",
              artifacts: []
            })
          };
        }
        if (String(input) === "/api/projects/synthetic_segmentation/validate-manuscript") {
          return {
            ok: true,
            json: async () => ({
              status: "passed",
              return_code: 0,
              report: "synthetic_segmentation/manuscript/validation_report.txt",
              artifacts: []
            })
          };
        }
        if (String(input).endsWith("/artifacts/1")) {
          return {
            ok: true,
            json: async () => ({
              artifact_id: 1,
              kind: "text",
              mime_type: "text/markdown",
              content: "# Topic Summary\n\n- First finding\n\n| Metric | Value |\n| --- | --- |\n| Accuracy | 0.70 |\n",
              size_bytes: 86
            })
          };
        }
        if (String(input).endsWith("/artifacts/2")) {
          return {
            ok: true,
            json: async () => ({
              artifact_id: 2,
              kind: "text",
              mime_type: "text/csv",
              content: "metric,value\naccuracy,0.70\n",
              size_bytes: 27
            })
          };
        }
        if (String(input).endsWith("/artifacts")) {
          return {
            ok: true,
            json: async () => [
              {
                artifact_id: 1,
                artifact_type: "summary",
                title: "phase1_topic.md",
                path: "synthetic_segmentation/summaries/phase1_topic.md",
                validation_status: "valid"
              },
              {
                artifact_id: 2,
                artifact_type: "result",
                title: "metrics.csv",
                path: "synthetic_segmentation/experiment/results/metrics.csv",
                validation_status: "unknown"
              }
            ]
          };
        }
        return {
          ok: true,
          json: async () => projectsResponse
        };
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders discovered projects with friendly phase labels first", async () => {
    render(<App />);

    expect(await screen.findByText("synthetic_segmentation")).toBeInTheDocument();
    expect(screen.getByText("Synthetic data for segmentation")).toBeInTheDocument();
    expect(screen.getByText("Design Experiments")).toBeInTheDocument();
    expect(screen.getByText("Phase 4")).toBeInTheDocument();
    expect(screen.getByText("waiting_for_user")).toBeInTheDocument();
  });

  it("archives a project from the project card after confirmation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input) === "/api/projects/synthetic_segmentation/archive") {
        return {
          ok: true,
          json: async () => ({
            ...projectsResponse.projects[0],
            phase_status: "archived",
            project_status: "archived"
          })
        };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(<App />);

    expect(await screen.findByText("synthetic_segmentation")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /archive synthetic_segmentation/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/archive",
      expect.objectContaining({ method: "POST" })
    );
    expect(await screen.findByText("Project archived.")).toBeInTheDocument();
    expect(screen.queryByText("synthetic_segmentation")).not.toBeInTheDocument();
  });

  it("routes setup-required repositories to settings and safety", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => ({
        ok: true,
        json: async () =>
          String(input) === "/api/settings"
            ? { ...settingsResponse, repository: { ...settingsResponse.repository, config_exists: false } }
            : { ...projectsResponse, setup_required: true, config_exists: false }
      }))
    );

    render(<App />);

    expect(await screen.findByText("Settings And Safety")).toBeInTheDocument();
    expect(screen.getByText(".rev2agent_config.json is missing")).toBeInTheDocument();
  });

  it("completes host-only Phase 0 setup from settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/setup/host-only") {
        return {
          ok: true,
          json: async () => settingsResponse
        };
      }
      if (String(input) === "/api/settings") {
        return {
          ok: true,
          json: async () => ({ ...settingsResponse, repository: { ...settingsResponse.repository, config_exists: false } })
        };
      }
      return {
        ok: true,
        json: async () => ({ ...projectsResponse, setup_required: true, config_exists: false, projects: [] })
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /complete phase 0 setup/i }));

    expect(await screen.findByText(".rev2agent_config.json found")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/setup/host-only",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("prevents project creation until Phase 0 setup is complete", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => ({
        ok: true,
        json: async () =>
          String(input) === "/api/settings"
            ? { ...settingsResponse, repository: { ...settingsResponse.repository, config_exists: false } }
            : { ...projectsResponse, setup_required: true, config_exists: false, projects: [] }
      }))
    );

    render(<App />);

    await screen.findByText("Settings And Safety");
    await userEvent.click(screen.getByRole("button", { name: "Projects" }));

    expect(await screen.findByRole("button", { name: /start new project/i })).toBeDisabled();
    expect(screen.getByText(/complete phase 0 setup in settings/i)).toBeInTheDocument();
  });

  it("shows backend settings and tool status", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));

    expect(await screen.findByText("openai_codex is installed.")).toBeInTheDocument();
    expect(screen.getByText("tectonic found at C:/tools/tectonic.exe")).toBeInTheDocument();
    expect(screen.getByText("Python 3.11.14")).toBeInTheDocument();
    expect(screen.getByText("pnpm found at C:/tools/pnpm.cmd")).toBeInTheDocument();
  });

  it("does not show the implementation label in the header", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: "Project Home" });

    expect(screen.queryByText("Local browser GUI")).not.toBeInTheDocument();
  });

  it("shows install guidance when tectonic is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => ({
        ok: true,
        json: async () =>
          String(input) === "/api/settings"
            ? {
                ...settingsResponse,
                tools: {
                  ...settingsResponse.tools,
                  latex: {
                    name: "tectonic",
                    available: false,
                    path: null
                  }
                }
              }
            : projectsResponse
      }))
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));

    expect(await screen.findByText("Install Tectonic")).toBeInTheDocument();
    expect(screen.getByText(/Needed for Phase 7 manuscript PDF compilation/i)).toBeInTheDocument();
    expect(screen.getByText(/drop-ps1\.fullyjustified\.net/i)).toHaveTextContent(
      "cd 'C:/dev/rev2agent/rev2agent-repo'"
    );
    expect(screen.getByRole("link", { name: /official install docs/i })).toHaveAttribute(
      "href",
      "https://tectonic-typesetting.github.io/en-US/install.html"
    );
  });

  it("refreshes settings after tectonic is installed", async () => {
    let settingsChecks = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          settingsChecks += 1;
          return {
            ok: true,
            json: async () => (settingsChecks === 1 ? missingTectonicSettingsResponse : settingsResponse)
          };
        }
        return {
          ok: true,
          json: async () => projectsResponse
        };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(await screen.findByText("Install Tectonic")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh checks/i }));

    expect(await screen.findByText("tectonic found at C:/tools/tectonic.exe")).toBeInTheDocument();
    expect(screen.queryByText("Install Tectonic")).not.toBeInTheDocument();
  });

  it("opens phase dashboard from a project card", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(screen.getByRole("heading", { name: "Synthetic Segmentation", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Design Experiments", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Step Details" })).not.toBeInTheDocument();
    expect(screen.queryByText("SYNTHETIC_SEGMENTATION")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run next step/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run experiment scripts/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view files/i })).not.toBeInTheDocument();
  });

  it("keeps the console above the prompt and the latest artifact beside the step controls", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    const phasePanel = screen.getByRole("region", { name: /current step/i });
    expect(within(phasePanel).getByRole("heading", { name: "Live Run Console" })).toBeInTheDocument();
    expect(within(phasePanel).getByLabelText("Prompt")).toBeInTheDocument();
    expect(within(phasePanel).getByRole("button", { name: /send/i })).toBeInTheDocument();

    const consoleHeading = within(phasePanel).getByRole("heading", { name: "Live Run Console" });
    const promptBox = within(phasePanel).getByLabelText("Prompt");
    expect(consoleHeading.compareDocumentPosition(promptBox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(screen.getByRole("region", { name: /latest artifact preview/i })).toBeInTheDocument();
  });

  it("shows the latest artifact preview on the phase dashboard and links to files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        if (String(input).endsWith("/artifacts/9")) {
          return {
            ok: true,
            json: async () => ({
              artifact_id: 9,
              kind: "text",
              mime_type: "text/markdown",
              content: "# Latest Results\n\n- Accuracy improved\n",
              size_bytes: 36
            })
          };
        }
        if (String(input).endsWith("/artifacts")) {
          return {
            ok: true,
            json: async () => [
              {
                artifact_id: 3,
                artifact_type: "summary",
                title: "phase1_topic.md",
                path: "synthetic_segmentation/summaries/phase1_topic.md",
                validation_status: "valid"
              },
              {
                artifact_id: 9,
                artifact_type: "result",
                title: "phase5_results.md",
                path: "synthetic_segmentation/experiment/results/phase5_results.md",
                validation_status: "valid"
              }
            ]
          };
        }
        return { ok: true, json: async () => projectsResponse };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(await screen.findByRole("heading", { name: "Latest Artifact" })).toBeInTheDocument();
    expect(screen.getByText("phase5_results.md")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Latest Results" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Raw" }));
    expect(await screen.findByText(/# Latest Results/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /open files/i }));
    expect(await screen.findByRole("heading", { name: "Artifact Browser", level: 1 })).toBeInTheDocument();
  });

  it("formats project update timestamps for display", async () => {
    render(<App />);

    expect(await screen.findByText(expectedLocalTimestamp("2026-06-02T10:00:00Z"))).toBeInTheDocument();
    expect(screen.queryByText("2026-06-02T10:00:00Z")).not.toBeInTheDocument();
  });

  it("shows Phase 7 choices when tectonic is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        return {
          ok: true,
          json: async () =>
            String(input) === "/api/settings" ? missingTectonicSettingsResponse : phaseSevenProjectsResponse
        };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open manuscript_project/i }));

    expect(await screen.findByText("PDF compiler missing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show install command/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open settings/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /skip pdf compile/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /show install command/i }));

    expect(await screen.findByText(/drop-ps1\.fullyjustified\.net/i)).toBeInTheDocument();
  });

  it("refreshes Phase 7 compiler status from the embedded install guidance", async () => {
    let settingsChecks = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          settingsChecks += 1;
          return {
            ok: true,
            json: async () => (settingsChecks === 1 ? missingTectonicSettingsResponse : settingsResponse)
          };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        return {
          ok: true,
          json: async () => phaseSevenProjectsResponse
        };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open manuscript_project/i }));
    await userEvent.click(await screen.findByRole("button", { name: /show install command/i }));
    expect(await screen.findByText("Install Tectonic")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /refresh checks/i }));

    await screen.findByRole("button", { name: /send/i });
    expect(screen.queryByText("tectonic found at C:/tools/tectonic.exe")).not.toBeInTheDocument();
    expect(screen.queryByText("PDF compiler missing")).not.toBeInTheDocument();
  });

  it("starts Phase 7 with a skip-PDF prompt when the user chooses to skip compilation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/settings") {
        return {
          ok: true,
          json: async () => missingTectonicSettingsResponse
        };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input).includes("/phase/7/jobs")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-phase7-skip-pdf",
            requires_approval: false,
            status: "completed",
            sandbox: "workspace_write"
          })
        };
      }
      return {
        ok: true,
        json: async () => phaseSevenProjectsResponse
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open manuscript_project/i }));
    await userEvent.click(await screen.findByRole("button", { name: /skip pdf compile/i }));

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();

    const phaseRequest = fetchMock.mock.calls.find(([input]) => String(input).includes("/phase/7/jobs"));
    const requestBody = JSON.parse(String(phaseRequest?.[1]?.body ?? "{}"));

    expect(phaseRequest?.[0]).toBe("/api/projects/manuscript_project/phase/7/jobs");
    expect(requestBody.action).toMatch(/Skip PDF Compile/i);
    expect(requestBody.prompt).toMatch(/skip PDF compilation/i);
  });

  it("starts a new draft project from project home", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /start new project/i }));

    expect(await screen.findByLabelText("Research idea")).toBeInTheDocument();
    expect(screen.getByLabelText("Project folder name (optional)")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith("/api/projects", expect.objectContaining({ method: "POST" }));

    await userEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(screen.getByText("Research idea is required.")).toBeInTheDocument();

    const idea =
      "Closed-loop synthetic data generation: train a downstream task on existing data, generate synthetic data to improve performance, retrain, evaluate, and repeat.";
    await userEvent.type(screen.getByLabelText("Research idea"), idea);
    await userEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(await screen.findByRole("heading", { name: "New Project Draft", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Choose Topic", level: 2 })).toBeInTheDocument();
    expect(screen.queryByText("_new_project_draft")).not.toBeInTheDocument();
    expect(screen.getByText(idea)).toBeInTheDocument();
    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ research_idea: idea, project_name: "" })
      })
    );
  });

  it("auto-starts Phase 1 after project creation using the research idea", async () => {
    const fetchMock = vi.mocked(fetch);
    const idea = "Road surface understanding from camera, LiDAR, and vehicle signals.";

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /start new project/i }));
    await userEvent.type(screen.getByLabelText("Research idea"), idea);
    await userEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();
    expect(await screen.findByText(`You: Research idea: ${idea}`)).toBeInTheDocument();

    const phaseRequest = fetchMock.mock.calls.find(([input]) => String(input).includes("/phase/1/jobs"));
    const requestBody = JSON.parse(String(phaseRequest?.[1]?.body ?? "{}"));
    expect(phaseRequest?.[0]).toBe("/api/projects/_new_project_draft/phase/1/jobs");
    expect(requestBody.prompt).toMatch(/Road surface understanding/i);
  });

  it("includes the project topic in the Phase 1 launch prompt", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/settings") {
        return {
          ok: true,
          json: async () => settingsResponse
        };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input).includes("/phase/1/jobs")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-phase1",
            requires_approval: false,
            status: "completed",
            sandbox: "workspace_write"
          })
        };
      }
      return {
        ok: true,
        json: async () => phaseOneProjectsResponse
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open _new_project_draft/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();

    const phaseRequest = fetchMock.mock.calls.find(([input]) => String(input).includes("/phase/1/jobs"));
    const requestBody = JSON.parse(String(phaseRequest?.[1]?.body ?? "{}"));

    expect(requestBody.prompt).toMatch(/Closed-loop synthetic data generation/i);
  });

  it("labels the user text box as a prompt", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(await screen.findByLabelText("Prompt")).toBeInTheDocument();
    expect(screen.queryByLabelText("Phase instruction")).not.toBeInTheDocument();
  });

  it("launches the current phase job and refreshes projects when it finishes", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/phase/4/jobs",
      expect.objectContaining({ method: "POST" })
    );

    const projectListCallsBefore = vi
      .mocked(fetch)
      .mock.calls.filter(([input, init]) => String(input) === "/api/projects" && !init?.method).length;

    FakeEventSource.instances.at(-1)?.emit({ event_type: "job_status", job_id: "job-1", status: "completed" });

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    const projectListCallsAfter = vi
      .mocked(fetch)
      .mock.calls.filter(([input, init]) => String(input) === "/api/projects" && !init?.method).length;
    expect(projectListCallsAfter).toBeGreaterThan(projectListCallsBefore);
  });

  it("shows backend error details when starting a job fails", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input).includes("/phase/4/jobs")) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: "Current project phase is 5; refusing to run phase 4." })
        };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(
      await screen.findByText("Failed to start phase job: Current project phase is 5; refusing to run phase 4.")
    ).toBeInTheDocument();
  });

  it("removes the dedicated experiment execution button from the step controls", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(screen.queryByRole("button", { name: /run experiment scripts/i })).not.toBeInTheDocument();
  });

  it("shows only user-facing console messages and skips replayed duplicates", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await screen.findByText("Rev2Agent is working now.");
    expect(FakeEventSource.instances.at(-1)?.url).toBe("/api/jobs/job-1/events/stream");

    FakeEventSource.instances.at(-1)?.emit({
      event_id: 3,
      event_type: "CommandExecutionStatus.in_progress",
      summary: "CommandExecutionStatus.in_progress"
    });
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 4,
      event_type: "thread/tokenUsage/updated",
      summary: "thread/tokenUsage/updated"
    });
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 5,
      event_type: "item/agentMessage/delta",
      summary: "Got"
    });
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 6,
      event_type: "item/agentMessage/delta",
      summary: " it"
    });

    const assistantMessage = {
      event_id: 7,
      event_type: "item/completed",
      summary: "Got it: camera + LiDAR + vehicle signals.",
      raw_payload_json: "AgentMessageThreadItem(id='msg_1')"
    };
    FakeEventSource.instances.at(-1)?.emit(assistantMessage);
    FakeEventSource.instances.at(-1)?.emit(assistantMessage);

    expect(await screen.findAllByText("Got it: camera + LiDAR + vehicle signals.")).toHaveLength(1);
    expect(screen.queryByText("CommandExecutionStatus.in_progress")).not.toBeInTheDocument();
    expect(screen.queryByText("thread/tokenUsage/updated")).not.toBeInTheDocument();
    expect(screen.queryByText("Got it")).not.toBeInTheDocument();
  });

  it("extracts the next phase question and hides run-process chatter from the console", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await screen.findByText("Rev2Agent is working now.");
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 21,
      event_type: "item/completed",
      raw_payload_json: "AgentMessageThreadItem(id='msg_phase1')",
      summary:
        "I’ll use the `using-superpowers` skill for session discipline, then I’ll persist this Phase 1 answer before continuing the interview one question at a time.\n\n" +
        "I found the local Phase 1 prompt and the current state file. I’m going to record the application domain now, then continue with the next Phase 1 question.\n\n" +
        "The timestamp command used a newer PowerShell flag that is not available here. I’ll use the compatible UTC conversion path and keep the state update straightforward.\n\n" +
        "Next Phase 1 question: Do you have any specific datasets or benchmarks in mind, or should I identify suitable ones during the literature search?"
    });
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 22,
      event_type: "completion_warning",
      summary:
        "Job completed but the project state did not change (still phase 1, status in_progress). The phase may not have produced its required outputs; review the run log and consider retrying."
    });
    FakeEventSource.instances.at(-1)?.emit({
      event_id: 23,
      event_type: "assistant_message",
      summary:
        "That timestamp command used a PowerShell option not available in this environment. I'll use the older-compatible UTC call and keep going; the failure is harmless but worth recording accurately."
    });
    FakeEventSource.instances.at(-1)?.emit({ event_type: "job_status", job_id: "job-1", status: "completed" });

    expect(
      await screen.findByText(
        "Next Phase 1 question: Do you have any specific datasets or benchmarks in mind, or should I identify suitable ones during the literature search?"
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/using-superpowers/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/local Phase 1 prompt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/timestamp command/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/older-compatible UTC call/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Job completed but the project state did not change/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Run finished/i)).not.toBeInTheDocument();
  });

  it("refreshes the latest artifact preview when a job completes", async () => {
    let artifactListCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input) === "/api/jobs/job-1/events") {
        return { ok: true, json: async () => [] };
      }
      if (String(input).includes("/phase/4/jobs")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-1",
            requires_approval: false,
            status: "running",
            sandbox: "workspace_write"
          })
        };
      }
      if (String(input).endsWith("/artifacts/10")) {
        return {
          ok: true,
          json: async () => ({
            artifact_id: 10,
            kind: "text",
            mime_type: "text/markdown",
            content: "# Phase 1 Topic\n\nUpdated topic summary.",
            size_bytes: 39
          })
        };
      }
      if (String(input).endsWith("/artifacts")) {
        artifactListCalls += 1;
        return {
          ok: true,
          json: async () =>
            artifactListCalls === 1
              ? []
              : [
                  {
                    artifact_id: 10,
                    artifact_type: "summary",
                    title: "phase1_topic.md",
                    path: "synthetic_segmentation/summaries/phase1_topic.md",
                    validation_status: "valid"
                  }
                ]
        };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    expect(await screen.findByText("No artifacts yet.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("Rev2Agent is working now.");
    FakeEventSource.instances.at(-1)?.emit({ event_type: "job_status", job_id: "job-1", status: "completed" });

    expect(await screen.findByText("phase1_topic.md")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Phase 1 Topic" })).toBeInTheDocument();
  });

  it("keeps the console transcript across runs until the user clears it", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.type(await screen.findByLabelText("Prompt"), "Use camera and LiDAR.");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await screen.findByText("You: Use camera and LiDAR.");
    const firstSource = FakeEventSource.instances.at(-1);
    firstSource?.emit({
      event_id: 11,
      event_type: "item/completed",
      summary: "First answer from Rev2Agent.",
      raw_payload_json: "AgentMessageThreadItem(id='msg_2')"
    });
    firstSource?.emit({ event_type: "job_status", job_id: "job-1", status: "completed" });

    expect(await screen.findByText("First answer from Rev2Agent.")).toBeInTheDocument();
    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    expect(screen.queryByText("Run finished. Rev2Agent is waiting for your next prompt.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("You: Use camera and LiDAR.")).toBeInTheDocument();
    expect(screen.getByText("First answer from Rev2Agent.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(screen.queryByText("You: Use camera and LiDAR.")).not.toBeInTheDocument();
    expect(screen.queryByText("First answer from Rev2Agent.")).not.toBeInTheDocument();
  });

  it("reloads the saved console transcript when returning to a project", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("Rev2Agent is working now.");

    FakeEventSource.instances.at(-1)?.emit({
      event_id: 31,
      event_type: "item/completed",
      summary: "Next Phase 1 question: Which evaluation metric matters most?",
      raw_payload_json: "AgentMessageThreadItem(id='msg_saved')"
    });

    expect(await screen.findByText("Next Phase 1 question: Which evaluation metric matters most?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Projects" }));
    expect(await screen.findByRole("heading", { name: "Existing Projects" })).toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    expect(await screen.findByText("Next Phase 1 question: Which evaluation metric matters most?")).toBeInTheDocument();
  });

  it("sends the prompt with Ctrl+Enter from the text box", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.type(await screen.findByLabelText("Prompt"), "Use a tiny dataset smoke test.");
    await userEvent.keyboard("{Control>}{Enter}{/Control}");

    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/phase/4/jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          action: "Continue Design Experiments",
          prompt: "Use a tiny dataset smoke test."
        })
      })
    );
  });

  it("keeps the live console mounted when an SSE event has invalid data", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await screen.findByText("Rev2Agent is working now.");
    FakeEventSource.instances.at(-1)?.emit(undefined);

    expect(await screen.findByText("A job event could not be displayed.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live Run Console" })).toBeInTheDocument();
  });

  it("interrupts the active job from the dashboard while it is running", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    const stopButton = screen.getByRole("button", { name: /stop/i });
    expect(stopButton).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("Rev2Agent is working now.");
    expect(stopButton).toBeEnabled();

    await userEvent.click(stopButton);

    expect(await screen.findByText("Rev2Agent stopped. You can revise the prompt and run the step again.")).toBeInTheDocument();
    expect(stopButton).toBeDisabled();
    expect(fetch).toHaveBeenCalledWith(
      "/api/jobs/job-1/interrupt",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows a high-risk approval dialog before risky work proceeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        if (String(input).includes("/phase/5/jobs")) {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: true,
              status: "waiting_for_approval",
              sandbox: "workspace_write",
              message: "This starts a long-running experiment or training job."
            })
          };
        }
        return { ok: true, json: async () => phaseFiveProjectsResponse };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open experiment_project/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByRole("dialog", { name: /approval required/i })).toBeInTheDocument();
    expect(screen.getByText("This starts a long-running experiment or training job.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve high-risk action/i })).toBeInTheDocument();
  });

  it("submits approval and continues a high-risk job", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        if (String(input) === "/api/jobs/job-risk/approval") {
          return {
            ok: true,
            json: async () => ({ approval_id: 1, user_action: "approved", final_status: "approved" })
          };
        }
        if (String(input) === "/api/jobs/job-risk/continue") {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: false,
              status: "completed",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input).includes("/phase/5/jobs")) {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: true,
              status: "waiting_for_approval",
              sandbox: "workspace_write",
              message: "This starts a long-running experiment or training job."
            })
          };
        }
        return { ok: true, json: async () => phaseFiveProjectsResponse };
      })
    );

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open experiment_project/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await userEvent.click(await screen.findByRole("button", { name: /approve high-risk action/i }));

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/jobs/job-risk/approval",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/jobs/job-risk/continue",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("preserves a custom experiment instruction after high-risk approval", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        if (String(input) === "/api/jobs/job-risk/approval") {
          return {
            ok: true,
            json: async () => ({ approval_id: 1, user_action: "approved", final_status: "approved" })
          };
        }
        if (String(input) === "/api/jobs/job-risk/continue") {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: false,
              status: "completed",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input).includes("/phase/5/jobs")) {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-risk",
              requires_approval: true,
              status: "waiting_for_approval",
              sandbox: "workspace_write",
              message: "This starts a long-running experiment or training job."
            })
          };
        }
        return { ok: true, json: async () => phaseFiveProjectsResponse };
      })
    );

    const instruction = "Run a tiny closed-loop synthetic data smoke experiment and write metrics.json.";
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open experiment_project/i }));
    await userEvent.type(screen.getByLabelText("Prompt"), instruction);
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await userEvent.click(await screen.findByRole("button", { name: /approve high-risk action/i }));

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/jobs/job-risk/continue",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "Continue Run Experiments", prompt: instruction })
      })
    );
  });

  it("sends the rejection to the backend when the user rejects a high-risk action", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input) === "/api/jobs/job-risk/approval") {
        return {
          ok: true,
          json: async () => ({ approval_id: 1, user_action: "rejected", final_status: "rejected" })
        };
      }
      if (String(input).includes("/phase/5/jobs")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-risk",
            requires_approval: true,
            status: "waiting_for_approval",
            sandbox: "workspace_write",
            message: "This starts a long-running experiment or training job."
          })
        };
      }
      return { ok: true, json: async () => phaseFiveProjectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open experiment_project/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await userEvent.click(await screen.findByRole("button", { name: /reject/i }));

    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/jobs/job-risk/approval",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ user_action: "rejected" })
      })
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/jobs/job-risk/continue",
      expect.anything()
    );
  });

  it("renders markdown artifacts by default and can toggle to raw text", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /open files/i }));

    expect(await screen.findByText("phase1_topic.md")).toBeInTheDocument();
    expect(screen.queryByText("metrics.csv")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /open phase1_topic.md/i }));

    const preview = screen.getByLabelText("Artifact preview");
    expect(await within(preview).findByRole("heading", { name: "Topic Summary", level: 1 })).toBeInTheDocument();
    expect(within(preview).getByRole("list")).toBeInTheDocument();
    expect(within(preview).getByRole("table")).toBeInTheDocument();
    expect(within(preview).queryByText("# Topic Summary")).not.toBeInTheDocument();

    await userEvent.click(within(preview).getByRole("button", { name: "Raw" }));

    expect(await within(preview).findByText(/# Topic Summary/)).toBeInTheDocument();

    await userEvent.click(within(preview).getByRole("button", { name: "Markdown" }));

    expect(await within(preview).findByRole("heading", { name: "Topic Summary", level: 1 })).toBeInTheDocument();
  });

  it("filters artifacts by tab category", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /open files/i }));

    expect(await screen.findByText("phase1_topic.md")).toBeInTheDocument();
    expect(screen.queryByText("metrics.csv")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Results" }));

    expect(await screen.findByText("metrics.csv")).toBeInTheDocument();
    expect(screen.queryByText("phase1_topic.md")).not.toBeInTheDocument();
  });

  it("runs result collection and manuscript validation from the artifact screen", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /open files/i }));
    await userEvent.click(await screen.findByRole("button", { name: /collect results/i }));

    expect(await screen.findByText("Result collection passed")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/collect-results",
      expect.objectContaining({ method: "POST" })
    );

    await userEvent.click(screen.getByRole("button", { name: /validate manuscript/i }));

    expect(await screen.findByText("Manuscript validation passed")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/validate-manuscript",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("adopts an already-active job when the phase dashboard mounts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input) === "/api/projects/synthetic_segmentation/jobs?active=true") {
        return {
          ok: true,
          json: async () => [
            {
              job_id: "job-resumed",
              project_dir: "synthetic_segmentation",
              phase: 4,
              status: "running",
              approval_state: "none",
              sandbox: "workspace_write",
              started_at: "2026-06-11T21:00:00Z",
              completed_at: null,
              last_error: null
            }
          ]
        };
      }
      if (String(input).endsWith("/artifacts")) {
        return { ok: true, json: async () => [] };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();
    expect(FakeEventSource.instances.at(-1)?.url).toBe("/api/jobs/job-resumed/events/stream");
  });

  it("issues exactly one job request when Send is double-clicked", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    const runButton = screen.getByRole("button", { name: /send/i });
    act(() => {
      runButton.click();
      runButton.click();
    });

    expect(await screen.findByText("Rev2Agent is working now.")).toBeInTheDocument();

    const phaseJobPosts = vi
      .mocked(fetch)
      .mock.calls.filter(([input, init]) => String(input).includes("/phase/4/jobs") && init?.method === "POST");
    expect(phaseJobPosts).toHaveLength(1);
  });

  it("shows the backend detail when manuscript validation fails", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input) === "/api/projects/synthetic_segmentation/validate-manuscript") {
        return {
          ok: true,
          json: async () => ({
            status: "failed",
            return_code: 1,
            stderr: "Validation failed:\nmanuscript/main.tex: 2 unresolved references",
            artifacts: []
          })
        };
      }
      if (String(input).endsWith("/artifacts")) {
        return { ok: true, json: async () => [] };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /open files/i }));
    await userEvent.click(await screen.findByRole("button", { name: /validate manuscript/i }));

    expect(
      await screen.findByText(
        /Manuscript validation failed: Validation failed: manuscript\/main\.tex: 2 unresolved references/
      )
    ).toBeInTheDocument();
  });

  it("renders project timestamps in local time", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      return {
        ok: true,
        json: async () => ({
          ...projectsResponse,
          projects: [{ ...projectsResponse.projects[0], updated_at: "2026-06-11T22:14:26Z" }]
        })
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText(expectedLocalTimestamp("2026-06-11T22:14:26Z"))).toBeInTheDocument();
    expect(screen.queryByText("2026-06-11T22:14:26Z")).not.toBeInTheDocument();
  });

  it("coalesces token delta events into one row and supersedes them with the full message", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("Rev2Agent is working now.");

    const source = FakeEventSource.instances.at(-1);
    source?.emit({ event_id: 1, event_type: "item/agent_message/delta", summary: "I'" });
    source?.emit({ event_id: 2, event_type: "item/agent_message/delta", summary: "ll" });
    source?.emit({ event_id: 3, event_type: "item/agent_message/delta", summary: " resume" });

    expect(await screen.findByText("I'll resume")).toBeInTheDocument();
    expect(screen.queryByText("I'")).not.toBeInTheDocument();
    expect(screen.queryByText("ll")).not.toBeInTheDocument();

    source?.emit({
      event_id: 4,
      event_type: "assistant_message",
      summary: "I'll resume the interrupted experiment run."
    });

    expect(await screen.findByText("I'll resume the interrupted experiment run.")).toBeInTheDocument();
    expect(screen.queryByText("I'll resume")).not.toBeInTheDocument();
    expect(screen.getAllByText(/I'll resume/)).toHaveLength(1);
  });

  it("drains tail events from the events endpoint when the SSE stream closes", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input).includes("/jobs?active=")) {
        return { ok: true, json: async () => [] };
      }
      if (String(input) === "/api/jobs/job-1/events") {
        return {
          ok: true,
          json: async () => [
            { event_id: 41, event_type: "turn_completed", summary: "Turn completed" },
            {
              event_id: 42,
              event_type: "assistant_message",
              summary: "Next Phase 1 question: Which benchmark should be the primary target?"
            },
            {
              event_id: 43,
              event_type: "completion_warning",
              summary: "Job completed but the project state did not change."
            }
          ]
        };
      }
      if (String(input).includes("/phase/4/jobs")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-1",
            requires_approval: false,
            status: "running",
            sandbox: "workspace_write"
          })
        };
      }
      if (String(input).endsWith("/artifacts")) {
        return { ok: true, json: async () => [] };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("Rev2Agent is working now.");

    const source = FakeEventSource.instances.at(-1);
    source?.emit({ event_id: 41, event_type: "turn_completed", summary: "Turn completed" });
    source?.emit({ event_type: "job_status", job_id: "job-1", status: "completed" });

    expect(await screen.findByText("Next Phase 1 question: Which benchmark should be the primary target?")).toBeInTheDocument();
    expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
    // Internal turn status events are not part of the user-facing transcript.
    expect(screen.queryByText("Turn completed")).not.toBeInTheDocument();
    expect(screen.queryByText("Job completed but the project state did not change.")).not.toBeInTheDocument();
  });

  it("drains tail events when polling notices the job finished after the stream went quiet", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    try {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
        }
        if (String(input).includes("/jobs?active=")) {
          return { ok: true, json: async () => [] };
        }
        if (String(input) === "/api/jobs/job-1/events") {
          return {
            ok: true,
            json: async () => [
              {
                event_id: 6,
                event_type: "assistant_message",
                summary: "Next Phase 1 question: Which dataset split should be used?"
              },
              {
                event_id: 7,
                event_type: "completion_warning",
                summary: "Job completed but the project state did not change."
              }
            ]
          };
        }
        if (String(input) === "/api/jobs/job-1") {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-1",
              project_dir: "synthetic_segmentation",
              phase: 4,
              status: "completed",
              approval_state: "not_required",
              sandbox: "workspace_write",
              started_at: "2026-06-11T21:00:00Z",
              completed_at: "2026-06-11T21:05:00Z",
              last_error: null
            })
          };
        }
        if (String(input).includes("/phase/4/jobs")) {
          return {
            ok: true,
            json: async () => ({
              job_id: "job-1",
              requires_approval: false,
              status: "running",
              sandbox: "workspace_write"
            })
          };
        }
        if (String(input).endsWith("/artifacts")) {
          return { ok: true, json: async () => [] };
        }
        return { ok: true, json: async () => projectsResponse };
      });
      vi.stubGlobal("fetch", fetchMock);

      render(<App />);

      await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
      await userEvent.click(screen.getByRole("button", { name: /send/i }));
      await screen.findByText("Rev2Agent is working now.");

      // Fire the 5s poll fallback; the SSE stream never reported the close.
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      expect(await screen.findByText("Rev2Agent is waiting for your next prompt.")).toBeInTheDocument();
      expect(await screen.findByText("Next Phase 1 question: Which dataset split should be used?")).toBeInTheDocument();
      expect(screen.queryByText("Job completed but the project state did not change.")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("guides the user when a reconciled job is waiting for approval", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/settings") {
        return { ok: true, json: async () => settingsResponse };
      }
      if (String(input) === "/api/projects/synthetic_segmentation/jobs?active=true") {
        return {
          ok: true,
          json: async () => [
            {
              job_id: "job-waiting",
              project_dir: "synthetic_segmentation",
              phase: 4,
              status: "waiting_for_approval",
              approval_state: "required",
              sandbox: "workspace_write",
              started_at: "2026-06-11T21:00:00Z",
              completed_at: null,
              last_error: null
            }
          ]
        };
      }
      if (/\/api\/jobs\/[^/]+\/events$/.test(String(input))) {
        return { ok: true, json: async () => [] };
      }
      if (String(input).endsWith("/artifacts")) {
        return { ok: true, json: async () => [] };
      }
      return { ok: true, json: async () => projectsResponse };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(
      await screen.findByText(
        "Rev2Agent is waiting for approval. Press Stop to clear this waiting job, then run the step again."
      )
    ).toBeInTheDocument();
    // Stop must stay available so the user can clear the stuck job.
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();
    // The job is not running, so no elapsed timer is shown.
    expect(screen.queryByText(/^\d{2}:\d{2}$/)).not.toBeInTheDocument();
    // The console still follows the waiting job's history.
    expect(FakeEventSource.instances.at(-1)?.url).toBe("/api/jobs/job-waiting/events/stream");
  });
});
