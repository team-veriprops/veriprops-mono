// ─────────────────────────────────────────────────────────────────────────────
// domains/[DOMAIN_NAME]/contract.ts
// [CLAUDE: Replace [DOMAIN_NAME] with the kebab-case domain name throughout.]
// [CLAUDE: This file defines the domain's identity and runtime behaviour flags.]
// [CLAUDE: Do not add logic here. Keep this declarative.]
// ─────────────────────────────────────────────────────────────────────────────

import { CURRENT_SCHEMA_VERSION } from "../../core/types.js";
import type { DomainContract } from "../../core/types.js";

// [CLAUDE: contract.name must exactly match the directory name and manifest key.]
// [CLAUDE: contract.description is shown in reports and CLI output. Be concise.]
// [CLAUDE: dependsOn lists domain names that must complete before this one runs.]
//          Leave as [] if this domain has no dependencies.
// [CLAUDE: otpPattern overrides the default OTP regex for this domain's email flows.]
//          Format: a regex string with one capture group, e.g. "Code: (\\d{6})"
//          Omit the field entirely to use the platform default (\b\d{4,8}\b).
// [CLAUDE: appReadySelector overrides the global APP_READY_SELECTOR for this domain.]
//          Omit to use the platform default (window.__app_ready → env selector → networkidle).
// [CLAUDE: tags are used for filtering and reporting. Use lowercase kebab-case.]
// [CLAUDE: owner is a team name or email shown in drift reports.]

export const contract: DomainContract = {
  schemaVersion: CURRENT_SCHEMA_VERSION,
  name: "[DOMAIN_NAME]",
  description: "[Brief human-readable description of what this domain tests]",
  dependsOn: [],
  // otpPattern: "Your code is (\\d{6})",
  // appReadySelector: "[data-testid='app-ready']",
  tags: ["[TAG_1]", "[TAG_2]"],
  owner: "[TEAM_OR_EMAIL]",
};
