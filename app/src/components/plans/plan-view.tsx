import { useState } from "react";
import { toast } from "sonner";
import {
  CircleCheck,
  CircleX,
  Flag,
  MessageSquareText,
  Undo2,
} from "lucide-react";
import {
  usePlanComplete,
  usePlanTaskUpdate,
  usePlanWithdraw,
} from "@/api/endpoints/plans/plans";
import { usePlanApprove, usePlanReturn } from "@/api/endpoints/reviews/reviews";
import type { PlanResponse, PlanTaskResponse } from "@/api/model";
import { Avatar } from "@/components/app-shell";
import { useSyncPlan } from "@/components/plans/plan-cache";
import {
  ShippedBadge,
  StatusBadge,
  TaskProgress,
} from "@/components/plans/plan-bits";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api-error";
import { describeWeek, formatDateTime } from "@/lib/week";
import { cn, fullName } from "@/lib/utils";

// A plan that is past drafting: submitted, approved, or closed. Shows what
// the viewer can do with it, as the API reports in `permissions`.
export function PlanView({
  orgId,
  plan,
  showAuthor = false,
}: {
  orgId: string;
  plan: PlanResponse;
  showAuthor?: boolean;
}) {
  const sync = useSyncPlan(orgId);
  const [pendingTask, setPendingTask] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [reviewMode, setReviewMode] = useState<"approve" | "return" | null>(
    null
  );

  const tick = usePlanTaskUpdate({
    mutation: {
      onSuccess: sync,
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't update the task.")),
      onSettled: () => setPendingTask(null),
    },
  });
  const withdraw = usePlanWithdraw({
    mutation: {
      onSuccess: (updated) => {
        sync(updated);
        toast.success("Plan withdrawn. Edit it and submit again.");
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't withdraw the plan.")),
    },
  });

  const { permissions } = plan;
  const main = plan.tasks.find((task) => task.kind === "main");
  const subGoals = plan.tasks.filter((task) => task.kind === "sub_goal");
  const goToMarket = plan.tasks.filter((task) => task.kind === "go_to_market");

  const toggle = (task: PlanTaskResponse) => {
    setPendingTask(task.id);
    tick.mutate({
      organizationId: orgId,
      planId: plan.id,
      taskId: task.id,
      data: { status: task.status === "done" ? "todo" : "done" },
    });
  };

  const taskRow = (task: PlanTaskResponse, prominent = false) => (
    <li key={task.id} className="flex items-start gap-3">
      <Checkbox
        className="mt-0.5"
        checked={task.status === "done"}
        disabled={!permissions.can_tick || pendingTask === task.id}
        onCheckedChange={() => toggle(task)}
        aria-label={`Mark "${task.title}" as ${task.status === "done" ? "not done" : "done"}`}
      />
      <span
        className={cn(
          prominent ? "text-base font-medium" : "text-sm",
          task.status === "done" && "text-muted-foreground line-through"
        )}
      >
        {task.title}
      </span>
    </li>
  );

  return (
    <section className="rounded-xl border bg-background">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          {showAuthor && (
            <Avatar
              firstName={plan.author.first_name}
              lastName={plan.author.last_name}
              className="size-8"
            />
          )}
          <div className="min-w-0">
            <h2 className="truncate font-medium">
              {showAuthor ? `${fullName(plan.author)} · ` : "Plan for "}
              {describeWeek(plan.week_start).toLowerCase()}
            </h2>
            {plan.submitted_at && (
              <p className="text-xs text-muted-foreground">
                Submitted {formatDateTime(plan.submitted_at)}
              </p>
            )}
          </div>
          <StatusBadge status={plan.status} />
        </div>
        <TaskProgress done={plan.tasks_done} total={plan.tasks_total} />
      </div>

      <div className="space-y-6 p-4 sm:p-5">
        {plan.review_decision &&
          plan.reviewed_by &&
          plan.status !== "draft" && (
            <div className="flex gap-3 rounded-lg bg-muted/60 p-3 text-sm">
              <MessageSquareText className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <p>
                <span className="font-medium">
                  {plan.review_decision === "approved"
                    ? `Approved by ${fullName(plan.reviewed_by)}`
                    : `Sent back earlier by ${fullName(plan.reviewed_by)}`}
                </span>
                {plan.reviewed_at && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {formatDateTime(plan.reviewed_at)}
                  </span>
                )}
                {plan.review_comment && (
                  <span className="block text-muted-foreground">
                    &ldquo;{plan.review_comment}&rdquo;
                  </span>
                )}
              </p>
            </div>
          )}

        {plan.status === "done" && (
          <div
            className={cn(
              "flex gap-3 rounded-lg border p-4",
              plan.main_task_shipped
                ? "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/30"
                : "border-rose-200 bg-rose-50/60 dark:border-rose-900 dark:bg-rose-950/30"
            )}
          >
            {plan.main_task_shipped ? (
              <CircleCheck className="size-5 shrink-0 text-emerald-600" />
            ) : (
              <CircleX className="size-5 shrink-0 text-rose-600" />
            )}
            <div className="text-sm">
              <ShippedBadge shipped={plan.main_task_shipped} />
              {plan.outcome_note && (
                <p className="mt-1 text-muted-foreground">
                  {plan.outcome_note}
                </p>
              )}
            </div>
          </div>
        )}

        <div>
          <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Main task
          </p>
          <ul className="mt-2">{main && taskRow(main, true)}</ul>
          <p className="mt-2 pl-7 text-sm text-muted-foreground">
            {plan.why_it_matters ? (
              <>
                <span className="font-medium text-foreground">
                  Why it matters:{" "}
                </span>
                {plan.why_it_matters}
              </>
            ) : (
              "No reason given for why this matters."
            )}
          </p>
        </div>

        <TaskGroup title="Sub-goals" empty="No sub-goals.">
          {subGoals.map((task) => taskRow(task))}
        </TaskGroup>
        <TaskGroup title="Go-to-market goals" empty="No go-to-market goals.">
          {goToMarket.map((task) => taskRow(task))}
        </TaskGroup>
      </div>

      {(permissions.can_withdraw ||
        permissions.can_complete ||
        permissions.can_review) && (
        <div className="flex flex-wrap justify-end gap-2 border-t px-4 py-3 sm:px-5">
          {permissions.can_withdraw && (
            <Button
              variant="outline"
              disabled={withdraw.isPending}
              onClick={() =>
                withdraw.mutate({ organizationId: orgId, planId: plan.id })
              }
            >
              {withdraw.isPending ? <Spinner /> : <Undo2 className="size-4" />}
              Withdraw to edit
            </Button>
          )}
          {permissions.can_complete && (
            <Button onClick={() => setCompleting(true)}>
              <Flag className="size-4" />
              Close the week
            </Button>
          )}
          {permissions.can_review && (
            <>
              <Button variant="outline" onClick={() => setReviewMode("return")}>
                Send back
              </Button>
              <Button onClick={() => setReviewMode("approve")}>
                <CircleCheck className="size-4" />
                Approve
              </Button>
            </>
          )}
        </div>
      )}

      <CompleteWeekDialog
        open={completing}
        onOpenChange={setCompleting}
        orgId={orgId}
        plan={plan}
      />
      <ReviewDialog
        mode={reviewMode}
        onClose={() => setReviewMode(null)}
        orgId={orgId}
        plan={plan}
      />
    </section>
  );
}

