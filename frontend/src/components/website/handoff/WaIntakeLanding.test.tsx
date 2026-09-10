import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

/**
 * The chat→web intake landing (§5.1, §26.5, D69).
 *
 * Server-rendered assertions only, so what is pinned is the **first paint** — which is the
 * part that matters here. The customer arrives from WhatsApp having answered four
 * questions, and §26.4.2 requires the landing to acknowledge the context it picked up:
 * dropping them into a form with no explanation is a spec violation, not a rough edge.
 *
 * The dead-link copy is the other load-bearing piece. Expired, spent and forged must read
 * identically — saying which one it was classifies the link for whoever is probing — and
 * the page must offer a way back to the chat rather than stranding the customer.
 */

const state: { failed: boolean } = { failed: false };

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    // The redemption fires in an effect, which does not run under `renderToStaticMarkup`.
    // Driving the failed/pending state directly is what lets both paints be asserted
    // without standing up a DOM or a fetch.
    useState: (initial: unknown) =>
      typeof initial === "boolean" ? [state.failed, () => {}] : actual.useState(initial),
    useEffect: () => {},
  };
});
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: { whatsappNumber: "2349167624347" } }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: () => {} }) }));
vi.mock("@/containers", () => ({ httpClient: {} }));

const { default: WaIntakeLanding } = await import("./WaIntakeLanding");

beforeEach(() => {
  state.failed = false;
});

describe("WaIntakeLanding", () => {
  it("acknowledges the context it picked up while redeeming (§26.4.2)", () => {
    const html = renderToStaticMarkup(<WaIntakeLanding token="tok-123" />);

    expect(html).toContain("Bringing over what you told us on WhatsApp");
    expect(html).toContain("wa-intake-landing-loading");
  });

  it("gives a dead link one state, with no reason", () => {
    state.failed = true;

    const html = renderToStaticMarkup(<WaIntakeLanding token="tok-123" />);
    // The prose only — the `wa.me` prefill carries a fixed `…-expired` page code for §26.10
    // attribution, which is the same for every failure and so classifies nothing.
    const copy = html.split('data-testid="wa-intake-landing-dead">')[1].split("</p>")[0];

    expect(copy).toContain("no longer valid");
    // Never "expired", "already used", or "invalid signature" — one indistinguishable state.
    expect(copy).not.toContain("expired");
    expect(copy).not.toContain("already used");
    expect(copy).not.toContain("invalid");
  });

  it("offers a way back to the chat rather than stranding the customer", () => {
    state.failed = true;

    const html = renderToStaticMarkup(<WaIntakeLanding token="tok-123" />);

    expect(html).toContain("wa.me/2349167624347");
    expect(html).toContain("wa-intake-landing-new");
  });

  it("reassures the customer their answers survive a dead link", () => {
    // They do: the answers live on the bot session until a redemption consumes them, so a
    // fresh link picks up exactly where the old one would have.
    state.failed = true;

    const html = renderToStaticMarkup(<WaIntakeLanding token="tok-123" />);

    expect(html).toContain("your answers are");
  });
});
