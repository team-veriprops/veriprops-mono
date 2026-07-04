"use client";

import { useState } from "react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { Loader2 } from "lucide-react";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { TierWeights } from "@/types/adminReview";
import {
  useSetTierWeightsMutation,
  useTrustWeightsQuery,
} from "@components/admin/verifications/libs/useReviewQueries";

function TierCard({ tier }: { tier: TierWeights }) {
  const setWeights = useSetTierWeightsMutation();
  // Seed editable local state from the tier once; the card stays mounted across
  // refetches (values already equal what was saved), so no resync effect is needed.
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(tier.weights.map((w) => [w.role, w.weightPercent])),
  );

  const total = Object.values(values).reduce((a, b) => a + (b || 0), 0);
  const valid = total === 100;

  const onSave = async () => {
    await setWeights.mutateAsync({
      tier: tier.tier as VerificationTier,
      weights: values as Record<AgentRole, number>,
    });
    toast({ title: `${tier.tier} weights saved` });
  };

  return (
    <Card data-testid={`weights-${tier.tier}`}>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{tier.tier}</CardTitle>
        <Badge variant={valid ? "secondary" : "destructive"}>Total: {total}%</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {tier.weights.map((w) => (
          <div key={w.role} className="flex items-center justify-between gap-3">
            <Label className="w-28">{w.role}</Label>
            <Input
              type="number"
              min={0}
              max={100}
              value={values[w.role] ?? 0}
              onChange={(e) => setValues((s) => ({ ...s, [w.role]: Number(e.target.value) }))}
              className="w-24"
              data-testid={`weight-${tier.tier}-${w.role}`}
            />
          </div>
        ))}
        <Button
          onClick={onSave}
          disabled={setWeights.isPending || !valid}
          data-testid={`save-${tier.tier}`}
        >
          Save {tier.tier} weights
        </Button>
        {!valid && <p className="text-xs text-destructive">Weights must sum to 100%.</p>}
      </CardContent>
    </Card>
  );
}

export default function TrustScoreWeights() {
  const { data, isLoading } = useTrustWeightsQuery();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading weights…
      </div>
    );
  }

  const tiers = (data as TierWeights[]) ?? [];

  return (
    <div className="space-y-6" data-testid="trust-score-weights">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Trust Score Weights</h1>
        <p className="text-sm text-muted-foreground">
          Per-role contribution to a tier&apos;s composite trust score. Each tier must sum to 100%.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {tiers.map((t) => (
          <TierCard key={t.tier} tier={t} />
        ))}
      </div>
    </div>
  );
}
