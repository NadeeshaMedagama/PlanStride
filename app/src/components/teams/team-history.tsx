import { useTeamHistory } from "@/api/endpoints/teams/teams";
import { ErrorState, ForbiddenState, PageSkeleton } from "@/components/states";
import { getApiErrorMessage, getApiErrorStatus } from "@/lib/api-error";
import { describeWeek, formatWeekRange } from "@/lib/week";

// Past weeks for the team's current members: how many planned, got approved,
// closed out and shipped. Picking a week opens it in the week view.
export function TeamHistory({
  orgId,
  teamId,
  onPickWeek,
}: {
  orgId: string;
  teamId: string;
  onPickWeek: (week: string) => void;
}) {
  const { data, error, isLoading, refetch } = useTeamHistory(
    orgId,
    teamId,
    { weeks: 8 },
    { query: { retry: false } }
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

  return (
    <div className="overflow-x-auto rounded-xl border bg-background">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-4 py-2.5 font-medium sm:px-5">Week</th>
            <th className="px-3 py-2.5 font-medium">Submitted</th>
            <th className="px-3 py-2.5 font-medium">Approved</th>
            <th className="px-3 py-2.5 font-medium">Tasks done</th>
            <th className="px-3 py-2.5 font-medium">Shipped</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {data.weeks.map((week) => {
            const shipRate = week.done
              ? Math.round((week.shipped / week.done) * 100)
              : null;
            return (
              <tr
                key={week.week_start}
                className="transition-colors hover:bg-muted/40"
              >
                <td className="px-4 py-3 sm:px-5">
                  <button
                    type="button"
                    className="text-left hover:underline"
                    onClick={() => onPickWeek(week.week_start)}
                  >
                    <span className="block font-medium">
                      {describeWeek(week.week_start)}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {formatWeekRange(week.week_start)}
                    </span>
                  </button>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {week.submitted}/{week.members}
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {week.approved}/{week.members}
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {week.tasks_total
                    ? `${week.tasks_done}/${week.tasks_total}`
                    : "—"}
                </td>
                <td className="px-3 py-3">
                  {shipRate === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <span className="inline-flex items-center gap-2 tabular-nums">
                      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-muted">
                        <span
                          className="block h-full rounded-full bg-emerald-500"
                          style={{ width: `${shipRate}%` }}
                        />
                      </span>
                      {week.shipped}/{week.done}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
