"use client";

import { useCallback } from "react";
import { REFETCH_INTERVAL_MS, SHORT_REFETCH_INTERVAL_MS } from "@lib/config/app";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { useUserStream } from "@lib/useUserStream";
import { ConversationType, MessageKind } from "@/types/chat";
import { ChatService } from "./chat-service";

const service = new ChatService(httpClient);

export const chatKeys = {
  conversations: () => ["chat", "conversations"] as const,
  unread: () => ["chat", "unread"] as const,
  messages: (conversationId: string, page: number) => ["chat", "messages", conversationId, page] as const,
  held: (page: number) => ["chat", "held", page] as const,
};

/**
 * Subscribes to the per-user SSE stream once and invalidates the Chat counter +
 * conversation list on any pushed chat event. Mount high in the tree (e.g. the top nav)
 * so the counter stays live across the app.
 */
export function useChatRealtime(enabled = true) {
  const qc = useQueryClient();
  const onEvent = useCallback(
    (evt: { event: string }) => {
      if (evt.event === "chat_message" || evt.event === "chat_unread") {
        qc.invalidateQueries({ queryKey: chatKeys.unread() });
        qc.invalidateQueries({ queryKey: chatKeys.conversations() });
        qc.invalidateQueries({ queryKey: ["chat", "messages"] });
      }
    },
    [qc],
  );
  useUserStream({ onEvent, enabled });
}

export function useChatUnreadQuery(enabled = true) {
  return useQuery({
    queryKey: chatKeys.unread(),
    enabled,
    queryFn: async () => (await service.unreadCount()).data?.count ?? 0,
    refetchInterval: REFETCH_INTERVAL_MS, // polling fallback shares the counter shape
  });
}

export function useConversationsQuery(enabled = true) {
  return useQuery({
    queryKey: chatKeys.conversations(),
    enabled,
    queryFn: async () => (await service.listConversations()).data ?? [],
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useMessagesQuery(conversationId: string | null, page = 0, enabled = true) {
  return useQuery({
    queryKey: chatKeys.messages(conversationId ?? "none", page),
    enabled: !!conversationId && enabled,
    queryFn: async () => (await service.listMessages(conversationId as string, page)).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useMarkReadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => service.markRead(conversationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: chatKeys.unread() });
      qc.invalidateQueries({ queryKey: chatKeys.conversations() });
    },
  });
}

// ── Thread openers + sends ───────────────────────────────────────────

export function useCustomerThreadQuery(verificationId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["chat", "customer-thread", verificationId ?? "none"],
    enabled: !!verificationId && enabled,
    queryFn: async () => (await service.openCustomerThread(verificationId as string)).data ?? null,
  });
}

export function useAgentThreadQuery(verificationId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["chat", "agent-thread", verificationId ?? "none"],
    enabled: !!verificationId && enabled,
    queryFn: async () => (await service.openAgentThread(verificationId as string)).data ?? null,
  });
}

export function useSupportThreadQuery(enabled = true) {
  return useQuery({
    queryKey: ["chat", "support-thread"],
    enabled,
    queryFn: async () => (await service.openSupportThread()).data ?? null,
  });
}

export function useAdminThreadQuery(
  verificationId: string | null,
  type: ConversationType,
  enabled = true,
) {
  return useQuery({
    queryKey: ["chat", "admin-thread", verificationId ?? "none", type],
    enabled: !!verificationId && enabled,
    queryFn: async () => (await service.openAdminThread(verificationId as string, type)).data ?? null,
  });
}

interface SendVars {
  verificationId: string;
  body: string;
  taskId?: string;
  kind?: MessageKind;
  type?: ConversationType;
}

export function useSendMessageMutation(role: "customer" | "agent" | "admin" | "support") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: SendVars) => {
      if (role === "customer") return service.customerSend(vars.verificationId, vars.body, vars.kind);
      if (role === "agent") return service.agentSend(vars.verificationId, vars.body, vars.taskId);
      if (role === "support") return service.supportSend(vars.body);
      return service.adminSend(
        vars.verificationId,
        vars.body,
        vars.type ?? ConversationType.ADMIN_AGENT,
        vars.taskId,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", "messages"] });
      qc.invalidateQueries({ queryKey: chatKeys.conversations() });
    },
  });
}

/**
 * Send into a thread the caller is a member of, addressed by conversation id.
 *
 * The admin WhatsApp inbox needs this rather than `useSendMessageMutation`: a §26.8
 * enquiry thread often has no verification behind it yet, so there is no id to send by.
 */
export function useConversationSendMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ conversationId, body }: { conversationId: string; body: string }) =>
      service.sendToConversation(conversationId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", "messages"] });
      qc.invalidateQueries({ queryKey: chatKeys.conversations() });
      // Replying takes a WhatsApp thread off the bot (D57), so the mode banner beside
      // this thread is now stale.
      qc.invalidateQueries({ queryKey: ["whatsapp-bot", "session"] });
    },
  });
}

// ── Admin hold review ────────────────────────────────────────────────

export function useHeldQueueQuery(page = 0, enabled = true) {
  return useQuery({
    queryKey: chatKeys.held(page),
    enabled,
    queryFn: async () => (await service.heldQueue(page)).data ?? null,
    refetchInterval: SHORT_REFETCH_INTERVAL_MS,
  });
}

export function useReviewMessageMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, approve }: { messageId: string; approve: boolean }) =>
      approve ? service.approveMessage(messageId) : service.rejectMessage(messageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat", "held"] }),
  });
}

export { service as chatService };
