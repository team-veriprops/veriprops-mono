"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@3rdparty/ui/button";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatusPill } from "@components/ui/StatusPill";
import { formatRelativeTime } from "@lib/time";
import { getErrorMessage } from "@lib/utils";
import { WhatsAppTemplate, WhatsAppTemplateStatus } from "@/types/whatsappTemplate";
import {
  useSyncWhatsAppTemplatesMutation,
  useWhatsAppTemplatesQuery,
} from "./libs/useWhatsAppTemplateQueries";

/**
 * Admin → WhatsApp templates (PRD §26.7, WA-15/WA-41).
 *
 * The §26.11 launch gate turns on "all §26.7 templates approved", and approval is Meta's to
 * give — asynchronously, sometimes as a rejection with a reason. This page is where that
 * answer becomes visible instead of living in somebody's inbox.
 *
 * Read-only by design: the definitions are code-owned (the code is what fills the
 * parameters) and the status is Meta's, so an editable field here would let the page
 * describe something the app does not do. The only action is to go and ask again.
 */
export default function WhatsAppTemplates() {
  const { data, isLoading, isError } = useWhatsAppTemplatesQuery();
  const sync = useSyncWhatsAppTemplatesMutation();

  const onSync = async () => {
    try {
      const result = await sync.mutateAsync();
      toast.success(
        result
          ? `Synced ${result.synced} templates — ${result.approved} approved, ${result.missing} not yet submitted.`
          : "Synced.",
      );
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not reach the template directory."));
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6" data-testid="wa-templates">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">WhatsApp templates</h1>
          <p className="text-sm text-muted-foreground">
            Meta must approve each template before it can be sent. Approval is a launch
            gate, and it is Meta&rsquo;s answer &mdash; this page reads it, it does not set it.
          </p>
        </div>
        <Button variant="outline" onClick={onSync} disabled={sync.isPending} data-testid="wa-templates-sync">
          {sync.isPending
            ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            : <RefreshCw className="mr-2 h-4 w-4" />}
          Sync from Meta
        </Button>
      </div>

      <AsyncStateComponent<WhatsAppTemplate[]>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading templates…"
        emptyText="No templates declared."
      >
        {(templates) => (
          <div className="space-y-3">
            {templates.map((template) => (
              <TemplateRow key={template.name} template={template} />
            ))}
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function TemplateRow({ template }: { template: WhatsAppTemplate }) {
  return (
    <div className="rounded-lg border p-3" data-testid={`wa-template-${template.name}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-sm font-medium">{template.name}</p>
          <p className="text-xs text-muted-foreground">
            {template.category} · {template.language}
            {template.parameters.length > 0 && ` · ${template.parameters.join(" → ")}`}
          </p>
        </div>
        <StatusPill status={template.status} />
      </div>

      {template.status === WhatsAppTemplateStatus.NOT_FOUND && (
        <p className="mt-2 text-xs text-muted-foreground">
          Declared here but not on the business account yet &mdash; submit it to Meta.
        </p>
      )}
      {template.rejectionReason && (
        <p className="mt-2 text-xs text-destructive" data-testid="wa-template-rejection">
          Rejected: {template.rejectionReason}
        </p>
      )}
      {template.lastSyncedAt && (
        <p className="mt-2 text-xs text-muted-foreground">
          Last checked {formatRelativeTime(template.lastSyncedAt)}
        </p>
      )}
    </div>
  );
}
