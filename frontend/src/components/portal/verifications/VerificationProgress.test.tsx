import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole } from "@/types/agent";
import { TrackingTask } from "@/types/tracking";
import { VerificationProgress } from "./VerificationProgress";

const tasks: TrackingTask[] = [
  { role: AgentRole.REGISTRY, stateLabel: "Completed", completed: true, locked: false },
  { role: AgentRole.FIELD, stateLabel: "In Progress", completed: false, locked: false },
  { role: AgentRole.LAWYER, stateLabel: "Awaiting other stages", completed: false, locked: true },
];

describe("VerificationProgress", () => {
  it("renders humanized step labels and their state labels", () => {
    const html = renderToStaticMarkup(<VerificationProgress tasks={tasks} progressPercent={40} />);
    expect(html).toContain("Registry &amp; Title"); // "&" is HTML-escaped in static markup
    expect(html).toContain("Physical Inspection");
    expect(html).toContain("Legal Opinion");
    expect(html).toContain("Awaiting other stages");
  });

  it("gives the active (in-progress) step its attention pulse", () => {
    const html = renderToStaticMarkup(<VerificationProgress tasks={tasks} progressPercent={40} />);
    // Only the non-completed, non-locked step carries the ping ring.
    expect(html).toContain("animate-ping");
  });
});
