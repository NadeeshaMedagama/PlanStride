import { useState } from "react";
import {
  Check,
  CircleCheck,
  CircleX,
  RotateCcw,
  Sparkles,
  Star,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Real product moments, rendered in the page rather than screenshotted, so
// they stay sharp at every size and read correctly to screen readers.

function Tick({ done }: { done: boolean }) {
  return (
    <span
      className={cn(
        "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[4px] border",
        done
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background"
      )}
      aria-hidden
    >
      {done && <Check className="size-3" strokeWidth={3} />}
    </span>
  );
}

function TaskRow({
  title,
  done,
  big = false,
}: {
  title: string;
  done: boolean;
  big?: boolean;
}) {
  return (
    <li className="flex items-start gap-2.5">
      <Tick done={done} />
      <span
        className={cn(
          big ? "text-[15px] font-medium" : "text-sm",
          done && "text-muted-foreground line-through"
        )}
      >
        {title}
      </span>
    </li>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
      {children}
    </p>
  );
}

// The hero: one engineer's approved week, mid-way through.
export function PlanCard() {
  return (
    <div
      className="rounded-2xl border bg-background shadow-[0_30px_60px_-30px_rgba(15,27,22,0.35)]"
      role="img"
      aria-label="An approved weekly plan in PlanStride, with three of five tasks done"
    >
      <div className="flex items-center justify-between gap-3 border-b px-5 py-3.5">
        <div>
          <p className="text-sm font-medium">Aisha&apos;s week</p>
          <p className="text-xs text-muted-foreground">
            Approved by Marcus · Monday 14:10
          </p>
        </div>
        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
          Approved
        </span>
      </div>
      <div className="space-y-4 px-5 py-4">
        <div className="space-y-2">
          <Label>Main task</Label>
          <ul>
            <TaskRow
              big
              done={false}
              title="Expired cards are retried automatically at renewal, verified on staging"
            />
          </ul>
          <p className="pl-6.5 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              Why it matters:{" "}
            </span>
            expired cards are the top cause of failed renewals.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Sub-goals</Label>
          <ul className="space-y-1.5">
            <TaskRow
              done
              title="Card updater webhook stores new expiry dates"
            />
            <TaskRow done title="Retry schedule covered by integration tests" />
            <TaskRow
              done={false}
              title="Failed-retry email uses the new template"
            />
          </ul>
        </div>
        <div className="space-y-2">
          <Label>Go-to-market</Label>
          <ul className="space-y-1.5">
            <TaskRow
              done
              title="checkout_retry_succeeded tracked in analytics"
            />
            <TaskRow
              done={false}
              title="Changelog entry for automatic card updates"
            />
          </ul>
        </div>
      </div>
      <div className="flex items-center gap-2 border-t px-5 py-3 text-xs text-muted-foreground">
        <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
          <span className="block h-full w-3/5 rounded-full bg-primary" />
        </span>
        3 of 5 done · Wednesday
      </div>
    </div>
  );
}

const ORIGINAL = "Implement checkout";
const REWRITE = "Checkout handles expired cards, confirmed on staging";

// The AI review, as members see it: a finding under the task it's about, with
// a rewrite that applies in one click. Try it.
export function ReviewDemo() {
  const [applied, setApplied] = useState(false);

  return (
    <div className="rounded-2xl border bg-background shadow-[0_30px_60px_-30px_rgba(15,27,22,0.35)]">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-3.5">
        <p className="text-sm font-medium">Lena&apos;s plan · draft</p>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800">
          <Sparkles className="size-3" /> AI review
        </span>
      </div>
      <div className="space-y-3 px-5 py-4">
        <Label>Main task</Label>
        <div
          className={cn(
            "rounded-lg border px-3 py-2.5 text-[15px] transition-colors",
            applied && "border-emerald-300 bg-emerald-50/60"
          )}
          aria-live="polite"
        >
          {applied ? REWRITE : ORIGINAL}
        </div>

        {applied ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50/60 px-3 py-2.5 text-sm text-emerald-900">
            <span className="flex items-center gap-2">
              <CircleCheck className="size-4" /> Applied. Now it&apos;s
              something you can tick off.
            </span>
            <button
              type="button"
              onClick={() => setApplied(false)}
              className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800 hover:underline"
            >
              <RotateCcw className="size-3" /> Reset
            </button>
          </div>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-sm">
            <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-amber-800 uppercase">
              <Target className="size-3.5" /> Work, not a result
            </p>
            <p className="mt-1.5 text-amber-950">
              &ldquo;Implement checkout&rdquo; describes work to do. Nobody can
              tick it off honestly on Friday.
            </p>
            <div className="mt-2.5 rounded-md border border-amber-200/80 bg-background px-3 py-2">
              <p className="text-xs text-muted-foreground">Suggested</p>
              <p className="font-medium">{REWRITE}</p>
            </div>
            <button
              type="button"
              onClick={() => setApplied(true)}
              className="mt-2.5 inline-flex h-7 items-center gap-1.5 rounded-md bg-primary px-2.5 text-[0.8rem] font-medium text-primary-foreground hover:bg-primary/85"
            >
              <Sparkles className="size-3.5" /> Use this wording
            </button>
          </div>
        )}

        <div className="space-y-2 pt-1">
          <p className="flex items-start gap-2 text-sm">
            <CircleX className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <span>
              <span className="font-medium">No go-to-market goal.</span>{" "}
              <span className="text-muted-foreground">
                Suggested: &ldquo;Changelog entry announcing card retries&rdquo;
              </span>
            </span>
          </p>
          <p className="flex items-start gap-2 text-sm">
            <CircleX className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <span>
              <span className="font-medium">
                Doesn&apos;t say why it matters.
              </span>{" "}
              <span className="text-muted-foreground">
                Suggested: &ldquo;Expired cards are our top cause of failed
                renewals.&rdquo;
              </span>
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}

const TEAM = [
  {
    name: "Aisha Bello",
    task: "Dunning emails stop once a payment succeeds",
    status: "approved",
    done: 3,
    total: 4,
  },
  {
    name: "Tom Novak",
    task: "Postgres 16 upgrade done on staging, zero failed jobs",
    status: "approved",
    done: 2,
    total: 5,
  },
  {
    name: "Lena Fischer",
    task: "Checkout handles expired cards, confirmed on staging",
    status: "submitted",
    done: 0,
    total: 5,
  },
  { name: "Dev Patel", task: null, status: "none", done: 0, total: 0 },
] as const;

// A lead's view: the whole team's week at a glance.
export function TeamWeekMock() {
  return (
    <div
      className="overflow-hidden rounded-2xl border bg-background shadow-[0_30px_60px_-30px_rgba(15,27,22,0.35)]"
      role="img"
      aria-label="A team lead's view of the week: who submitted, who's approved, and task progress for each member"
    >
      <div className="flex items-center justify-between border-b px-5 py-3.5">
        <p className="flex items-center gap-2 text-sm font-medium">
          Payments <Star className="size-3.5 text-amber-500" />
          <span className="font-normal text-muted-foreground">· this week</span>
        </p>
        <span className="text-xs text-muted-foreground">3 of 4 submitted</span>
      </div>
      <ul className="divide-y">
        {TEAM.map((member) => (
          <li key={member.name} className="flex items-center gap-3 px-5 py-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-[11px] font-semibold text-emerald-900">
              {member.name
                .split(" ")
                .map((part) => part[0])
                .join("")}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{member.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {member.task ?? "Hasn't started a plan"}
              </p>
            </div>
            {member.total > 0 && (
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
                <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-primary"
                    style={{ width: `${(member.done / member.total) * 100}%` }}
                  />
                </span>
                {member.done}/{member.total}
              </span>
            )}
            {member.status === "approved" && (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
                Approved
              </span>
            )}
            {member.status === "submitted" && (
              <span className="rounded-md bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground">
                Review
              </span>
            )}
            {member.status === "none" && (
              <span className="text-[11px] text-muted-foreground">
                Not started
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
