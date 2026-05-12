"use client";

import { useEffect, useRef, useState, useCallback, FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { threadService, buildWsUrl, ThreadMessage } from "./libs/thread-service";
import { Loader2, Send } from "lucide-react";
import { getErrorMessage } from "@lib/utils";

interface Props {
  threadId: string;
  currentUserId?: string;
  currentRole: "CUSTOMER" | "ADMIN" | "AGENT";
  placeholder?: string;
}

const ROLE_LABEL: Record<string, string> = {
  CUSTOMER: "You",
  ADMIN: "Admin",
  AGENT: "Agent",
  SYSTEM: "System",
};

const queryKey = (threadId: string) => ["threads", threadId, "messages"];

export default function ThreadView({ threadId, currentUserId, currentRole, placeholder = "Type a message…" }: Props) {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<"connecting" | "open" | "closed">("connecting");

  const { data, isLoading } = useQuery({
    queryKey: queryKey(threadId),
    queryFn: () => threadService.listMessages(threadId),
    staleTime: 30_000,
  });

  const messages: ThreadMessage[] = (data as any)?.data ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const appendMessage = useCallback(
    (msg: ThreadMessage) => {
      qc.setQueryData<any>(queryKey(threadId), (prev: any) => {
        const existing: ThreadMessage[] = prev?.data ?? [];
        if (existing.some((m) => m.id === msg.id)) return prev;
        return { ...prev, data: [...existing, msg] };
      });
    },
    [qc, threadId],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = buildWsUrl(threadId);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => setWsStatus("open");
    ws.onclose = () => setWsStatus("closed");
    ws.onerror = () => setWsStatus("closed");
    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        if (payload.type === "message" && payload.data) {
          appendMessage(payload.data as ThreadMessage);
        }
      } catch {
        // ignore malformed frames
      }
    };

    return () => {
      ws.close();
    };
  }, [threadId, appendMessage]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await threadService.postMessage(threadId, { body: trimmed, messageType: "TEXT" });
      appendMessage((res as any).data);
      setBody("");
    } catch (err) {
      setSendError(getErrorMessage(err as Error));
    } finally {
      setSending(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" data-testid="thread-view">
      {/* Status bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
        <span
          className={`inline-block w-2 h-2 rounded-full ${wsStatus === "open" ? "bg-green-500" : wsStatus === "connecting" ? "bg-yellow-400" : "bg-gray-300"}`}
        />
        {wsStatus === "open" ? "Live" : wsStatus === "connecting" ? "Connecting…" : "Disconnected"}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">No messages yet. Start the conversation.</p>
        )}
        {messages.map((msg) => {
          const isOwn = msg.senderRole === currentRole;
          const isSystem = msg.senderRole === "SYSTEM" || msg.messageType === "SYSTEM";

          if (isSystem) {
            return (
              <div key={msg.id} className="flex justify-center" data-testid="thread-system-message">
                <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1">{msg.body}</span>
              </div>
            );
          }

          return (
            <div
              key={msg.id}
              className={`flex ${isOwn ? "justify-end" : "justify-start"}`}
              data-testid="thread-message"
            >
              <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${isOwn ? "bg-indigo-600 text-white" : "bg-white border border-gray-200 text-gray-800"}`}>
                {!isOwn && (
                  <p className="text-[10px] font-medium mb-1 opacity-60">
                    {ROLE_LABEL[msg.senderRole] ?? msg.senderRole}
                  </p>
                )}
                <p className="text-sm whitespace-pre-wrap break-words">{msg.body}</p>
                <p className={`text-[10px] mt-1 ${isOwn ? "text-indigo-200" : "text-gray-400"} text-right`}>
                  {new Date(msg.dateCreated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSend}
        className="border-t border-gray-200 bg-white px-4 py-3 flex items-end gap-2"
        data-testid="thread-input-form"
      >
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend(e as any);
            }
          }}
          placeholder={placeholder}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          data-testid="thread-message-input"
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending || !body.trim()}
          style={{ cursor: "pointer" }}
          className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="thread-send-button"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </form>
      {sendError && (
        <p className="px-4 pb-2 text-xs text-red-600" data-testid="thread-send-error">{sendError}</p>
      )}
    </div>
  );
}
