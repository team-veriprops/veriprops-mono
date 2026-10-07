import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Broadcast, BroadcastAction, BroadcastAudience, BroadcastStatus } from "@/types/broadcast";
import BroadcastRow from "./BroadcastRow";

function broadcast(over: Partial<Broadcast> = {}): Broadcast {
  return {
    id: "b-1", audience: BroadcastAudience.ALL, subject: "Maintenance window", body: "Body",
    status: BroadcastStatus.DRAFT, recipientCount: 0, recipientsEnqueued: 0,
    allowedActions: [BroadcastAction.SEND, BroadcastAction.CANCEL], dateCreated: "2026-10-06T09:00:00Z",
    ...over,
  };
}

const render = (b: Broadcast) =>
  renderToStaticMarkup(<BroadcastRow broadcast={b} onSend={() => {}} onCancel={() => {}} busy={false} />);

describe("BroadcastRow", () => {
  it("offers exactly the actions the backend allows", () => {
    const html = render(broadcast());
    expect(html).toContain('data-testid="broadcast-send-b-1"');
    expect(html).toContain('data-testid="broadcast-cancel-b-1"');
  });

  it("offers only Cancel while sending, and nothing once sent", () => {
    const sending = render(broadcast({ status: BroadcastStatus.SENDING, allowedActions: [BroadcastAction.CANCEL] }));
    expect(sending).not.toContain("broadcast-send-b-1");
    expect(sending).toContain("broadcast-cancel-b-1");

    const sent = render(broadcast({ status: BroadcastStatus.SENT, allowedActions: [] }));
    expect(sent).not.toContain("broadcast-send-b-1");
    expect(sent).not.toContain("broadcast-cancel-b-1");
  });

  it("shows how far a sending broadcast has reached its audience", () => {
    const html = render(broadcast({
      status: BroadcastStatus.SENDING, recipientCount: 4200, recipientsEnqueued: 1500,
      allowedActions: [BroadcastAction.CANCEL],
    }));
    expect(html).toContain("1,500 of 4,200 recipients reached");
  });

  it("shows the audience a sent broadcast reached", () => {
    const html = render(broadcast({
      status: BroadcastStatus.SENT, recipientCount: 12, recipientsEnqueued: 12, allowedActions: [],
    }));
    expect(html).toContain("12 recipients");
  });

  it("says where a cancelled send stopped", () => {
    const html = render(broadcast({
      status: BroadcastStatus.CANCELLED, recipientCount: 4200, recipientsEnqueued: 500, allowedActions: [],
    }));
    expect(html).toContain("stopped after 500 of 4,200 recipients");
  });
});
