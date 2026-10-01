import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const session: { isLoading: boolean; data: unknown } = { isLoading: false, data: null };
vi.mock("../libs/useAuthQueries", () => ({
  useCurrentSession: () => session,
  useSetPasswordMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import SetPasswordForm from "./SetPasswordForm";

const testIds = { form: "f", current: "cur", input: "new", confirm: "conf", submit: "go" };
const render = () => renderToStaticMarkup(<SetPasswordForm testIds={testIds} onSaved={() => {}} />);
const withPassword = (hasPassword: boolean) => {
  session.data = { user: { hasPassword } };
};

describe("SetPasswordForm", () => {
  it("asks for the current password when the account already has one", () => {
    withPassword(true);
    const html = render();
    expect(html).toContain('data-testid="cur"');
    expect(html).toMatch(/signs you out on every other device/);
  });

  it("sets a first password without one", () => {
    withPassword(false);
    const html = render();
    expect(html).not.toContain('data-testid="cur"');
    expect(html).toContain('data-testid="new"');
  });

  it("waits for the session before choosing which form to show", () => {
    session.data = null;
    session.isLoading = true;
    expect(render()).not.toContain('data-testid="f"');
    session.isLoading = false;
  });
});
