import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Lightbulb,
  MessageSquareWarning,
  Plus,
  Save,
  Send,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { useAiPlanReview } from "@/api/endpoints/ai/ai";
import {
  getMyPlanListQueryKey,
  getMyWeekGetQueryKey,
  usePlanCreate,
  usePlanDelete,
  usePlanSubmit,
  usePlanUpdate,
} from "@/api/endpoints/plans/plans";
import type {
  MyWeekResponse,
  PlanContentRequest,
  PlanDraftResponse,
  PlanResponse,
  PlanReviewResponse,
  PlanTaskResponse,
  ReviewTaskRequest,
  UserSummary,
} from "@/api/model";
import {
  AiErrorAlert,
  FindingCard,
  ReviewSummary,
  ReviewingNotice,
  withIds,
  type Finding,
} from "@/components/plans/ai-review";
import { BrainDumpDialog } from "@/components/plans/brain-dump-dialog";
import { StatusBadge } from "@/components/plans/plan-bits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { getApiErrorMessage } from "@/lib/api-error";
import { describeWeek } from "@/lib/week";
import { cn, fullName } from "@/lib/utils";

const MAX_SUB_GOALS = 8;
const MAX_GO_TO_MARKET = 6;
// The main task always travels under this key, saved or not, so findings
// about it stay attached across saves.
const MAIN_KEY = "main";

interface EditorTask {
  key: string;
  id: string | null;
  title: string;
}

interface Content {
  main: EditorTask;
  why: string;
  subGoals: EditorTask[];
  goToMarket: EditorTask[];
}

function blank(): EditorTask {
  return { key: crypto.randomUUID(), id: null, title: "" };
}

function fromPlan(plan: PlanResponse | null): Content {
  if (!plan) {
    return {
      main: { key: MAIN_KEY, id: null, title: "" },
      why: "",
      subGoals: [blank()],
      goToMarket: [blank()],
    };
  }
  const main = plan.tasks.find((task) => task.kind === "main");
  const rows = (kind: PlanTaskResponse["kind"]) =>
    plan.tasks
      .filter((task) => task.kind === kind)
      .map((task) => ({ key: task.id, id: task.id, title: task.title }));
  return {
    main: { key: MAIN_KEY, id: main?.id ?? null, title: main?.title ?? "" },
    why: plan.why_it_matters ?? "",
    subGoals: rows("sub_goal"),
    goToMarket: rows("go_to_market"),
  };
}

function fromDraft(draft: PlanDraftResponse, current: Content): Content {
  const rows = (titles: string[]) =>
    titles.map((title) => ({ key: crypto.randomUUID(), id: null, title }));
  return {
    main: { ...current.main, title: draft.main_task },
    why: draft.why_it_matters,
    subGoals: rows(draft.sub_goals),
    goToMarket: rows(draft.go_to_market),
  };
}

// After a save the server has assigned ids. Keep each row's editor key (so
// open findings stay attached) and take the saved id and title by position.
function mergeSaved(content: Content, saved: PlanResponse): Content {
  const savedRows = (kind: PlanTaskResponse["kind"]) =>
    saved.tasks.filter((task) => task.kind === kind);
  const merge = (rows: EditorTask[], kind: PlanTaskResponse["kind"]) => {
    const persisted = savedRows(kind);
    return rows
      .filter((row) => row.title.trim())
      .map((row, index) => ({
        ...row,
        id: persisted[index]?.id ?? row.id,
        title: persisted[index]?.title ?? row.title,
      }));
  };
  const main = savedRows("main")[0];
  return {
    main: {
      key: MAIN_KEY,
      id: main?.id ?? null,
      title: main?.title ?? content.main.title,
    },
    why: saved.why_it_matters ?? "",
    subGoals: merge(content.subGoals, "sub_goal"),
    goToMarket: merge(content.goToMarket, "go_to_market"),
  };
}

function signature(content: Content): string {
  const titles = (rows: EditorTask[]) =>
    rows.map((row) => row.title.trim()).filter(Boolean);
  return JSON.stringify([
    content.main.title.trim(),
    content.why.trim(),
    titles(content.subGoals),
    titles(content.goToMarket),
  ]);
}

