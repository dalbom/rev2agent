import { render, screen } from "@testing-library/react";
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

describe("App", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/projects" && init?.method === "POST") {
          return {
            ok: true,
            json: async () => ({
              project_dir: "_new_project_draft",
              phase: 1,
              phase_label: "Choose Topic",
              phase_status: "in_progress",
              project_status: "active",
              topic: "",
              updated_at: "2026-06-02T11:00:00Z",
              active_runs: 0,
              healthy: true
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
        if (String(input).endsWith("/artifacts/1")) {
          return {
            ok: true,
            json: async () => ({
              artifact_id: 1,
              kind: "text",
              mime_type: "text/markdown",
              content: "# Topic Summary\n",
              size_bytes: 16
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

  it("routes setup-required repositories to settings and safety", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ ...projectsResponse, setup_required: true, config_exists: false })
      }))
    );

    render(<App />);

    expect(await screen.findByText("Settings And Safety")).toBeInTheDocument();
    expect(screen.getByText(".rev2agent_config.json is missing")).toBeInTheDocument();
  });

  it("opens phase dashboard from a project card", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));

    expect(screen.getByRole("heading", { name: "Design Experiments" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run next step/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view files/i })).toBeInTheDocument();
  });

  it("starts a new draft project from project home", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /start new project/i }));

    expect(await screen.findByRole("heading", { name: "Choose Topic" })).toBeInTheDocument();
    expect(screen.getByText("_new_project_draft")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/projects", { method: "POST" });
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
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /run experiment scripts/i }));

    expect(await screen.findByRole("dialog", { name: /approval required/i })).toBeInTheDocument();
    expect(screen.getByText("This starts a long-running experiment or training job.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve high-risk action/i })).toBeInTheDocument();
  });

  it("submits approval and continues a high-risk job", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
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

  it("lists artifacts and previews safe text content", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /open synthetic_segmentation/i }));
    await userEvent.click(screen.getByRole("button", { name: /view files/i }));

    expect(await screen.findByText("phase1_topic.md")).toBeInTheDocument();
    expect(screen.getByText("metrics.csv")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /open phase1_topic.md/i }));

    expect(await screen.findByText("# Topic Summary")).toBeInTheDocument();
  });
});
