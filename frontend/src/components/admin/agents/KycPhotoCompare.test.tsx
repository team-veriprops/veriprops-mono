import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { GovIdType, KycMethod, KycProvider, KycRecordView, KycResultStatus } from "@/types/agent";
import { KycPhotoCompare } from "./KycPhotoCompare";

const record = (over: Partial<KycRecordView> = {}): KycRecordView => ({
  provider: KycProvider.DOJAH, method: KycMethod.GOV_ID, status: KycResultStatus.NEEDS_REVIEW, ...over,
});

describe("KycPhotoCompare", () => {
  it("puts the selfie and the document side by side with a draggable divider", () => {
    const html = renderToStaticMarkup(<KycPhotoCompare kyc={record({
      idType: GovIdType.DRIVERS_LICENCE, selfieUrl: "https://signed/selfie", documentUrl: "https://signed/document",
    })} />);
    expect(html).toContain('data-testid="admin-kyc-compare"');
    expect(html).toContain('src="https://signed/selfie"');
    expect(html).toContain('src="https://signed/document"');
    expect(html).toContain('role="separator"');
    // The selfie on the left, the named document on the right.
    expect(html.indexOf("admin-kyc-selfie")).toBeLessThan(html.indexOf("admin-kyc-document"));
    expect(html).toContain("Drivers Licence");
  });

  it("shows the selfie alone when no document photo was needed", () => {
    const html = renderToStaticMarkup(<KycPhotoCompare kyc={record({ method: KycMethod.BVN, selfieUrl: "https://signed/selfie" })} />);
    expect(html).toContain('data-testid="admin-kyc-selfie"');
    expect(html).not.toContain('role="separator"');
  });

  it("says so when no photos were kept", () => {
    expect(renderToStaticMarkup(<KycPhotoCompare kyc={record()} />)).toContain('data-testid="admin-kyc-no-photos"');
  });
});
