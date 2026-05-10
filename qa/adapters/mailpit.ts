// ─────────────────────────────────────────────────────────────────────────────
// adapters/mailpit.ts
// Client for the Mailpit email testing server.
// Supports OTP extraction with a configurable per-domain regex pattern.
// ─────────────────────────────────────────────────────────────────────────────

import type { QAConfig } from "../core/types.js";

// ─── Mailpit API types ────────────────────────────────────────────────────────

export interface MailpitMessage {
  ID: string;
  Subject: string;
  From: { Address: string; Name: string };
  To: Array<{ Address: string; Name: string }>;
  Date: string;
  Size: number;
  Snippet: string;
}

export interface MailpitMessageDetail extends MailpitMessage {
  Text: string;
  HTML: string;
  Attachments: Array<{ FileName: string; ContentType: string; Size: number }>;
}

export interface MailpitListResponse {
  messages: MailpitMessage[];
  total: number;
  count: number;
}

// ─── Default OTP pattern ──────────────────────────────────────────────────────

/**
 * Default regex to extract a 4–8 digit OTP from email body text.
 * Domain contracts can override this via contract.otpPattern.
 * Pattern is applied to both plain text and HTML bodies.
 */
const DEFAULT_OTP_PATTERN = /\b(\d{4,8})\b/;

// ─── MailpitAdapter ───────────────────────────────────────────────────────────

export class MailpitAdapter {
  private baseUrl: string;
  private timeout: number;

  constructor(config: QAConfig) {
    this.baseUrl = config.mailpitUrl.replace(/\/$/, "");
    this.timeout = config.timeout;
  }

  // ─── Message listing ──────────────────────────────────────────────────────

  async listMessages(limit = 50): Promise<MailpitMessage[]> {
    const response = await this.fetch<MailpitListResponse>(
      `/api/v1/messages?limit=${limit}`
    );
    return response.messages ?? [];
  }

  async getMessage(id: string): Promise<MailpitMessageDetail> {
    return this.fetch<MailpitMessageDetail>(`/api/v1/message/${id}`);
  }

  /**
   * Finds messages matching optional subject/recipient filters.
   */
  async findMessages(filters: {
    subjectContains?: string;
    toAddress?: string;
  }): Promise<MailpitMessage[]> {
    const messages = await this.listMessages();

    return messages.filter((msg) => {
      if (filters.subjectContains && !msg.Subject.includes(filters.subjectContains)) {
        return false;
      }
      if (
        filters.toAddress &&
        !msg.To.some((t) => t.Address === filters.toAddress)
      ) {
        return false;
      }
      return true;
    });
  }

  // ─── Wait for email ───────────────────────────────────────────────────────

  /**
   * Polls Mailpit until a matching email arrives or the timeout elapses.
   * Returns the first matching message.
   */
  async waitForEmail(
    filters: { subjectContains?: string; toAddress?: string },
    options: { pollIntervalMs?: number; timeoutMs?: number } = {}
  ): Promise<MailpitMessage> {
    const pollInterval = options.pollIntervalMs ?? 1000;
    const timeoutMs = options.timeoutMs ?? this.timeout;
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      const found = await this.findMessages(filters);
      if (found.length > 0) return found[0]!;
      await sleep(pollInterval);
    }

    throw new Error(
      `waitForEmail timed out after ${timeoutMs}ms. ` +
        `No email matching: ${JSON.stringify(filters)}`
    );
  }

  // ─── OTP extraction ───────────────────────────────────────────────────────

  /**
   * Extracts an OTP from a message's text or HTML body.
   *
   * @param messageId  - Mailpit message ID to fetch and parse
   * @param otpPattern - Optional regex pattern string from domain contract.
   *                     Falls back to DEFAULT_OTP_PATTERN (\b\d{4,8}\b).
   *                     Must contain exactly one capture group for the OTP digits.
   *
   * Example domain override:
   *   contract.otpPattern = "Your verification code is (\\d{6})"
   */
  async extractOTP(messageId: string, otpPattern?: string): Promise<string> {
    const detail = await this.getMessage(messageId);
    const body = detail.Text || detail.HTML || "";

    let pattern: RegExp;
    if (otpPattern) {
      try {
        pattern = new RegExp(otpPattern);
      } catch (err) {
        console.warn(
          `[mailpit] Invalid otpPattern "${otpPattern}": ${String(err)}. ` +
            `Falling back to default OTP pattern.`
        );
        pattern = DEFAULT_OTP_PATTERN;
      }
    } else {
      pattern = DEFAULT_OTP_PATTERN;
    }

    const match = body.match(pattern);
    const otp = match?.[1] ?? match?.[0];

    if (!otp) {
      throw new Error(
        `extractOTP: No OTP found in message ${messageId} using pattern /${pattern.source}/. ` +
          `Body preview: "${body.slice(0, 200)}"`
      );
    }

    return otp.trim();
  }

  // ─── Cleanup ──────────────────────────────────────────────────────────────

  /**
   * Deletes all messages from Mailpit.
   * Call in teardown steps to ensure a clean inbox for the next run.
   */
  async deleteAll(): Promise<void> {
    await this.fetch("/api/v1/messages", { method: "DELETE" });
  }

  // ─── Snapshot ─────────────────────────────────────────────────────────────

  /**
   * Returns a forensic snapshot of the current inbox.
   * Useful for attaching to failure reports.
   */
  async snapshot(): Promise<{ total: number; messages: MailpitMessage[] }> {
    const messages = await this.listMessages(100);
    return { total: messages.length, messages };
  }

  // ─── Internals ────────────────────────────────────────────────────────────

  private async fetch<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      ...init,
      signal: AbortSignal.timeout(this.timeout),
      headers: { Accept: "application/json", ...init?.headers },
    });

    if (!response.ok) {
      throw new Error(
        `Mailpit ${init?.method ?? "GET"} ${path} failed: ${response.status} ${response.statusText}`
      );
    }

    const text = await response.text();
    return text ? (JSON.parse(text) as T) : ({} as T);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
