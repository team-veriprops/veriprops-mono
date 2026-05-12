import { httpClient } from "@/containers";

export type SenderRole = "CUSTOMER" | "ADMIN" | "AGENT" | "SYSTEM";
export type MessageType = "TEXT" | "SYSTEM" | "ATTACHMENT";
export type ThreadType = "CUSTOMER_ADMIN" | "ADMIN_AGENT";

export interface ThreadMessage {
  id: string;
  threadId: string;
  senderId: string | null;
  senderRole: SenderRole;
  messageType: MessageType;
  body: string;
  attachmentKey: string | null;
  isHeld: boolean;
  dateCreated: string;
}

export interface Thread {
  id: string;
  threadType: ThreadType;
  verificationId: string;
  taskId: string | null;
  dateCreated: string;
}

export interface PostMessagePayload {
  body: string;
  messageType?: MessageType;
}

export class ThreadService {
  getByVerification(vid: string): Promise<{ data: Thread }> {
    return httpClient.get(`/threads/by-verification/${vid}`);
  }

  getByTask(taskId: string): Promise<{ data: Thread }> {
    return httpClient.get(`/threads/by-task/${taskId}`);
  }

  listMessages(threadId: string, limit = 50): Promise<{ data: ThreadMessage[] }> {
    return httpClient.get(`/threads/${threadId}/messages?limit=${limit}`);
  }

  postMessage(threadId: string, payload: PostMessagePayload): Promise<{ data: ThreadMessage }> {
    return httpClient.post(`/threads/${threadId}/messages`, payload);
  }
}

export const threadService = new ThreadService();

export function buildWsUrl(threadId: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host;
  const csrf = getCookie("csrf_access") ?? "";
  return `${proto}://${host}/api/ws/threads/${threadId}?token=${encodeURIComponent(csrf)}`;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}
