import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { History } from "lucide-react";
import { useMyPlanList } from "@/api/endpoints/plans/plans";
import {
  ShippedBadge,
  StatusBadge,
  TaskProgress,
} from "@/components/plans/plan-bits";
import {
  ErrorState,
  PageHeader,
  PageSkeleton,
  StateMessage,
} from "@/components/states";
import { Button } from "@/components/ui/button";
import { useOrg } from "@/contexts/org-context";
import { describeWeek, formatWeekRange } from "@/lib/week";

const PAGE = 12;

export const Route = createFileRoute("/_main/orgs/$orgId/history")({
  head: () => ({ meta: [{ title: "History · PlanStride" }] }),
  component: HistoryPage,
});

function HistoryPage() {
  const { orgId } = useOrg();
  const [limit, setLimit] = useState(PAGE);
  const { data, isLoading, isError, refetch, isFetching } = useMyPlanList(
    orgId,
    {
      limit,
      offset: 0,
    }
  );
  const plans = data?.items ?? [];
  const shipped = plans.filter(
    (plan) => plan.main_task_shipped === true
  ).length;
  const closed = plans.filter((plan) => plan.status === "done").length;

  return (
    <>
      <PageHeader
        title="History"
        description={
          closed > 0
            ? `You shipped your main task in ${shipped} of your last ${closed} closed weeks.`
            : "Every week you've planned, newest first."
        }
      />
      {isLoading && <PageSkeleton />}
      {isError && <ErrorState onRetry={() => void refetch()} />}
      {data && plans.length === 0 && (
        <StateMessage
          icon={History}
          title="No plans yet"
          description="Your weeks will show up here once you've written your first plan."
        />
      )}
      {plans.length > 0 && (
        <ul className="divide-y rounded-xl border bg-background">
          {plans.map((plan) => (
            <li key={plan.id}>
              <Link
                to="/orgs/$orgId/plans/$planId"
                params={{ orgId, planId: plan.id }}
                className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-muted/40 sm:flex-row sm:items-center sm:gap-4 sm:px-5"
              >
                <div className="w-36 shrink-0">
                  <p className="text-sm font-medium">
                    {describeWeek(plan.week_start)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatWeekRange(plan.week_start)}
                  </p>
                </div>
                <p className="min-w-0 flex-1 truncate text-sm">
                  {plan.main_task}
                </p>
                <div className="flex shrink-0 items-center gap-4">
                  {plan.tasks_total !== null && plan.tasks_done !== null && (
                    <TaskProgress
                      done={plan.tasks_done}
                      total={plan.tasks_total}
                    />
                  )}
                  {plan.status === "done" ? (
                    <ShippedBadge shipped={plan.main_task_shipped} />
                  ) : (
                    <StatusBadge
                      status={plan.status}
                      returned={plan.review_decision === "returned"}
                    />
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {data && data.total > plans.length && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            disabled={isFetching}
            onClick={() => setLimit((current) => current + PAGE)}
          >
            {isFetching ? "Loading…" : "Show older weeks"}
          </Button>
        </div>
      )}
    </>
  );
}
