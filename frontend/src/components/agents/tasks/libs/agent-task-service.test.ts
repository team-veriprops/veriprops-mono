import { describe, it, expect } from "vitest";
import { AgentTaskService } from "./agent-task-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { EvidenceKind } from "@/types/agentTask";
import { TaskState } from "@/types/adminVerification";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: rec("get"),
    post: rec("post"),
    put: rec("put"),
    delete: rec("delete"),
    patch: rec("patch"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("AgentTaskService contract (mirrors /agents/tasks backend routes)", () => {
  it("lists my tasks with state + snake_case pagination", async () => {
    const { http, calls } = mockHttp();
    await new AgentTaskService(http).list(TaskState.PENDING, 1, 10);
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toBe("/agents/tasks?state=PENDING&page=1&page_size=10");
  });

  it("fetches the agent dashboard summary from /agents/tasks/summary", async () => {
    const { http, calls } = mockHttp();
    await new AgentTaskService(http).getSummary();
    expect(calls[0]).toMatchObject({ method: "get", url: "/agents/tasks/summary" });
  });

  it("accepts / declines / starts a task", async () => {
    const { http, calls } = mockHttp();
    const svc = new AgentTaskService(http);
    await svc.accept("t-1");
    await svc.decline("t-1", "too far");
    await svc.start("t-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/agents/tasks/t-1/accept" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/agents/tasks/t-1/decline", body: { reason: "too far" } });
    expect(calls[2]).toMatchObject({ method: "post", url: "/agents/tasks/t-1/start" });
  });

  it("uploads evidence as multipart FormData with kind + gps", async () => {
    const { http, calls } = mockHttp();
    const file = new File(["x"], "proof.jpg", { type: "image/jpeg" });
    await new AgentTaskService(http).uploadEvidence("t-1", file, EvidenceKind.PHOTO, {
      latitude: 6.5,
      longitude: 3.3,
    });
    expect(calls[0]).toMatchObject({ method: "post", url: "/agents/tasks/t-1/evidence" });
    const body = calls[0].body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("kind")).toBe(EvidenceKind.PHOTO);
    expect(body.get("gps_latitude")).toBe("6.5");
    expect(body.get("file")).toBeInstanceOf(File);
  });

  it("submits the role payload wrapped under `payload`", async () => {
    const { http, calls } = mockHttp();
    await new AgentTaskService(http).submit("t-1", { occupancy_status: "vacant" });
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/agents/tasks/t-1/submit",
      body: { payload: { occupancy_status: "vacant" } },
    });
  });

  it("fetches PII-safe task history with snake_case pagination (§19.3)", async () => {
    const { http, calls } = mockHttp();
    await new AgentTaskService(http).getHistory("t-1", 0, 20);
    expect(calls[0]).toMatchObject({ method: "get" });
    expect(calls[0].url).toBe("/agents/tasks/t-1/history?page=0&page_size=20");
  });
});
