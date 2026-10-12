import { useState } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus, Star, Users } from "lucide-react";
import { useTeamList } from "@/api/endpoints/teams/teams";
import {
  ErrorState,
  PageHeader,
  PageSkeleton,
  StateMessage,
} from "@/components/states";
import { TeamFormDialog } from "@/components/teams/team-form-dialog";
import { Button } from "@/components/ui/button";
import { useOrg } from "@/contexts/org-context";
import { fullName } from "@/lib/utils";

export const Route = createFileRoute("/_main/orgs/$orgId/teams/")({
  head: () => ({ meta: [{ title: "Teams · PlanStride" }] }),
  component: TeamsPage,
});

function TeamsPage() {
  const { orgId, isManager } = useOrg();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const { data: teams, isLoading, isError, refetch } = useTeamList(orgId);

  return (
    <>
      <PageHeader
        title="Teams"
        description="Each team has a lead who approves its members' plans."
      >
        {isManager && (
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            New team
          </Button>
        )}
      </PageHeader>

      {isLoading && <PageSkeleton />}
      {isError && <ErrorState onRetry={() => void refetch()} />}
      {teams && teams.length === 0 && (
        <StateMessage
          icon={Users}
          title="No teams yet"
          description={
            isManager
              ? "Create a team and give it a lead, so plans have someone to approve them."
              : "An owner or admin of your organization sets up teams."
          }
        >
          {isManager && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              Create the first team
            </Button>
          )}
        </StateMessage>
      )}
      {teams && teams.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {teams.map((team) => (
            <Link
              key={team.id}
              to="/orgs/$orgId/teams/$teamId"
              params={{ orgId, teamId: team.id }}
              className="group rounded-xl border bg-background p-5 transition-colors hover:border-primary/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold group-hover:text-primary">
                    {team.name}
                  </h2>
                  {team.description && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {team.description}
                    </p>
                  )}
                </div>
                {team.is_lead ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    <Star className="size-3" /> You lead
                  </span>
                ) : (
                  team.is_member && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      Your team
                    </span>
                  )
                )}
              </div>
              <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
                <span>
                  {team.member_count}{" "}
                  {team.member_count === 1 ? "member" : "members"}
                </span>
                <span>
                  Lead: {team.lead ? fullName(team.lead) : "none yet"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <TeamFormDialog
        orgId={orgId}
        open={creating}
        onOpenChange={setCreating}
        onSaved={(team) =>
          navigate({
            to: "/orgs/$orgId/teams/$teamId",
            params: { orgId, teamId: team.id },
          })
        }
      />
    </>
  );
}
