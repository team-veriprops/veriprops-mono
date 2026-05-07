// ─────────────────────────────────────────────────────────────────────────────
// domains/[DOMAIN_NAME]/fixtures.ts
// [CLAUDE: Declares the sessions this domain needs and their bootstrap/teardown steps.]
// [CLAUDE: Each session maps to a real user role (admin, customer, guest, etc).]
// [CLAUDE: Bootstrap steps run before journeys. Teardown steps run after all journeys.]
// [CLAUDE: The runner executes steps in array order — sequence matters.]
// [CLAUDE: idempotent: true means the step is cached by action+payload hash.]
//          Only set this on steps that are safe to skip (reference data seeding).
//          Never set it on steps that modify user-specific state.
// ─────────────────────────────────────────────────────────────────────────────

import type { DomainFixtures } from "../../core/types.js";

// [CLAUDE: Define one SessionFixture per user role this domain exercises.]
// [CLAUDE: If the domain only has API journeys with no auth, use an empty sessions array.]
// [CLAUDE: session.key must match the sessionKey declared in each journey in journeys.ts.]

export const fixtures: DomainFixtures = {
  sessions: [
    {
      key: "[SESSION_KEY]", // [CLAUDE: e.g. "adminUser", "customerUser", "guestUser"]
      bootstrap: [
        // [CLAUDE: List every backend step needed before journeys run.]
        // [CLAUDE: Common pattern: reset → seed → domain-specific bootstrap.]
        {
          label: "Reset database",
          action: "reset",
          // [CLAUDE: Set idempotent: true only for reference data that does not change between runs.]
          // idempotent: true,
        },
        {
          label: "Seed [DOMAIN_NAME] fixtures",
          action: "seed",
          payload: {
            // [CLAUDE: Pass any fixture data the backend seeder needs.]
            // [CLAUDE: Keys here depend on your backend's /qa/seed endpoint contract.]
            domain: "[DOMAIN_NAME]",
          },
          // idempotent: true,
        },
        // [CLAUDE: Add domain-specific bootstrap steps here if needed.]
        // {
        //   label: "Bootstrap [specific state]",
        //   action: "[custom-action-name]",
        //   payload: { /* ... */ },
        // },
      ],
      teardown: [
        // [CLAUDE: Teardown steps are optional. Add them only when cleanup is required.]
        // [CLAUDE: Teardown steps are never cached — always execute.]
        // {
        //   label: "Clean up [DOMAIN_NAME] test data",
        //   action: "reset",
        // },
      ],
    },
    // [CLAUDE: Add more sessions here if the domain tests multiple user roles.]
  ],
};
