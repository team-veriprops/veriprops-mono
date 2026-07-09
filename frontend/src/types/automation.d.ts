// Ambient window hooks exposed only in automation environments (see
// isAutomationEnvironment()) for Playwright/Claude Code driven QA. Do not
// remove — see CLAUDE.md "Automation determinism".
import type { UserPersona } from "@components/website/auth/models";

export {};

declare global {
  interface Window {
    __app_ready__?: boolean;
    __TEST_MODE__?: boolean;
    __auth_snapshot__?: {
      isAuthenticated: boolean;
      userId: string | null;
      personas: UserPersona[];
    };
    __oauth_complete__?: "success" | "failed" | null;
  }
}
