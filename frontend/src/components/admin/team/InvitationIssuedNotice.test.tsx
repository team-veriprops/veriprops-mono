import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import InvitationIssuedNotice from "./InvitationIssuedNotice";

const URL = "https://app.example.com/auth/admin-invite/tok123";

describe("InvitationIssuedNotice", () => {
  it("says the invitee was emailed and still offers the link", () => {
    const html = renderToStaticMarkup(
      <InvitationIssuedNotice issued={{ inviteUrl: URL, emailSent: true }} email="ada@example.com" />,
    );
    expect(html).toContain('data-testid="admin-invite-emailed"');
    expect(html).toContain("ada@example.com");
    expect(html).toContain(URL);
    expect(html).not.toContain('data-testid="admin-invite-email-failed"');
  });

  it("asks the Super Admin to pass the link on when the email did not go out", () => {
    const html = renderToStaticMarkup(
      <InvitationIssuedNotice issued={{ inviteUrl: URL, emailSent: false }} email="ada@example.com" />,
    );
    expect(html).toContain('data-testid="admin-invite-email-failed"');
    expect(html).toContain("send it to them yourself");
    expect(html).toContain(URL);
    expect(html).not.toContain('data-testid="admin-invite-emailed"');
  });

  it("keeps the link under its stable test id in both states", () => {
    for (const emailSent of [true, false]) {
      const html = renderToStaticMarkup(
        <InvitationIssuedNotice issued={{ inviteUrl: URL, emailSent }} email="ada@example.com" />,
      );
      expect(html).toContain('data-testid="admin-invite-link"');
    }
  });
});