function toRequest(content: Content): PlanContentRequest {
  const rows = (list: EditorTask[]) =>
    list
      .filter((row) => row.title.trim())
      .map((row) => ({ id: row.id, title: row.title.trim() }));
  return {
    main_task: content.main.title.trim(),
    why_it_matters: content.why.trim() || null,
    sub_goals: rows(content.subGoals),
    go_to_market: rows(content.goToMarket),
  };
}

function reviewTasks(content: Content): ReviewTaskRequest[] {
  const rows = (list: EditorTask[], kind: ReviewTaskRequest["kind"]) =>
    list
      .filter((row) => row.title.trim())
      .map((row) => ({ key: row.key, kind, title: row.title.trim() }));
  return [
    { key: MAIN_KEY, kind: "main", title: content.main.title.trim() },
    ...rows(content.subGoals, "sub_goal"),
    ...rows(content.goToMarket, "go_to_market"),
  ];
}

interface ReviewState {
  data: PlanReviewResponse;
  findings: Finding[];
  signature: string;
}

export function PlanEditor({
  orgId,
  weekStart,
  plan,
  reviewers,
  startFromNotes = false,
}: {
  orgId: string;
  weekStart: string;
  plan: PlanResponse | null;
  reviewers: UserSummary[];
  startFromNotes?: boolean;
}) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState<Content>(() => fromPlan(plan));
  const [baseline, setBaseline] = useState(() => signature(fromPlan(plan)));
  const [review, setReview] = useState<ReviewState | null>(null);
  const [handled, setHandled] = useState<Record<string, true>>({});
  const [draftNotes, setDraftNotes] = useState<PlanDraftResponse | null>(null);
  const [brainDumpOpen, setBrainDumpOpen] = useState(startFromNotes);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mainError, setMainError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const create = usePlanCreate();
  const update = usePlanUpdate();
  const submitPlan = usePlanSubmit();
  const deletePlan = usePlanDelete();
  const aiReview = useAiPlanReview();

  const dirty = signature(content) !== baseline;
  const saving = create.isPending || update.isPending;
  const submitting = submitPlan.isPending;
  const hasContent = signature(content) !== signature(fromPlan(null));

  // Unsaved edits survive a mis-click on the browser's close button.
  useEffect(() => {
    if (!dirty) {
      return undefined;
    }
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const cacheWeek = (next: PlanResponse | null) => {
    queryClient.setQueryData<MyWeekResponse>(
      getMyWeekGetQueryKey(orgId, weekStart),
      (old) => (old ? { ...old, plan: next } : old)
    );
    void queryClient.invalidateQueries({
      queryKey: getMyPlanListQueryKey(orgId),
    });
  };

  const update_ = (change: (current: Content) => Content) => {
    setContent((current) => change(current));
    setSaveError(null);
  };

  async function save(): Promise<PlanResponse | null> {
    setSaveError(null);
    if (!content.main.title.trim()) {
      setMainError("Write the one thing you'll ship this week.");
      return null;
    }
    const body = toRequest(content);
    try {
      const saved = plan
        ? await update.mutateAsync({
            organizationId: orgId,
            planId: plan.id,
            data: body,
          })
        : await create.mutateAsync({
            organizationId: orgId,
            data: { ...body, week_start: weekStart },
          });
      const merged = mergeSaved(content, saved);
      setContent(merged);
      setBaseline(signature(merged));
      cacheWeek(saved);
      return saved;
    } catch (error) {
      setSaveError(
        getApiErrorMessage(error, "Couldn't save your plan. Try again.")
      );
      return null;
    }
  }

  async function submit() {
    const saved = plan && !dirty ? plan : await save();
    if (!saved) {
      return;
    }
    try {
      const submitted = await submitPlan.mutateAsync({
        organizationId: orgId,
        planId: saved.id,
      });
      cacheWeek(submitted);
      toast.success("Plan submitted for approval");
    } catch (error) {
      setSaveError(
        getApiErrorMessage(error, "Couldn't submit your plan. Try again.")
      );
    }
  }

  function runReview() {
    if (!content.main.title.trim()) {
      setMainError("Write your main task first, then ask for a review.");
      return;
    }
    const reviewedSignature = signature(content);
    aiReview.mutate(
      {
        organizationId: orgId,
        data: {
          week_start: weekStart,
          why_it_matters: content.why.trim() || null,
          tasks: reviewTasks(content),
        },
      },
      {
        onSuccess: (data) => {
          setReview({
            data,
            findings: withIds(data),
            signature: reviewedSignature,
          });
          setHandled({});
        },
      }
    );
  }

  function apply(finding: Finding) {
    const text = finding.suggested_rewrite;
    update_((current) => {
      if (finding.action === "set_why") {
        return { ...current, why: text };
      }
      if (finding.action === "add_go_to_market") {
        const empty = current.goToMarket.findIndex((row) => !row.title.trim());
        if (empty >= 0) {
          return {
            ...current,
            goToMarket: current.goToMarket.map((row, index) =>
              index === empty ? { ...row, title: text } : row
            ),
          };
        }
        if (current.goToMarket.length >= MAX_GO_TO_MARKET) {
          return current;
        }
        return {
          ...current,
          goToMarket: [...current.goToMarket, { ...blank(), title: text }],
        };
      }
      if (finding.task_key === MAIN_KEY) {
        return { ...current, main: { ...current.main, title: text } };
      }
      const swap = (rows: EditorTask[]) =>
        rows.map((row) =>
          row.key === finding.task_key ? { ...row, title: text } : row
        );
      return {
        ...current,
        subGoals: swap(current.subGoals),
        goToMarket: swap(current.goToMarket),
      };
    });
    setHandled((current) => ({ ...current, [finding.id]: true }));
  }

  function dismiss(finding: Finding) {
    setHandled((current) => ({ ...current, [finding.id]: true }));
  }

  function onDraft(draft: PlanDraftResponse) {
    update_((current) => fromDraft(draft, current));
    setReview(null);
    setHandled({});
    setMainError(null);
    setDraftNotes(
      draft.left_out.length || draft.open_questions.length ? draft : null
    );
    toast.success("Draft ready. Edit it, then save.");
  }

  const open = (review?.findings ?? []).filter(
    (finding) => !handled[finding.id]
  );
  const rowKeys = new Set([
    MAIN_KEY,
    ...content.subGoals.map((row) => row.key),
    ...content.goToMarket.map((row) => row.key),
  ]);
  const forTask = (key: string) =>
    open.filter((f) => f.action === "replace_title" && f.task_key === key);
  const whyFindings = open.filter((f) => f.action === "set_why");
  const goToMarketFindings = open.filter(
    (f) => f.action === "add_go_to_market"
  );
  // A finding about a row the member has since deleted.
  const orphaned = open.filter(
    (f) =>
      f.action === "replace_title" &&
      f.task_key !== null &&
      !rowKeys.has(f.task_key)
  );
  const findingCards = (findings: Finding[]) =>
    findings.map((finding) => (
      <FindingCard
        key={finding.id}
        finding={finding}
        onApply={() => apply(finding)}
        onDismiss={() => dismiss(finding)}
      />
    ));

  const returned = plan?.review_decision === "returned";

  return (
    <div className="space-y-4">
      {returned && plan?.review_comment && (
        <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm dark:border-amber-900 dark:bg-amber-950/40">
          <MessageSquareWarning className="mt-0.5 size-5 shrink-0 text-amber-700 dark:text-amber-400" />
          <div>
            <p className="font-medium text-amber-950 dark:text-amber-100">
              {plan.reviewed_by ? fullName(plan.reviewed_by) : "Your lead"} sent
              this plan back
            </p>
            <p className="mt-0.5 text-amber-900 dark:text-amber-200">
              &ldquo;{plan.review_comment}&rdquo;
            </p>
          </div>
        </div>
      )}

      {draftNotes && (
        <div className="rounded-xl border bg-background p-4 text-sm">
          <div className="flex items-start justify-between gap-3">
            <p className="flex items-center gap-2 font-medium">
              <Lightbulb className="size-4 text-amber-500" /> From your notes
            </p>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="Dismiss"
              onClick={() => setDraftNotes(null)}
            >
              <X />
            </Button>
          </div>
          {draftNotes.open_questions.length > 0 && (
            <div className="mt-2">
              <p className="text-muted-foreground">
                Worth answering before you submit:
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {draftNotes.open_questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </div>
          )}
          {draftNotes.left_out.length > 0 && (
            <div className="mt-2">
              <p className="text-muted-foreground">Left out of this week:</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {draftNotes.left_out.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <section className="rounded-xl border bg-background">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2">
            <h2 className="font-medium">
              Plan for {describeWeek(weekStart).toLowerCase()}
            </h2>
            <StatusBadge status="draft" returned={returned} />
            {dirty && (
              <span className="text-xs text-muted-foreground">
                Unsaved changes
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setBrainDumpOpen(true)}
            >
              <Wand2 className="size-3.5" />
              Draft from notes
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={runReview}
              disabled={aiReview.isPending}
            >
              {aiReview.isPending ? (
                <Spinner />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              {aiReview.isPending ? "Reviewing…" : "Review with AI"}
            </Button>
          </div>
        </div>

        <div className="space-y-7 p-4 sm:p-5">
          {aiReview.isPending && <ReviewingNotice />}
          {!aiReview.isPending && aiReview.isError && (
            <AiErrorAlert
              error={aiReview.error}
              onDismiss={() => aiReview.reset()}
            />
          )}
          {!aiReview.isPending && review && (
            <ReviewSummary
              review={review.data}
              open={open.length}
              stale={signature(content) !== review.signature}
              onReviewAgain={runReview}
              reviewing={aiReview.isPending}
            />
          )}
          {orphaned.length > 0 && (
            <div className="space-y-2">{findingCards(orphaned)}</div>
          )}

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Main task</legend>
            <p className="text-sm text-muted-foreground">
              The one significant thing you&apos;ll ship by Friday, written as a
              result someone can check.
            </p>
            <Input
              className={cn(
                "h-11 text-base",
                mainError && "border-destructive"
              )}
              maxLength={200}
              placeholder="e.g. Checkout handles expired cards, confirmed on staging"
              value={content.main.title}
              aria-invalid={mainError ? true : undefined}
              onChange={(event) => {
                setMainError(null);
                const title = event.target.value;
                update_((current) => ({
                  ...current,
                  main: { ...current.main, title },
                }));
              }}
            />
            {mainError && (
              <p className="text-sm text-destructive">{mainError}</p>
            )}
            {findingCards(forTask(MAIN_KEY))}
            <label
              className="block pt-2 text-sm font-medium"
              htmlFor="why-it-matters"
            >
              Why it matters
            </label>
            <Textarea
              id="why-it-matters"
              rows={2}
              maxLength={1000}
              placeholder="e.g. Expired cards are our top cause of failed renewals."
              value={content.why}
              onChange={(event) => {
                const why = event.target.value;
                update_((current) => ({ ...current, why }));
              }}
            />
            {findingCards(whyFindings)}
          </fieldset>

          <TaskList
            legend="Sub-goals"
            hint="Smaller results that get the main task over the line."
            placeholder="e.g. Retry schedule covered by integration tests"
            addLabel="Add sub-goal"
            rows={content.subGoals}
            max={MAX_SUB_GOALS}
            onChange={(subGoals) =>
              update_((current) => ({ ...current, subGoals }))
            }
            findingsFor={(key) => findingCards(forTask(key))}
          />

          <TaskList
            legend="Go-to-market goals"
            hint="How users will hear about it: a changelog entry, an announcement, analytics, onboarding, docs or a flag rollout."
            placeholder="e.g. Changelog entry announcing card retries"
            addLabel="Add go-to-market goal"
            rows={content.goToMarket}
            max={MAX_GO_TO_MARKET}
            onChange={(goToMarket) =>
              update_((current) => ({ ...current, goToMarket }))
            }
            findingsFor={(key) => findingCards(forTask(key))}
            before={
              goToMarketFindings.length > 0
                ? findingCards(goToMarketFindings)
                : null
            }
          />
        </div>

        <div className="space-y-3 border-t px-4 py-3 sm:px-5">
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              {saveError}
            </p>
          )}
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <ReviewerNote reviewers={reviewers} />
            <div className="flex flex-wrap justify-end gap-2">
              {plan && (
                <Button
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="size-4" />
                  Delete draft
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() =>
                  void save().then(
                    (saved) => saved && toast.success("Draft saved")
                  )
                }
                disabled={
                  saving ||
                  submitting ||
                  (!dirty && plan !== null) ||
                  !hasContent
                }
              >
                {saving ? <Spinner /> : <Save className="size-4" />}
                Save draft
              </Button>
              <Button
                onClick={() => void submit()}
                disabled={saving || submitting}
              >
                {submitting ? <Spinner /> : <Send className="size-4" />}
                Submit for approval
              </Button>
            </div>
          </div>
        </div>
      </section>

      <BrainDumpDialog
        open={brainDumpOpen}
        onOpenChange={setBrainDumpOpen}
        orgId={orgId}
        weekStart={weekStart}
        replacing={hasContent}
        onDraft={onDraft}
      />

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this draft?</AlertDialogTitle>
            <AlertDialogDescription>
              Your plan for {describeWeek(weekStart).toLowerCase()} will be
              removed. You can start a new one any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletePlan.isPending}>
              Keep it
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deletePlan.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (!plan) {
                  return;
                }
                deletePlan.mutate(
                  { organizationId: orgId, planId: plan.id },
                  {
                    onSuccess: () => {
                      setConfirmDelete(false);
                      cacheWeek(null);
                      toast.success("Draft deleted");
                    },
                    onError: (error) =>
                      toast.error(
                        getApiErrorMessage(error, "Couldn't delete the draft.")
                      ),
                  }
                );
              }}
            >
              {deletePlan.isPending ? "Deleting…" : "Delete draft"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function TaskList({
  legend,
  hint,
  placeholder,
  addLabel,
  rows,
  max,
  onChange,
  findingsFor,
  before,
}: {
  legend: string;
  hint: string;
  placeholder: string;
  addLabel: string;
  rows: EditorTask[];
  max: number;
  onChange: (rows: EditorTask[]) => void;
  findingsFor: (key: string) => React.ReactNode;
  before?: React.ReactNode;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{legend}</legend>
      <p className="text-sm text-muted-foreground">{hint}</p>
      {before}
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={row.key} className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                maxLength={200}
                placeholder={index === 0 ? placeholder : undefined}
                value={row.title}
                aria-label={`${legend} ${index + 1}`}
                onChange={(event) =>
                  onChange(
                    rows.map((candidate) =>
                      candidate.key === row.key
                        ? { ...candidate, title: event.target.value }
                        : candidate
                    )
                  )
                }
              />
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${legend.toLowerCase()} ${index + 1}`}
                onClick={() =>
                  onChange(
                    rows.filter((candidate) => candidate.key !== row.key)
                  )
                }
              >
                <X />
              </Button>
            </div>
            {findingsFor(row.key)}
          </div>
        ))}
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="text-muted-foreground"
        disabled={rows.length >= max}
        onClick={() => onChange([...rows, blank()])}
      >
        <Plus className="size-3.5" />
        {rows.length >= max ? `Up to ${max}` : addLabel}
      </Button>
    </fieldset>
  );
}

function ReviewerNote({ reviewers }: { reviewers: UserSummary[] }) {
  if (reviewers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No team lead can approve this yet. Ask an admin to add you to a team
        with a lead.
      </p>
    );
  }
  const names = reviewers.map(fullName);
  return (
    <p className="text-sm text-muted-foreground">
      {names.length === 1
        ? `${names[0]} reviews your plan.`
        : `Reviewed by a lead of your teams: ${names.join(", ")}.`}
    </p>
  );
}
