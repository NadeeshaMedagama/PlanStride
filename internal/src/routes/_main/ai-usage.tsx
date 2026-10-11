import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { keepPreviousData } from "@tanstack/react-query";
import { CircleCheck, CircleX, Clock } from "lucide-react";
import {
  useAiUsageEvents,
  useAiUsageSummary,
} from "@/api/endpoints/ai-usage/ai-usage";
import type { AIUsageTotals } from "@/api/model";
import { DailyOutcomesChart } from "@/components/ai-usage/daily-outcomes-chart";
import { PageTitle, SectionHeading, StatTile } from "@/components/stat-tile";
import { Button } from "@/components/ui/button";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatAgo,
  formatCount,
  formatDateTime,
  formatPercent,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const RANGES = [7, 30, 90] as const;

const FEATURE_LABELS: Record<string, string> = {
  plan_review: "Plan review",
  plan_draft: "Draft from notes",
};

const ERROR_LABELS: Record<string, string> = {
  provider_rate_limit: "Gemini rate limit (429)",
  throttled: "Our per-user throttle",
  timeout: "Timed out",
  provider_error: "Provider error",
  invalid_output: "Unusable model output",
  not_configured: "No API key configured",
  internal_error: "Internal error",
};

export const Route = createFileRoute("/_main/ai-usage")({
  head: () => ({ meta: [{ title: "AI usage · PlanStride Internal" }] }),
  component: AiUsagePage,
});

function failureRate(totals: AIUsageTotals): string {
  return formatPercent(totals.failed + totals.rate_limited, totals.calls);
}