function TaskGroup({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: React.ReactNode[];
}) {
  return (
    <div>
      <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
        {title}
      </p>
      {children.length > 0 ? (
        <ul className="mt-2 space-y-2">{children}</ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function CompleteWeekDialog({
  open,
  onOpenChange,
  orgId,
  plan,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  plan: PlanResponse;
}) {
  const sync = useSyncPlan(orgId);
  const [shipped, setShipped] = useState<boolean | null>(null);
  const [note, setNote] = useState("");
  const complete = usePlanComplete({
    mutation: {
      onSuccess: (updated) => {
        sync(updated);
        onOpenChange(false);
        toast.success(
          updated.main_task_shipped ? "Shipped. Nice week." : "Week closed."
        );
      },
    },
  });
  const main = plan.tasks.find((task) => task.kind === "main");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Close the week</DialogTitle>
          <DialogDescription>Did your main task ship?</DialogDescription>
        </DialogHeader>
        {main && (
          <p className="rounded-lg bg-muted/60 p-3 text-sm font-medium">
            {main.title}
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          {[
            {
              value: true,
              label: "It shipped",
              icon: CircleCheck,
              tone: "text-emerald-600",
            },
            {
              value: false,
              label: "It didn't",
              icon: CircleX,
              tone: "text-rose-600",
            },
          ].map(({ value, label, icon: Icon, tone }) => (
            <button
              key={label}
              type="button"
              aria-pressed={shipped === value}
              onClick={() => setShipped(value)}
              className={cn(
                "flex items-center justify-center gap-2 rounded-lg border p-3 text-sm font-medium transition-colors hover:bg-muted/50",
                shipped === value &&
                  "border-primary bg-primary/5 ring-2 ring-primary/20"
              )}
            >
              <Icon className={cn("size-4", tone)} /> {label}
            </button>
          ))}
        </div>
        <Textarea
          rows={3}
          maxLength={1000}
          placeholder={
            shipped === false
              ? "What got in the way? It helps your lead plan next week."
              : "Anything worth noting? (optional)"
          }
          value={note}
          onChange={(event) => setNote(event.target.value)}
          aria-label="Outcome note"
        />
        {complete.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getApiErrorMessage(
              complete.error,
              "Couldn't close the week. Try again."
            )}
          </p>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Not yet
          </Button>
          <Button
            disabled={shipped === null || complete.isPending}
            onClick={() =>
              shipped !== null &&
              complete.mutate({
                organizationId: orgId,
                planId: plan.id,
                data: {
                  main_task_shipped: shipped,
                  outcome_note: note.trim() || null,
                },
              })
            }
          >
            {complete.isPending && <Spinner />}
            Close the week
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReviewDialog({
  mode,
  onClose,
  orgId,
  plan,
}: {
  mode: "approve" | "return" | null;
  onClose: () => void;
  orgId: string;
  plan: PlanResponse;
}) {
  const sync = useSyncPlan(orgId);
  const [comment, setComment] = useState("");
  const done = (message: string) => (updated: PlanResponse) => {
    sync(updated);
    setComment("");
    onClose();
    toast.success(message);
  };
  const approve = usePlanApprove({
    mutation: { onSuccess: done(`Approved ${plan.author.first_name}'s plan`) },
  });
  const sendBack = usePlanReturn({
    mutation: { onSuccess: done(`Sent back to ${plan.author.first_name}`) },
  });
  const pending = approve.isPending || sendBack.isPending;
  const error = approve.error ?? sendBack.error;
  const returning = mode === "return";

  return (
    <Dialog open={mode !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {returning
              ? "Send the plan back"
              : `Approve ${plan.author.first_name}'s plan`}
          </DialogTitle>
          <DialogDescription>
            {returning
              ? "Say what to change. The plan goes back to draft with your comment on it."
              : "Add a note if you like. They'll see it on their plan."}
          </DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          rows={4}
          maxLength={1000}
          placeholder={
            returning
              ? "e.g. This is three projects. Pick the Postgres upgrade and move the rest to next week."
              : "e.g. Good scope. Ship it."
          }
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          aria-label="Comment"
        />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {getApiErrorMessage(error, "That didn't work. Try again.")}
          </p>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          {returning ? (
            <Button
              disabled={!comment.trim() || pending}
              onClick={() =>
                sendBack.mutate({
                  organizationId: orgId,
                  planId: plan.id,
                  data: { comment: comment.trim() },
                })
              }
            >
              {pending && <Spinner />}
              Send back
            </Button>
          ) : (
            <Button
              disabled={pending}
              onClick={() =>
                approve.mutate({
                  organizationId: orgId,
                  planId: plan.id,
                  data: { comment: comment.trim() || null },
                })
              }
            >
              {pending && <Spinner />}
              Approve
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
