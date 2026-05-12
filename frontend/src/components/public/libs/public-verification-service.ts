import { PublicVerificationSummary } from "../models";

export async function getPublicSummary(vid: string): Promise<PublicVerificationSummary | null> {
  const res = await fetch(`/api/public/verifications/${vid}`, { cache: "no-store" });
  if (!res.ok) return null;
  const json = await res.json();
  return json.data ?? null;
}
