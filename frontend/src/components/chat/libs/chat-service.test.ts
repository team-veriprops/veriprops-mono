import { describe, it, expect } from "vitest";
import { ChatService } from "./chat-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { ConversationType, MessageKind } from "@/types/chat";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: (url: string) => rec("get")(url),
    post: rec("post"),
    put: rec("put"),
    patch: rec("patch"),
    delete: rec("delete"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("ChatService contract (mirrors /chat + /admin/messages)", () => {
  it("lists conversations and the unread counter", async () => {
    const { http, calls } = mockHttp();
    const svc = new ChatService(http);
    await svc.listConversations();
    await svc.unreadCount();
    expect(calls[0]).toMatchObject({ method: "get", url: "/chat/conversations" });
    expect(calls[1]).toMatchObject({ method: "get", url: "/chat/unread" });
  });

  it("lists a conversation's messages (paged) and marks it read", async () => {
    const { http, calls } = mockHttp();
    const svc = new ChatService(http);
    await svc.listMessages("conv-1", 0, 30);
    await svc.markRead("conv-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/chat/conversations/conv-1/messages?page=0&pageSize=30" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/chat/conversations/conv-1/read" });
  });

  it("builds the proxied per-user SSE stream URL", () => {
    const { http } = mockHttp();
    expect(new ChatService(http).streamUrl()).toBe("/api/chat/stream");
  });

  it("opens the customer thread and sends (with clarification kind)", async () => {
    const { http, calls } = mockHttp();
    const svc = new ChatService(http);
    await svc.openCustomerThread("ver-1");
    await svc.customerSend("ver-1", "hello", MessageKind.CLARIFICATION_REQUEST);
    expect(calls[0]).toMatchObject({ method: "get", url: "/verifications/ver-1/chat" });
    expect(calls[1]).toMatchObject({
      method: "post",
      url: "/verifications/ver-1/chat/messages",
      body: { body: "hello", kind: MessageKind.CLARIFICATION_REQUEST },
    });
  });

  it("sends an agent message tagged to a task", async () => {
    const { http, calls } = mockHttp();
    await new ChatService(http).agentSend("ver-1", "on site now", "task-9");
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/agents/verifications/ver-1/chat/messages",
      body: { body: "on site now", taskId: "task-9" },
    });
  });

  it("reviews held messages (approve / reject) and lists the queue", async () => {
    const { http, calls } = mockHttp();
    const svc = new ChatService(http);
    await svc.heldQueue(0, 20);
    await svc.approveMessage("msg-1");
    await svc.rejectMessage("msg-2");
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/messages/held?page=0&pageSize=20" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/messages/msg-1/approve" });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/messages/msg-2/reject" });
  });

  it("opens an admin thread by channel type", async () => {
    const { http, calls } = mockHttp();
    await new ChatService(http).openAdminThread("ver-1", ConversationType.ADMIN_AGENT);
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/verifications/ver-1/chat?type=ADMIN_AGENT" });
  });
});
