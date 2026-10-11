import { Link, createFileRoute, useRouter } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { usePlanGet } from "@/api/endpoints/plans/plans";
import { PlanView } from "@/components/plans/plan-view";
import { ErrorState, NotFoundState, PageSkeleton } from "@/components/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { useCurrentUser } from "@/contexts/user-context";
import { useOrg } from "@/contexts/org-context";
import { getApiErrorStatus } from "@/lib/api-error";

// A single plan: where a lead approves or sends it back, and where teammates
// read each other's plans. Drafts stay private to their author; anything the
// caller may not see comes back as "not found".
export const Route = createFileRoute("/_main/orgs/$orgId/plans/$planId")({
  head: () => ({ meta: [{ title: "Plan · PlanStride" }] }),
  component: PlanPage,
});

function PlanPage() {
  const { orgId } = useOrg();
  const { planId } = Route.useParams();
  const router = useRouter();
  const user = useCurrentUser();
  const {
    data: plan,
    error,
    isLoading,
    refetch,
  } = usePlanGet(orgId, planId, {
    query: { retry: false },
  });

  if (isLoading) {
    return <PageSkeleton />;
  }
  if (!plan) {
    return getApiErrorStatus(error) === 404 ? (
      <NotFoundState
        title="Plan not found"
        description="It doesn't exist, it's still a draft, or it belongs to someone you don't share a team with."
      />
    ) : (
      <ErrorState onRetry={() => void refetch()} />
    );
  }

  const mine = plan.author.id === user?.id;
  if (mine && plan.status === "draft") {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          This plan is still a draft.
        </p>
        <Link
          to="/orgs/$orgId/week"
          params={{ orgId }}
          search={{ week: plan.week_start }}
          className={buttonVariants()}
        >
          Continue editing
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-2 text-muted-foreground"
        onClick={() => router.history.back()}
      >
        <ArrowLeft className="size-4" /> Back
      </Button>
      <PlanView orgId={orgId} plan={plan} showAuthor={!mine} />
    </div>
  );
}
