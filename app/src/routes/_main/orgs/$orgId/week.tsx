import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarX, Check, PenLine, Wand2, X } from "lucide-react";
import { useMyWeekGet } from "@/api/endpoints/plans/plans";
import type { MyWeekResponse } from "@/api/model";
import { PlanEditor } from "@/components/plans/plan-editor";
import { PlanView } from "@/components/plans/plan-view";
import { WeekSwitcher } from "@/components/plans/week-switcher";
import {
  ErrorState,
  PageHeader,
  PageSkeleton,
  StateMessage,
} from "@/components/states";
import { Button } from "@/components/ui/button";
import { useOrg } from "@/contexts/org-context";
import { canStartPlan, currentWeekStart, isMonday } from "@/lib/week";
import { fullName } from "@/lib/utils";

export const Route = createFileRoute("/_main/orgs/$orgId/week")({
  validateSearch: (search: Record<string, unknown>): { week?: string } => {
    const week = search["week"];
    return {
      week: typeof week === "string" && isMonday(week) ? week : undefined,
    };
  },
  head: () => ({ meta: [{ title: "My week · PlanStride" }] }),
  component: WeekPage,
});

function WeekPage() {
  const { orgId } = useOrg();
  const navigate = Route.useNavigate();
  const week = Route.useSearch().week ?? currentWeekStart();
  const { data, isLoading, isError, refetch } = useMyWeekGet(orgId, week);

  return (
    <>
      <PageHeader
        title="My week"
        description="Commit to one thing you'll ship by Friday, and tick it off as you go."
      >
        <WeekSwitcher
          week={week}
          onChange={(next) =>
            navigate({
              search: { week: next === currentWeekStart() ? undefined : next },
            })
          }
        />
      </PageHeader>

      {isLoading && <PageSkeleton />}
      {isError && <ErrorState onRetry={() => void refetch()} />}
      {data && <WeekBody key={week} orgId={orgId} week={week} data={data} />}
    </>
  );
}

function WeekBody({
  orgId,
  week,
  data,
}: {
  orgId: string;
  week: string;
  data: MyWeekResponse;
}) {
  const [start, setStart] = useState<"blank" | "notes" | null>(null);
  const { plan, reviewers } = data;

  if (plan === null) {
    if (start) {
      return (
        <PlanEditor
          orgId={orgId}
          weekStart={week}
          plan={null}
          reviewers={reviewers}
          startFromNotes={start === "notes"}
        />
      );
    }
    if (!canStartPlan(week)) {
      const past = week < currentWeekStart();
      return (
        <StateMessage
          icon={CalendarX}
          title="No plan for this week"
          description={
            past
              ? "You didn't write a plan for this week."
              : "You can plan up to four weeks ahead."
          }
        />
      );
    }
    return <StartPlan onStart={setStart} />;
  }

  if (plan.status === "draft") {
    return (
      <PlanEditor
        orgId={orgId}
        weekStart={week}
        plan={plan}
        reviewers={reviewers}
      />
    );
  }

  return (
    <div className="space-y-4">
      {plan.status === "submitted" && (
        <p className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
          {reviewers.length > 0
            ? `Waiting for ${reviewers.map(fullName).join(" or ")} to approve. You can tick tasks off in the meantime.`
            : "Submitted. No team lead can approve it yet; ask an admin to add you to a team with a lead."}
        </p>
      )}
      <PlanView orgId={orgId} plan={plan} />
    </div>
  );
}

function StartPlan({
  onStart,
}: {
  onStart: (mode: "blank" | "notes") => void;
}) {
  return (
    <section className="rounded-xl border bg-background p-6 sm:p-8">
      <div className="max-w-xl">
        <h2 className="text-lg font-semibold tracking-tight">
          What&apos;s the one thing you&apos;ll ship by Friday?
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          A plan is one main task and why it matters, a few sub-goals that get
          it over the line, and how users will hear about it. Your lead approves
          it, and you tick it off during the week.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button size="lg" onClick={() => onStart("blank")}>
            <PenLine className="size-4" />
            Write my plan
          </Button>
          <Button size="lg" variant="outline" onClick={() => onStart("notes")}>
            <Wand2 className="size-4" />
            Draft it from my notes
          </Button>
        </div>
      </div>
      <div className="mt-8 grid gap-3 border-t pt-6 text-sm sm:grid-cols-2">
        <p className="flex gap-2">
          <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" />
          <span>
            <span className="font-medium">A result you can check:</span>{" "}
            <span className="text-muted-foreground">
              &ldquo;Checkout handles expired cards, confirmed on staging&rdquo;
            </span>
          </span>
        </p>
        <p className="flex gap-2">
          <X className="mt-0.5 size-4 shrink-0 text-rose-600" />
          <span>
            <span className="font-medium">Work you&apos;ll do:</span>{" "}
            <span className="text-muted-foreground">
              &ldquo;Implement checkout&rdquo;
            </span>
          </span>
        </p>
      </div>
    </section>
  );
}
