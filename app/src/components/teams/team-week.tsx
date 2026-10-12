import { Link } from "@tanstack/react-router";
import { Star } from "lucide-react";
import { useTeamWeekGet } from "@/api/endpoints/teams/teams";
import type { TeamWeekMember } from "@/api/model";
import { Avatar } from "@/components/app-shell";
import {
  ShippedBadge,
  StatusBadge,
  TaskProgress,
} from "@/components/plans/plan-bits";
import { ErrorState, ForbiddenState, PageSkeleton } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { getApiErrorMessage, getApiErrorStatus } from "@/lib/api-error";
import { fullName } from "@/lib/utils";

// The lead's view of the week: everyone on the team at a glance.
export function TeamWeek({
  orgId,
  teamId,
  week,
}: {
  orgId: string;
  teamId: string;
  week: string;
}) {
  const { data, error, isLoading, refetch } = useTeamWeekGet(
    orgId,
    teamId,
    week,
    {
      query: { retry: false },
    }
  );

  if (isLoading) {
    return <PageSkeleton />;
  }
  if (!data) {
    return getApiErrorStatus(error) === 403 ? (
      <ForbiddenState description={getApiErrorMessage(error, "")} />
    ) : (
      <ErrorState onRetry={() => void refetch()} />
    );
  }

  const { stats } = data;
  const tiles = [
    { label: "Submitted", value: `${stats.submitted}/${stats.members}` },
    { label: "Approved", value: `${stats.approved}/${stats.members}` },
    {
      label: "Tasks done",
      value: stats.tasks_total
        ? `${stats.tasks_done}/${stats.tasks_total}`
        : "—",
    },
    {
      label: "Shipped",
      value: stats.done ? `${stats.shipped}/${stats.done}` : "—",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label} className="rounded-xl border bg-background p-4">
            <p className="text-xs text-muted-foreground">{tile.label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">
              {tile.value}
            </p>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border bg-background">
        <ul className="divide-y">
          {data.members.map((row) => (
            <MemberRow
              key={row.member.id}
              orgId={orgId}
              row={row}
              viewerIsLead={data.viewer_is_lead}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}

function MemberRow({
  orgId,
  row,
  viewerIsLead,
}: {
  orgId: string;
  row: TeamWeekMember;
  viewerIsLead: boolean;
}) {
  const { member, plan, is_lead } = row;
  const canOpen = plan !== null && plan.main_task !== null;
  const awaitingMe = viewerIsLead && plan?.status === "submitted" && !is_lead;

  return (
    <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar
          firstName={member.first_name}
          lastName={member.last_name}
          className="size-8"
        />
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm font-medium">
            {fullName(member)}
            {is_lead && (
              <Star
                className="size-3.5 text-amber-500"
                aria-label="Team lead"
              />
            )}
          </p>
          <p className="truncate text-sm text-muted-foreground">
            {plan === null
              ? "Hasn't started a plan"
              : (plan.main_task ?? "Writing a draft")}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 sm:justify-end">
        {plan && plan.tasks_total !== null && plan.tasks_done !== null && (
          <TaskProgress done={plan.tasks_done} total={plan.tasks_total} />
        )}
        {plan?.status === "done" ? (
          <ShippedBadge shipped={plan.main_task_shipped} />
        ) : plan ? (
          <StatusBadge
            status={plan.status}
            returned={plan.review_decision === "returned"}
          />
        ) : (
          <span className="text-xs text-muted-foreground">Not started</span>
        )}
        {canOpen && plan && (
          <Link
            to="/orgs/$orgId/plans/$planId"
            params={{ orgId, planId: plan.id }}
            className={buttonVariants({
              size: "sm",
              variant: awaitingMe ? "default" : "outline",
            })}
          >
            {awaitingMe ? "Review" : "View"}
          </Link>
        )}
      </div>
    </li>
  );
}
