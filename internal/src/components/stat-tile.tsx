import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// A headline number: label, value, and an optional line of context. Values
// use proportional figures (tabular digits look loose at this size).
export function StatTile({
  label,
  value,
  note,
  tone = "default",
  className,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "default" | "warning" | "critical";
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border bg-background p-4", className)}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {note && (
        <p
          className={cn(
            "mt-1 text-xs",
            tone === "critical"
              ? "text-red-700 dark:text-red-400"
              : tone === "warning"
                ? "text-amber-700 dark:text-amber-400"
                : "text-muted-foreground"
          )}
        >
          {note}
        </p>
      )}
    </div>
  );
}

export function SectionHeading({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="font-medium">{title}</h2>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}

export function PageTitle({
  title,
  description,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children && (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      )}
    </div>
  );
}
