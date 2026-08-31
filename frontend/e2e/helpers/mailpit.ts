/**
 * Mailpit inbox reader (docs/uat-strategy.md §2, §6b).
 *
 * Used for the flows whose only delivery channel is email — invites, password reset,
 * share links, and "was this notification actually dispatched" assertions. It is NEVER
 * used for OTPs: those are deterministic (`TEST_OTP`) by contract.
 */
import { expect, request } from "@playwright/test";

import { MAILPIT_URL } from "./env";

export interface MailpitMessage {
  ID: string;
  Subject: string;
  To: { Address: string }[];
  Created: string;
}

/** A fetched message with its rendered bodies. */
export interface MailpitMessageBody extends MailpitMessage {
  HTML: string;
  Text: string;
}

async function mailpitFetch<T>(path: string): Promise<T> {
  const context = await request.newContext({ baseURL: MAILPIT_URL });
  try {
    const response = await context.get(path);
    if (!response.ok()) {
      throw new Error(`Mailpit ${path} → ${response.status()} ${response.statusText()}`);
    }
    return (await response.json()) as T;
  } finally {
    await context.dispose();
  }
}

/** Delete every captured message — call before an action whose email you will assert. */
export async function clearMailbox(): Promise<void> {
  const context = await request.newContext({ baseURL: MAILPIT_URL });
  try {
    await context.delete("/api/v1/messages");
  } finally {
    await context.dispose();
  }
}

/**
 * The newest message addressed to *recipient*, polled until it arrives.
 * Email dispatch is asynchronous, so this waits rather than asserting a single snapshot.
 */
export async function waitForEmail(
  recipient: string,
  options: { subjectContains?: string; timeoutMs?: number } = {},
): Promise<MailpitMessageBody> {
  const deadline = Date.now() + (options.timeoutMs ?? 20_000);
  let lastSeen: MailpitMessage | undefined;

  while (Date.now() < deadline) {
    const { messages } = await mailpitFetch<{ messages: MailpitMessage[] }>(
      `/api/v1/search?query=${encodeURIComponent(`to:${recipient}`)}&limit=20`,
    );
    lastSeen = messages.find(
      (message) =>
        !options.subjectContains ||
        message.Subject.toLowerCase().includes(options.subjectContains.toLowerCase()),
    );
    if (lastSeen) return mailpitFetch<MailpitMessageBody>(`/api/v1/message/${lastSeen.ID}`);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(
    `No email for ${recipient}` +
      (options.subjectContains ? ` with subject containing "${options.subjectContains}"` : "") +
      ` within ${options.timeoutMs ?? 20_000}ms`,
  );
}

/**
 * The first app link in the newest matching email — the reset/invite/share URL a token
 * flow needs.
 *
 * Templates render both ways: some carry anchor tags, others are plain text with the URL
 * inline (`Reset your password ( https://… )`), so both forms are scanned.
 */
export async function extractLinkFromEmail(
  recipient: string,
  options: { subjectContains?: string; pathContains?: string; timeoutMs?: number } = {},
): Promise<string> {
  const message = await waitForEmail(recipient, options);
  const links = [
    ...[...(message.HTML ?? "").matchAll(/href="([^"]+)"/g)].map(([, href]) => href),
    // Trailing `)`/`>` and punctuation are stripped so a bracketed plain-text URL is usable.
    ...[...`${message.Text ?? ""}\n${message.HTML ?? ""}`.matchAll(/https?:\/\/[^\s<>"')]+/g)].map(
      ([url]) => url,
    ),
  ];
  const match = options.pathContains
    ? links.find((link) => link.includes(options.pathContains!))
    : links[0];

  expect(
    match,
    `No link${options.pathContains ? ` containing "${options.pathContains}"` : ""} in email "${
      message.Subject
    }"`,
  ).toBeTruthy();
  return match!;
}
