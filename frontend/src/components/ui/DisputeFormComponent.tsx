import { Button } from "@components/3rdparty/ui/button";
import { Card } from "@components/3rdparty/ui/card";
import { Textarea } from "@components/3rdparty/ui/textarea";
import { AlertCircle, Upload } from "lucide-react";
import { useState } from "react";

export default function DisputeFormComponent() {
  const [disputeReason, setDisputeReason] = useState<string>();
  const handleRaiseDispute = () => "";
  
  return (
    <Card className="p-6 border-destructive/20">
      <h3 className="font-semibold mb-2 flex items-center gap-2 text-destructive">
        <AlertCircle className="h-5 w-5" />
        Raise a Dispute
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        We respond within 48 hours. Please provide detailed information about
        your concern.
      </p>
      <Textarea
        placeholder="Describe the issue with this transaction..."
        value={disputeReason}
        onChange={(e) => setDisputeReason(e.target.value)}
        className="mb-3"
        rows={4}
      />
      <div className="flex gap-2">
        <Button variant="outline" size="sm" className="flex-1">
          <Upload className="h-4 w-4 mr-2" />
          Upload Evidence
        </Button>
        <Button
          variant="destructive"
          size="sm"
          className="flex-1"
          onClick={handleRaiseDispute}
        >
          Submit Dispute
        </Button>
      </div>
    </Card>
  );
}
