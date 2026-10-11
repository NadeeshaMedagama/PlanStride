import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, EyeOff, PauseCircle, PlayCircle } from "lucide-react";
import {
  getOrganizationGetQueryKey,
  getOrganizationListQueryKey,
  useOrganizationGet,
  useOrganizationReinstate,
  useOrganizationSuspend,
} from "@/api/endpoints/organizations/organizations";
import { getOverviewGetQueryKey } from "@/api/endpoints/overview/overview";
import type { InternalOrganizationDetailResponse } from "@/api/model";
import { OrganizationStatus } from "@/components/organizations/organization-status";
import { PageTitle, SectionHeading, StatTile } from "@/components/stat-tile";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  formatAgo,
  formatCount,
  formatDate,
  formatPercent,
  fullName,
} from "@/lib/format";

export const Route = createFileRoute("/_main/organizations/$organizationId")({
  head: () => ({ meta: [{ title: "Organization · PlanStride Internal" }] }),
  component: OrganizationPage,
});

function OrganizationPage() {
  const { organizationId } = Route.useParams();
  const [suspending, setSuspending] = useState(false);
  const queryClient = useQueryClient();
  const {
    data: organization,
    isLoading,
    isError,
  } = useOrganizationGet(organizationId, {
    query: { retry: false },
  });

  const refresh = (updated: InternalOrganizationDetailResponse) => {
    queryClient.setQueryData(
      getOrganizationGetQueryKey(organizationId),
      updated
    );
    void queryClient.invalidateQueries({
      queryKey: getOrganizationListQueryKey(),
    });
    void queryClient.invalidateQueries({ queryKey: getOverviewGetQueryKey() });
  };
  const reinstate = useOrganizationReinstate({
    mutation: {
      onSuccess: (updated) => {
        refresh(updated);
        toast.success(`${updated.name} reinstated. Members can sign in again.`);
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't reinstate it.")),
    },
  });

  if (isLoading) {
    return <Skeleton className="h-96 w-full rounded-xl" />;
  }
  if (isError || !organization) {
    return (
      <div className="space-y-4">
        <BackLink />
        <p className="text-sm text-muted-foreground">Organization not found.</p>
      </div>
    );
  }

  const { plans_by_status: plans, ai_usage_30d: ai } = organization;

  return (
    <>
      <BackLink />
      <PageTitle
        title={
          <span className="flex flex-wrap items-center gap-3">
            {organization.name}
            <OrganizationStatus suspendedAt={organization.suspended_at} />
          </span>
        }
        description={`Customer since ${formatDate(organization.created_at)} · last active ${formatAgo(organization.last_active_at)}`}
      >
        {organization.suspended_at ? (
          <Button
            disabled={reinstate.isPending}
            onClick={() => reinstate.mutate({ organizationId })}
          >
            <PlayCircle className="size-4" />
            Reinstate
          </Button>
        ) : (
          <Button variant="destructive" onClick={() => setSuspending(true)}>
            <PauseCircle className="size-4" />
            Suspend
          </Button>
        )}
      </PageTitle>

      {organization.suspended_at && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          <p className="font-medium">
            Suspended {formatDate(organization.suspended_at)}. Every member is
            locked out of this organization until it&apos;s reinstated.
          </p>
          {organization.suspension_reason && (
            <p className="mt-1">
              Reason (internal): {organization.suspension_reason}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Members" value={organization.member_count} />
        <StatTile label="Teams" value={organization.team_count} />
        <StatTile
          label="Plans"
          value={organization.plan_count}
          note={`${plans.submitted} awaiting approval · ${plans.approved} approved · ${plans.done} closed · ${plans.draft} drafts`}
        />
        <StatTile
          label="AI calls, 30 days"
          value={formatCount(ai.calls)}
          note={
            ai.calls
              ? `${formatPercent(ai.failed + ai.rate_limited, ai.calls)} failed or rate limited · ${formatCount(ai.input_tokens + ai.output_tokens)} tokens`
              : "No calls"
          }
          tone={ai.failed + ai.rate_limited > 0 ? "warning" : "default"}
        />
      </div>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <EyeOff className="size-3.5" />
        Plans are counted, not shown: staff have no access to what customers
        write in them.
      </p>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <section className="space-y-3">
          <SectionHeading title="Members" />
          <ul className="divide-y rounded-xl border bg-background">
            {organization.members.map((member) => (
              <li
                key={member.user.id}
                className="flex items-center gap-3 px-4 py-3 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {fullName(member.user)}
                    {!member.is_active && (
                      <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                        Deactivated
                      </span>
                    )}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {member.user.email}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground capitalize">
                  {member.role}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section className="space-y-3">
          <SectionHeading title="Teams" />
          <ul className="divide-y rounded-xl border bg-background">
            {organization.teams.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-muted-foreground">
                No teams yet.
              </li>
            )}
            {organization.teams.map((team) => (
              <li key={team.id} className="px-4 py-3 text-sm">
                <p className="font-medium">{team.name}</p>
                <p className="text-xs text-muted-foreground">
                  {team.member_count} members · lead{" "}
                  {team.lead ? fullName(team.lead) : "none"}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <SuspendDialog
        organization={organization}
        open={suspending}
        onOpenChange={setSuspending}
        onSuspended={refresh}
      />
    </>
  );
}

function BackLink() {
  return (
    <Link
      to="/organizations"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" /> Organizations
    </Link>
  );
}

function SuspendDialog({
  organization,
  open,
  onOpenChange,
  onSuspended,
}: {
  organization: InternalOrganizationDetailResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuspended: (organization: InternalOrganizationDetailResponse) => void;
}) {
  const [reason, setReason] = useState("");
  const suspend = useOrganizationSuspend({
    mutation: {
      onSuccess: (updated) => {
        onSuspended(updated);
        onOpenChange(false);
        setReason("");
        toast.success(`${updated.name} suspended`);
      },
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Suspend {organization.name}?</DialogTitle>
          <DialogDescription>
            All {organization.member_count} members lose access to this
            organization straight away. Nothing is deleted, and you can
            reinstate it at any time.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <label htmlFor="suspend-reason" className="text-sm font-medium">
            Reason{" "}
            <span className="text-muted-foreground">(internal, optional)</span>
          </label>
          <Textarea
            id="suspend-reason"
            rows={3}
            maxLength={500}
            placeholder="e.g. Chargeback dispute on the last invoice"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        {suspend.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getApiErrorMessage(suspend.error, "Couldn't suspend it.")}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={suspend.isPending}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={suspend.isPending}
            onClick={() =>
              suspend.mutate({
                organizationId: organization.id,
                data: { reason: reason.trim() || null },
              })
            }
          >
            {suspend.isPending ? "Suspending…" : "Suspend organization"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
