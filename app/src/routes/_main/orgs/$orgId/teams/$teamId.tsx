import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Lock, Pencil, Trash2 } from "lucide-react";
import {
  getTeamListQueryKey,
  useTeamDelete,
  useTeamGet,
} from "@/api/endpoints/teams/teams";
import { WeekSwitcher } from "@/components/plans/week-switcher";
import {
  ErrorState,
  NotFoundState,
  PageHeader,
  PageSkeleton,
  StateMessage,
} from "@/components/states";
import { TeamFormDialog } from "@/components/teams/team-form-dialog";
import { TeamHistory } from "@/components/teams/team-history";
import { TeamMembers } from "@/components/teams/team-members";
import { TeamWeek } from "@/components/teams/team-week";
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
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useOrg } from "@/contexts/org-context";
import { getApiErrorMessage, getApiErrorStatus } from "@/lib/api-error";
import { currentWeekStart, isMonday } from "@/lib/week";
import { fullName } from "@/lib/utils";

type Tab = "week" | "history" | "members";

export const Route = createFileRoute("/_main/orgs/$orgId/teams/$teamId")({
  validateSearch: (
    search: Record<string, unknown>
  ): { tab?: Tab; week?: string } => {
    const tab = search["tab"];
    const week = search["week"];
    return {
      tab: tab === "history" || tab === "members" ? tab : undefined,
      week: typeof week === "string" && isMonday(week) ? week : undefined,
    };
  },
  head: () => ({ meta: [{ title: "Team · PlanStride" }] }),
  component: TeamPage,
});

function TeamPage() {
  const { orgId, isManager } = useOrg();
  const { teamId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const goTo = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const tab: Tab = search.tab ?? "week";
  const week = search.week ?? currentWeekStart();

  const {
    data: team,
    error,
    isLoading,
    refetch,
  } = useTeamGet(orgId, teamId, {
    query: { retry: false },
  });
  const remove = useTeamDelete({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: getTeamListQueryKey(orgId),
        });
        toast.success("Team deleted");
        goTo({ to: "/orgs/$orgId/teams", params: { orgId } });
      },
      onError: (err) =>
        toast.error(getApiErrorMessage(err, "Couldn't delete the team.")),
    },
  });

  if (isLoading) {
    return <PageSkeleton />;
  }
  if (!team) {
    return getApiErrorStatus(error) === 404 ? (
      <NotFoundState title="Team not found" />
    ) : (
      <ErrorState onRetry={() => void refetch()} />
    );
  }

  const setSearch = (next: { tab?: Tab; week?: string }) =>
    navigate({
      search: (current) => {
        const merged = { ...current, ...next };
        return {
          tab: merged.tab === "week" ? undefined : merged.tab,
          week: merged.week === currentWeekStart() ? undefined : merged.week,
        };
      },
    });

  return (
    <>
      <PageHeader
        title={team.name}
        description={
          <>
            {team.description ? `${team.description} ` : ""}
            Lead: {team.lead ? fullName(team.lead) : "none yet"} ·{" "}
            {team.member_count} {team.member_count === 1 ? "member" : "members"}
          </>
        }
      >
        {isManager && (
          <>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="size-4" />
              Edit
            </Button>
            <Button variant="ghost" onClick={() => setDeleting(true)}>
              <Trash2 className="size-4" />
              Delete
            </Button>
          </>
        )}
      </PageHeader>

      <Tabs
        value={tab}
        onValueChange={(value) => setSearch({ tab: value as Tab })}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <TabsList>
            <TabsTrigger value="week">The week</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
            <TabsTrigger value="members">Members</TabsTrigger>
          </TabsList>
          {tab === "week" && team.can_view_week && (
            <WeekSwitcher
              week={week}
              onChange={(next) => setSearch({ week: next })}
            />
          )}
        </div>
        <TabsContent value="week" className="pt-2">
          {team.can_view_week ? (
            <TeamWeek orgId={orgId} teamId={team.id} week={week} />
          ) : (
            <NotOnTeam />
          )}
        </TabsContent>
        <TabsContent value="history" className="pt-2">
          {team.can_view_week ? (
            <TeamHistory
              orgId={orgId}
              teamId={team.id}
              onPickWeek={(picked) => setSearch({ tab: "week", week: picked })}
            />
          ) : (
            <NotOnTeam />
          )}
        </TabsContent>
        <TabsContent value="members" className="pt-2">
          <TeamMembers orgId={orgId} team={team} canManage={isManager} />
        </TabsContent>
      </Tabs>

      <TeamFormDialog
        orgId={orgId}
        open={editing}
        onOpenChange={setEditing}
        team={team}
      />
      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {team.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              The team and its member list go away. Everyone&apos;s plans stay,
              and they keep their other teams.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              Keep it
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={(event) => {
                event.preventDefault();
                remove.mutate({ organizationId: orgId, teamId: team.id });
              }}
            >
              {remove.isPending ? "Deleting…" : "Delete team"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function NotOnTeam() {
  return (
    <StateMessage
      icon={Lock}
      title="This team's week is visible to its members"
      description="Plans are shared with the people you work with. Ask an admin to add you to the team if you need to see it."
    />
  );
}