function AiUsagePage() {
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const { data, isFetching } = useAiUsageSummary(
    { days },
    { query: { placeholderData: keepPreviousData } }
  );

  return (
    <>
      <PageTitle
        title="AI usage"
        description="What the AI features cost and where they break. Calls are counted, never read: no prompts or answers are stored."
      />

      {/* One filter row; it scopes everything below. */}
      <div
        className="flex items-center gap-1"
        role="group"
        aria-label="Time range"
      >
        {RANGES.map((range) => (
          <Button
            key={range}
            size="sm"
            variant={range === days ? "secondary" : "ghost"}
            aria-pressed={range === days}
            onClick={() => setDays(range)}
          >
            Last {range} days
          </Button>
        ))}
        {data && (
          <span className="ml-3 text-xs text-muted-foreground">
            Model: {data.model_name}
          </span>
        )}
      </div>

      {!data ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : (
        // Refetching keeps the frame: the previous numbers stay, dimmed.
        <div
          className={cn(
            "space-y-6 transition-opacity",
            isFetching && "opacity-60"
          )}
        >
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Calls"
              value={formatCount(data.totals.calls)}
              note={`${formatPercent(data.totals.succeeded, data.totals.calls)} succeeded`}
            />
            <StatTile
              label="Failed or rate limited"
              value={formatCount(data.totals.failed + data.totals.rate_limited)}
              note={`${formatCount(data.totals.failed)} failed · ${formatCount(data.totals.rate_limited)} rate limited`}
              tone={
                data.totals.failed + data.totals.rate_limited > 0
                  ? "critical"
                  : "default"
              }
            />
            <StatTile
              label="Tokens"
              value={formatCount(
                data.totals.input_tokens + data.totals.output_tokens
              )}
              note={`${formatCount(data.totals.input_tokens)} in · ${formatCount(data.totals.output_tokens)} out`}
            />
            <StatTile
              label="Average latency"
              value={
                data.totals.avg_latency_ms === null
                  ? "—"
                  : `${(data.totals.avg_latency_ms / 1000).toFixed(1)}s`
              }
              note="Per call, including failures"
            />
          </div>

          <section className="space-y-3 rounded-xl border bg-background p-5">
            <SectionHeading title="Calls per day, by outcome" />
            <DailyOutcomesChart days={data.by_day} />
          </section>

          <section className="space-y-3">
            <SectionHeading
              title="By organization"
              description="Who uses the AI, and whose calls break."
            />
            <div className="overflow-x-auto rounded-xl border bg-background">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2.5 font-medium">Organization</th>
                    <th className="px-3 py-2.5 text-right font-medium">
                      Calls
                    </th>
                    <th className="px-3 py-2.5 text-right font-medium">
                      Failed
                    </th>
                    <th className="px-3 py-2.5 text-right font-medium">
                      Rate limited
                    </th>
                    <th className="px-3 py-2.5 text-right font-medium">
                      Failure rate
                    </th>
                    <th className="px-3 py-2.5 text-right font-medium">
                      Tokens
                    </th>
                    <th className="px-4 py-2.5 text-right font-medium">
                      Last call
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y tabular-nums">
                  {data.by_organization.length === 0 && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-8 text-center text-muted-foreground"
                      >
                        No AI calls in this period.
                      </td>
                    </tr>
                  )}
                  {data.by_organization.map((row) => (
                    <tr key={row.organization_id} className="hover:bg-muted/40">
                      <td className="px-4 py-2.5">
                        <Link
                          to="/organizations/$organizationId"
                          params={{ organizationId: row.organization_id }}
                          className="font-medium hover:underline"
                        >
                          {row.organization_name}
                        </Link>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {formatCount(row.totals.calls)}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {row.totals.failed}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {row.totals.rate_limited}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {failureRate(row.totals)}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {formatCount(
                          row.totals.input_tokens + row.totals.output_tokens
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">
                        {formatAgo(row.last_call_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="space-y-3">
              <SectionHeading title="By feature" />
              <div className="divide-y rounded-xl border bg-background text-sm">
                {data.by_feature.length === 0 && (
                  <p className="px-4 py-6 text-center text-muted-foreground">
                    No calls.
                  </p>
                )}
                {data.by_feature.map((row) => (
                  <div
                    key={row.feature}
                    className="flex items-center justify-between px-4 py-3"
                  >
                    <span className="font-medium">
                      {FEATURE_LABELS[row.feature] ?? row.feature}
                    </span>
                    <span className="text-muted-foreground tabular-nums">
                      {formatCount(row.totals.calls)} calls ·{" "}
                      {failureRate(row.totals)} failing
                    </span>
                  </div>
                ))}
              </div>
            </section>
            <section className="space-y-3">
              <SectionHeading title="Why calls failed" />
              <div className="divide-y rounded-xl border bg-background text-sm">
                {data.by_error_type.length === 0 && (
                  <p className="px-4 py-6 text-center text-muted-foreground">
                    Nothing failed in this period.
                  </p>
                )}
                {data.by_error_type.map((row) => (
                  <div
                    key={row.error_type}
                    className="flex items-center justify-between px-4 py-3"
                  >
                    <span>
                      {ERROR_LABELS[row.error_type] ?? row.error_type}
                    </span>
                    <span className="font-medium tabular-nums">
                      {row.count}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}

      <RecentEvents />
    </>
  );
}

const OUTCOMES = {
  success: {
    label: "Succeeded",
    icon: CircleCheck,
    className: "text-[var(--viz-good)]",
  },
  failed: {
    label: "Failed",
    icon: CircleX,
    className: "text-[var(--viz-critical)]",
  },
  rate_limited: {
    label: "Rate limited",
    icon: Clock,
    className: "text-amber-600",
  },
} as const;

type OutcomeFilter = "" | "success" | "failed" | "rate_limited";
const MAX_EVENTS = 100; // the API's page-size ceiling

function RecentEvents() {
  const [outcome, setOutcome] = useState<OutcomeFilter>("");
  const [limit, setLimit] = useState(25);
  const { data, isFetching } = useAiUsageEvents(
    { outcome: outcome || undefined, limit },
    { query: { placeholderData: keepPreviousData } }
  );

  return (
    <section className="space-y-3">
      <SectionHeading title="Recent calls" description="Metadata only.">
        <NativeSelect
          size="sm"
          value={outcome}
          aria-label="Filter by outcome"
          onChange={(event) => setOutcome(event.target.value as OutcomeFilter)}
        >
          <NativeSelectOption value="">All outcomes</NativeSelectOption>
          <NativeSelectOption value="success">Succeeded</NativeSelectOption>
          <NativeSelectOption value="failed">Failed</NativeSelectOption>
          <NativeSelectOption value="rate_limited">
            Rate limited
          </NativeSelectOption>
        </NativeSelect>
      </SectionHeading>
      <div
        className={cn(
          "overflow-x-auto rounded-xl border bg-background transition-opacity",
          isFetching && "opacity-60"
        )}
      >
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">When</th>
              <th className="px-3 py-2.5 font-medium">Organization</th>
              <th className="px-3 py-2.5 font-medium">User</th>
              <th className="px-3 py-2.5 font-medium">Feature</th>
              <th className="px-3 py-2.5 font-medium">Outcome</th>
              <th className="px-3 py-2.5 text-right font-medium">Latency</th>
              <th className="px-4 py-2.5 text-right font-medium">Tokens</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No calls match.
                </td>
              </tr>
            )}
            {data?.items.map((event) => {
              const { label, icon: Icon, className } = OUTCOMES[event.outcome];
              return (
                <tr key={event.id} className="hover:bg-muted/40">
                  <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                    {formatDateTime(event.created_at)}
                  </td>
                  <td className="px-3 py-2.5">{event.organization_name}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {event.user_email ?? "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    {FEATURE_LABELS[event.feature] ?? event.feature}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="inline-flex items-center gap-1.5">
                      <Icon className={cn("size-4", className)} aria-hidden />
                      {label}
                      {event.error_type && (
                        <span className="text-xs text-muted-foreground">
                          · {ERROR_LABELS[event.error_type] ?? event.error_type}
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {event.latency_ms === null
                      ? "—"
                      : `${(event.latency_ms / 1000).toFixed(1)}s`}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {event.input_tokens === null
                      ? "—"
                      : formatCount(
                          event.input_tokens + (event.output_tokens ?? 0)
                        )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data && data.total > data.items.length && limit < MAX_EVENTS && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            disabled={isFetching}
            onClick={() => setLimit((n) => Math.min(MAX_EVENTS, n + 25))}
          >
            Show more
          </Button>
        </div>
      )}
    </section>
  );
}
