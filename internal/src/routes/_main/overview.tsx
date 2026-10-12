import { Link, createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useOverviewGet } from "@/api/endpoints/overview/overview";
import { useAiUsageSummary } from "@/api/endpoints/ai-usage/ai-usage";
import { DailyOutcomesChart } from "@/components/ai-usage/daily-outcomes-chart";
import { PageTitle, SectionHeading, StatTile } from "@/components/stat-tile";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/contexts/user-context";
import { formatCount, formatPercent } from "@/lib/format";

export const Route = createFileRoute("/_main/overview")({
  head: () => ({ meta: [{ title: "Overview · PlanStride Internal" }] }),
  component: OverviewPage,
});

function OverviewPage() {
  const user = useCurrentUser();
  const { data, isError } = useOverviewGet();
  const { data: usage } = useAiUsageSummary({ days: 14 });

  return (
    <>
      <PageTitle
        title={user ? `Hello, ${user.first_name}` : "Overview"}
        description="How PlanStride is doing across every customer organization."
      />

      {isError && (
        <p className="text-sm text-destructive">
          Couldn&apos;t load the numbers.
        </p>
      )}
      {!data && !isError && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 rounded-xl" />
          ))}
        </div>
      )}
      {data && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Organizations"
            value={formatCount(data.organizations)}
            note={
              data.organizations_suspended
                ? `${data.organizations_suspended} suspended`
                : "None suspended"
            }
            tone={data.organizations_suspended ? "warning" : "default"}
          />
          <StatTile
            label="Users"
            value={formatCount(data.users)}
            note={`${data.users_deactivated} deactivated · ${data.staff} staff`}
          />
          <StatTile
            label="Plans this week"
            value={formatCount(data.plans_this_week)}
            note={`${data.plans_submitted_this_week} submitted for approval`}
          />
          <StatTile
            label="AI calls, last 24h"
            value={formatCount(data.ai_calls_24h)}
            note={
              data.ai_calls_24h
                ? `${formatPercent(data.ai_failed_24h + data.ai_rate_limited_24h, data.ai_calls_24h)} failed or rate limited`
                : "No calls"
            }
            tone={
              data.ai_failed_24h + data.ai_rate_limited_24h > 0
                ? "critical"
                : "default"
            }
          />
        </div>
      )}

      <section className="space-y-3 rounded-xl border bg-background p-5">
        <SectionHeading
          title="AI calls, last 14 days"
          description="Every call is logged against the organization that made it."
        >
          <Link
            to="/ai-usage"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            AI usage details <ArrowRight className="size-3.5" />
          </Link>
        </SectionHeading>
        {usage ? (
          <DailyOutcomesChart days={usage.by_day} />
        ) : (
          <Skeleton className="h-56 w-full" />
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <Link
          to="/organizations"
          className="rounded-xl border bg-background p-5 transition-colors hover:border-primary/40"
        >
          <p className="font-medium">Organizations</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Size, activity and status of every customer. Suspend or reinstate.
          </p>
        </Link>
        <Link
          to="/users"
          className="rounded-xl border bg-background p-5 transition-colors hover:border-primary/40"
        >
          <p className="font-medium">Users</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Find an account, see its organizations, deactivate or reset a
            password.
          </p>
        </Link>
      </section>
    </>
  );
}
