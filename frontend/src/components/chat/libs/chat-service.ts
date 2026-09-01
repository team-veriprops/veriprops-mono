import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_HISTORY_PAGE_SIZE,CHAT_MESSAGES_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import {
  ChatMessage,
  Conversation,
  ConversationType,
  HeldMessage,
  MessageKind,
} from "@/types/chat";

/**
 * Communication-layer API. Mirrors the backend controllers at
 * `app/domain/communication`. Sends are HTTP POST; live delivery is over the per-user
 * SSE stream (§4.9). Backend owns the fraud-hold decision, unread counts, and the
 * customer-safe sender projection (§11.3).
 */
export class ChatService {
  constructor(private readonly http: HttpClient) {}

  // ── Shared member-gated surface (/chat) ─────────────────────────────

  listConversations(): Promise<SuccessResponse<Conversation[]>> {
    return this.http.get(`/chat/conversations`);
  }

  unreadCount(): Promise<SuccessResponse<{ count: number }>> {
    return this.http.get(`/chat/unread`);
  }

  listMessages(conversationId: string, page = 0, pageSize = CHAT_MESSAGES_PAGE_SIZE): Promise<SuccessResponse<Page<ChatMessage>>> {
    return this.http.get(`/chat/conversations/${conversationId}/messages?page=${page}&pageSize=${pageSize}`);
  }

  markRead(conversationId: string): Promise<SuccessResponse<{ count: number }>> {
    return this.http.post(`/chat/conversations/${conversationId}/read`);
  }

  /**
   * Post into a thread by id — the member-gated path, used where the caller holds a
   * conversation rather than a verification (the admin WhatsApp inbox: a §7.8 enquiry
   * thread has no case behind it yet). `senderKind` is derived server-side from the
   * caller's role, never sent.
   */
  sendToConversation(conversationId: string, body: string): Promise<SuccessResponse<ChatMessage>> {
    return this.http.post(`/chat/conversations/${conversationId}/messages`, { body });
  }

  /** Per-user SSE stream URL (§4.9, §N) — consumed by EventSource in useUserStream. */
  streamUrl(): string {
    return `/api/chat/stream`;
  }

  // ── Thread openers ─────────────────────────────────────────────────

  openCustomerThread(verificationId: string): Promise<SuccessResponse<Conversation>> {
    return this.http.get(`/verifications/${verificationId}/chat`);
  }

  customerSend(verificationId: string, body: string, kind: MessageKind = MessageKind.CHAT): Promise<SuccessResponse<ChatMessage>> {
    return this.http.post(`/verifications/${verificationId}/chat/messages`, { body, kind });
  }

  openAgentThread(verificationId: string): Promise<SuccessResponse<Conversation>> {
    return this.http.get(`/agents/verifications/${verificationId}/chat`);
  }

  agentSend(verificationId: string, body: string, taskId?: string): Promise<SuccessResponse<ChatMessage>> {
    return this.http.post(`/agents/verifications/${verificationId}/chat/messages`, { body, taskId });
  }

  openSupportThread(): Promise<SuccessResponse<Conversation>> {
    return this.http.get(`/support/chat`);
  }

  supportSend(body: string): Promise<SuccessResponse<ChatMessage>> {
    return this.http.post(`/support/chat/messages`, { body });
  }

  // ── Admin surface (RBAC-gated) ─────────────────────────────────────

  heldQueue(page = 0, pageSize = DEFAULT_HISTORY_PAGE_SIZE): Promise<SuccessResponse<Page<HeldMessage>>> {
    return this.http.get(`/admin/messages/held?page=${page}&pageSize=${pageSize}`);
  }

  approveMessage(messageId: string): Promise<SuccessResponse<{ id: string; state: string }>> {
    return this.http.post(`/admin/messages/${messageId}/approve`);
  }

  rejectMessage(messageId: string): Promise<SuccessResponse<{ id: string; state: string }>> {
    return this.http.post(`/admin/messages/${messageId}/reject`);
  }

  openAdminThread(verificationId: string, type: ConversationType): Promise<SuccessResponse<Conversation>> {
    return this.http.get(`/admin/verifications/${verificationId}/chat?type=${type}`);
  }

  adminSend(
    verificationId: string,
    body: string,
    conversationType: ConversationType,
    taskId?: string,
  ): Promise<SuccessResponse<ChatMessage>> {
    return this.http.post(`/admin/verifications/${verificationId}/chat/messages`, {
      body,
      conversationType,
      taskId,
    });
  }
}
