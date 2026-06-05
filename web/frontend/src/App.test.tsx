import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  url: string;
  listeners = new Map<string, (event: MessageEvent) => void>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(eventName: string, callback: (event: MessageEvent) => void) {
    this.listeners.set(eventName, callback);
  }

  close = vi.fn();

  emit(eventName: string, data: unknown) {
    this.listeners.get(eventName)?.({ data: JSON.stringify(data) } as MessageEvent);
  }
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
              status: "completed",
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
              status: "completed",
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

    expect(screen.getByRole("heading", { name: "Design Experiments" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run next step/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view files/i })).toBeInTheDocument();
  });

  it("shows the latest artifact preview on the phase dashboard and links to files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/settings") {
          return { ok: true, json: async () => settingsResponse };
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

    expect(await screen.findByText("2026-06-02 10:00:00")).toBeInTheDocument();
    expect(screen.queryByText("2026-06-02T10:00:00Z")).not.toBeInTheDocument();
  });

  it("shows Phase 7 choices when tectonic is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => ({
        ok: true,
        json: async () => (String(input) === "/api/settings" ? missingTectonicSettingsResponse : phaseSevenProjectsResponse)
      }))
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

    await screen.findByRole("button", { name: /run next step/i });
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

    expect(await screen.findByText("Job job-phase7-skip-pdf completed")).toBeInTheDocument();

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
    expect(fetch).not.toHaveBeenCalledWith("/api/projects", expect.objectContaining({ method: "POST" }));

    await userEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(screen.getByText("Research idea is required.")).toBeInTheDocument();

    const idea =
      "Closed-loop synthetic data generation: train a downstream task on existing data, generate synthetic data to improve performance, retrain, evaluate, and repeat.";
    await userEvent.type(screen.getByLabelText("Research idea"), idea);
    await userEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(await screen.findByRole("heading", { name: "Choose Topic" })).toBeInTheDocument();
    expect(screen.getByText("_new_project_draft")).toBeInTheDocument();
    expect(screen.getByText(idea)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ research_idea: idea })
      })
    );
  });

  it("includes the project topic in the Phase 1 launch prompt", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/settings") {
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
    await userEvent.click(screen.getByRole("button", { name: /run next step/i }));

    expect(await screen.findByText("Job job-phase1 completed")).toBeInTheDocument();

    const phaseRequest = fetchMock.mock.calls.find(([input]) => String(input).includes("/phase/1/jobs"));
    const requestBody = JSON.parse(String(phaseRequest?.[1]?.body ?? "{}"));

    expect(requestBody.prompt).toMatch(/Closed-loop synthetic data generation/i);
  });

  it("launches the current phase job from the dashboard", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /run next step/i }));

    expect(await screen.findByText("Job job-1 completed")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/projects/synthetic_segmentation/phase/4/jobs",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("disables experiment execution outside Phase 5", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(screen.getByRole("button", { name: /run experiment scripts/i })).toBeDisabled();
  });

  it("renders live SDK job events from the SSE stream", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /run next step/i }));

    expect(FakeEventSource.instances.at(-1)?.url).toBe("/api/jobs/job-1/events/stream");

    FakeEventSource.instances.at(-1)?.emit("turn_completed", {
      event_id: 5,
      event_type: "turn_completed",
      summary: "Codex produced the experiment design summary."
    });

    expect(await screen.findByText("Codex produced the experiment design summary.")).toBeInTheDocument();
  });

  it("keeps the live console mounted when an SSE event has invalid data", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /run next step/i }));

    FakeEventSource.instances.at(-1)?.emit("turn_completed", undefined);

    expect(await screen.findByText("A job event could not be displayed.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live Run Console" })).toBeInTheDocument();
  });

  it("interrupts the active job from the dashboard", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /run next step/i }));
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));

    expect(await screen.findByText("Job job-1 interrupted")).toBeInTheDocument();
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
    await userEvent.click(screen.getByRole("button", { name: /run experiment scripts/i }));

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
    await userEvent.click(screen.getByRole("button", { name: /run experiment scripts/i }));
    await userEvent.click(await screen.findByRole("button", { name: /approve high-risk action/i }));

    expect(await screen.findByText("Job job-risk completed")).toBeInTheDocument();
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
    await userEvent.type(screen.getByLabelText("Phase instruction"), instruction);
    await userEvent.click(screen.getByRole("button", { name: /run experiment scripts/i }));
    await userEvent.click(await screen.findByRole("button", { name: /approve high-risk action/i }));

    expect(await screen.findByText("Job job-risk completed")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/jobs/job-risk/continue",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "Run experiment scripts", prompt: instruction })
      })
    );
  });

  it("renders markdown artifacts by default and can toggle to raw text", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /view files/i }));

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
    await userEvent.click(screen.getByRole("button", { name: /view files/i }));

    expect(await screen.findByText("phase1_topic.md")).toBeInTheDocument();
    expect(screen.queryByText("metrics.csv")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Results" }));

    expect(await screen.findByText("metrics.csv")).toBeInTheDocument();
    expect(screen.queryByText("phase1_topic.md")).not.toBeInTheDocument();
  });

  it("runs result collection and manuscript validation from the artifact screen", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /view files/i }));
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
});
