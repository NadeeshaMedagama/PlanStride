import { Link, createFileRoute } from "@tanstack/react-router";
import { ClipboardCheck, ChevronRight } from "lucide-react";
import { useReviewQueue } from "@/api/endpoints/reviews/reviews";
import { Avatar } from "@/components/app-shell";
import {
  ErrorState,
  PageHeader,
  PageSkeleton,
  StateMessage,
} from "@/components/states";
import { useOrg } from "@/contexts/org-context";
import { describeWeek, formatDateTime } from "@/lib/week";
import { fullName } from "@/lib/utils";

export const Route = createFileRoute("/_main/orgs/$orgId/reviews")({
  head: () => ({ meta: [{ title: "Reviews · PlanStride" }] }),
  component: ReviewsPage,
});

function ReviewsPage() {
  const { orgId } = useOrg();
  const { data, isLoading, isError, refetch } = useReviewQueue(orgId);

  return (
    <>
      <PageHeader
        title="Reviews"
        description="Plans from your teams waiting for your approval, oldest first."
      />
      {isLoading && <PageSkeleton />}
      {isError && <ErrorState onRetry={() => void refetch()} />}
      {data && data.length === 0 && (
        <StateMessage
          icon={ClipboardCheck}
          title="You're all caught up"
          description="When someone on a team you lead submits a plan, it shows up here."
        />
      )}
      {data && data.length > 0 && (
        <ul className="divide-y rounded-xl border bg-background">
          {data.map(({ plan, teams }) => (
            <li key={plan.id}>
              <Link
                to="/orgs/$orgId/plans/$planId"
                params={{ orgId, planId: plan.id }}
                className="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/40 sm:px-5"
              >
                <Avatar
                  firstName={plan.author.first_name}
                  lastName={plan.author.last_name}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {fullName(plan.author)}
                    <span className="font-normal text-muted-foreground">
                      {" "}
                      · {teams.map((team) => team.name).join(", ")} ·{" "}
                      {describeWeek(plan.week_start).toLowerCase()}
                    </span>
                  </p>
                  <p className="mt-0.5 truncate text-sm">{plan.main_task}</p>
                  {plan.submitted_at && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Submitted {formatDateTime(plan.submitted_at)}
                    </p>
                  )}
                </div>
                <ChevronRight className="size-4 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
