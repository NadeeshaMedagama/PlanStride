import { CircleCheck, CircleX } from "lucide-react";
import type { PlanResponseStatus } from "@/api/model";
import { cn } from "@/lib/utils";

const STATUS: Record<PlanResponseStatus, { label: string; className: string }> =
  {
    draft: {
      label: "Draft",
      className: "border-border bg-muted text-muted-foreground",
    },
    submitted: {
      label: "Awaiting approval",
      className:
        "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200",
    },
    approved: {
      label: "Approved",
      className:
        "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
    },
    done: {
      label: "Week closed",
      className:
        "border-zinc-300 bg-zinc-900 text-white dark:border-zinc-700 dark:bg-zinc-100 dark:text-zinc-900",
    },
  };

export function StatusBadge({
  status,
  returned = false,
  className,
}: {
  status: PlanResponseStatus;
  returned?: boolean;
  className?: string;
}) {
  const { label, className: tone } =
    returned && status === "draft"
      ? {
          label: "Returned",
          className:
            "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
        }
      : STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-medium whitespace-nowrap",
        tone,
        className
      )}
    >
      {label}
    </span>
  );
}

export function ShippedBadge({ shipped }: { shipped: boolean | null }) {
  if (shipped === null) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }
  return shipped ? (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700 dark:text-emerald-400">
      <CircleCheck className="size-4" /> Shipped
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-rose-700 dark:text-rose-400">
      <CircleX className="size-4" /> Didn&apos;t ship
    </span>
  );
}

export function TaskProgress({
  done,
  total,
  className,
}: {
  done: number;
  total: number;
  className?: string;
}) {
  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className="h-1.5 w-20 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-label={`${done} of ${total} tasks done`}
      >
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums">
        {done}/{total}
      </span>
    </div>
  );
}

export const KIND_LABELS = {
  main: "Main task",
  sub_goal: "Sub-goals",
  go_to_market: "Go-to-market",
} as const;
