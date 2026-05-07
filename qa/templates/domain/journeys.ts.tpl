// ─────────────────────────────────────────────────────────────────────────────
// domains/[DOMAIN_NAME]/journeys.ts
// [CLAUDE: Each journey is a named sequence of steps that tests one user flow.]
// [CLAUDE: mode: "browser" — uses Playwright. mode: "api" — uses APIRunner.]
// [CLAUDE: sessionKey must match a key declared in fixtures.ts sessions.]
// [CLAUDE: selector values must be keys from selectors.ts — never raw strings.]
// [CLAUDE: value and url fields support {{state.key}} and {{config.baseUrl}} interpolation.]
// [CLAUDE: Store values for later steps using type: "custom" and ctx.state["key"] = value.]
// [CLAUDE: optional: true means a step failure does not cascade to subsequent steps.]
// [CLAUDE: skip: true on a journey skips it and marks it in the report — use for WIP.]
// ─────────────────────────────────────────────────────────────────────────────

import type { Journey } from "../../core/types.js";

// [CLAUDE: Define one Journey per distinct user flow this domain covers.]
// [CLAUDE: Name journeys as verb phrases: "user logs in", "admin creates report", etc.]
// [CLAUDE: Keep journeys focused — one happy path or one edge case per journey.]

export const journeys: Journey[] = [
  // ── Browser journey example ────────────────────────────────────────────────
  // [CLAUDE: Replace this example with real steps for [DOMAIN_NAME].]
  {
    name: "[describe the user flow in plain English]",
    mode: "browser", // [CLAUDE: Use "api" if no UI interaction is needed.]
    sessionKey: "[SESSION_KEY]", // [CLAUDE: Must match fixtures.ts session key.]
    // skip: true, // [CLAUDE: Uncomment to skip this journey during development.]
    steps: [
      {
        type: "navigate",
        label: "Open [page name]",
        url: "{{config.baseUrl}}/[route]",
        // [CLAUDE: Use {{config.baseUrl}} for the frontend base URL.]
        // [CLAUDE: Use {{config.apiBaseUrl}} for direct API calls in custom steps.]
      },
      {
        type: "fill",
        label: "Enter [field name]",
        selector: "[selectorKey]", // [CLAUDE: Must be a key from selectors.ts.]
        value: "[value or {{state.someKey}}]",
      },
      {
        type: "click",
        label: "Submit [form or button name]",
        selector: "[selectorKey]",
      },
      {
        type: "assert",
        label: "Verify [expected outcome]",
        assertion: async () => {
          // [CLAUDE: Import assertion helpers from core/assertions.ts.]
          // [CLAUDE: Return an AssertionResult — never throw inside assertion.]
          // Example:
          // return assertUrlContains(page, "/expected-route");
          return { status: "skip", message: "Replace with real assertion" };
        },
      },
    ],
  },

  // ── API journey example ────────────────────────────────────────────────────
  // [CLAUDE: Use API journeys for backend flows that do not require a browser.]
  // {
  //   name: "[API flow description]",
  //   mode: "api",
  //   sessionKey: "[SESSION_KEY]",
  //   steps: [
  //     {
  //       type: "api-call",
  //       label: "POST [resource]",
  //       apiOptions: {
  //         method: "POST",
  //         path: "/api/[endpoint]",
  //         body: { key: "value" },
  //       },
  //     },
  //     {
  //       type: "assert",
  //       label: "Response is 201",
  //       assertion: async () => {
  //         const response = ctx.state["__apiResponse_POST [resource]"];
  //         return assertStatus(response, 201);
  //       },
  //     },
  //   ],
  // },
];
