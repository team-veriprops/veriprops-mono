import { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Right-aligned actions (buttons, links) beside the title. */
  actions?: ReactNode;
  /** A row under the description for attention chips or supporting meta. */
  meta?: ReactNode;
}

export default function PageHeader({ title, description, actions, meta }: PageHeaderProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl lg:text-3xl font-display font-bold text-foreground">{title}</h1>
          {description ? <p className="text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="flex flex-wrap items-center gap-2">{meta}</div> : null}
    </div>
  );
}
