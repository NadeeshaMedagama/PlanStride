import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Clock,
  Megaphone,
  Repeat,
  Scale,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import type {
  PlanReviewResponse,
  ReviewFindingResponse,
  ReviewFindingResponseCategory,
} from "@/api/model";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getApiErrorCode, getApiErrorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";

export type Finding = ReviewFindingResponse & { id: string };

export function withIds(review: PlanReviewResponse): Finding[] {
  return review.findings.map((finding, index) => ({
    ...finding,
    id: `f${index}`,
  }));
}

const CATEGORY: Record<
  ReviewFindingResponseCategory,
  { label: string; icon: LucideIcon }
> = {
  not_verifiable: { label: "Work, not a result", icon: Target },
  missing_why: { label: "Doesn't say why it matters", icon: CircleHelp },
  missing_go_to_market: { label: "Nobody will hear about it", icon: Megaphone },
  scope_too_big: { label: "Too big for one week", icon: Scale },
  carry_over: { label: "Carried over", icon: Repeat },
};

const APPLY_LABEL: Record<Finding["action"], string> = {
  replace_title: "Use this wording",
  set_why: "Use this reason",
  add_go_to_market: "Add this goal",
};

// One finding, shown right under the task (or field) it's about.
export function FindingCard({
  finding,
  onApply,
  onDismiss,
}: {
  finding: Finding;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const { label, icon: Icon } = CATEGORY[finding.category];
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/40">
      <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-amber-800 uppercase dark:text-amber-300">
        <Icon className="size-3.5" /> {label}
      </p>
      <p className="mt-1.5 text-amber-950 dark:text-amber-100">
        {finding.problem}
      </p>
      <div className="mt-2.5 rounded-md border border-amber-200/80 bg-background px-3 py-2 dark:border-amber-900/60">
        <p className="text-xs text-muted-foreground">Suggested</p>
        <p className="font-medium">{finding.suggested_rewrite}</p>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-2">
        <Button size="sm" onClick={onApply}>
          <Sparkles className="size-3.5" /> {APPLY_LABEL[finding.action]}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}

export function ReviewSummary({
  review,
  open,
  stale,
  onReviewAgain,
  reviewing,
}: {
  review: PlanReviewResponse;
  open: number;
  stale: boolean;
  onReviewAgain: () => void;
  reviewing: boolean;
}) {
  const ready = review.verdict === "ready";
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        ready
          ? "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/30"
          : "border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/30"
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex gap-3">
          {ready ? (
            <CircleCheck className="mt-0.5 size-5 shrink-0 text-emerald-600" />
          ) : (
            <Sparkles className="mt-0.5 size-5 shrink-0 text-amber-600" />
          )}
          <div>
            <p className="font-medium">
              {ready ? "Ready to submit" : "A lead would push back on this"}
              {open > 0 && (
                <span className="font-normal text-muted-foreground">
                  {" "}
                  · {open} suggestion{open === 1 ? "" : "s"} below
                </span>
              )}
            </p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {review.summary}
            </p>
            {stale && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                You&apos;ve changed the plan since this review.
              </p>
            )}
          </div>
        </div>
        {stale && (
          <Button
            size="sm"
            variant="outline"
            onClick={onReviewAgain}
            disabled={reviewing}
          >
            {reviewing ? <Spinner /> : <Sparkles className="size-3.5" />}
            Review again
          </Button>
        )}
      </div>
    </div>
  );
}

export function ReviewingNotice() {
  return (
    <div
      className="flex items-center gap-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground"
      role="status"
    >
      <Spinner className="text-primary" />
      Reading your plan the way a demanding lead would…
    </div>
  );
}

const AI_ERROR_TITLES: Record<string, { title: string; icon: LucideIcon }> = {
  ai_rate_limited: { title: "The AI is busy right now", icon: Clock },
  ai_throttled: { title: "Give the AI a moment", icon: Clock },
  ai_timeout: { title: "The AI took too long", icon: Clock },
  ai_not_configured: { title: "AI isn't available here", icon: CircleAlert },
  ai_unavailable: { title: "The AI is unavailable", icon: CircleAlert },
  ai_invalid_output: {
    title: "The AI's answer didn't make sense",
    icon: CircleAlert,
  },
};

// Failures read as plain words, and always say the plan is safe: planning
// works the same without the AI.
export function AiErrorAlert({
  error,
  onDismiss,
}: {
  error: unknown;
  onDismiss?: () => void;
}) {
  const code = getApiErrorCode(error) ?? "";
  const { title, icon: Icon } = AI_ERROR_TITLES[code] ?? {
    title: "The AI couldn't help this time",
    icon: CircleAlert,
  };
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-xl border border-border bg-muted/50 p-4 text-sm"
    >
      <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-muted-foreground">
          {getApiErrorMessage(
            error,
            "Nothing in your plan changed. You can keep planning without it."
          )}
        </p>
      </div>
      {onDismiss && (
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          OK
        </Button>
      )}
    </div>
  );
}
