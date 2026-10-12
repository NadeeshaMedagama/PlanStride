import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { MoreHorizontal, Star, UserPlus } from "lucide-react";
import { useMemberList } from "@/api/endpoints/members/members";
import {
  getTeamGetQueryKey,
  getTeamListQueryKey,
  useTeamMemberAdd,
  useTeamMemberRemove,
  useTeamUpdate,
} from "@/api/endpoints/teams/teams";
import type { TeamDetailResponse, UserSummary } from "@/api/model";
import { Avatar } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { getApiErrorMessage } from "@/lib/api-error";
import { fullName } from "@/lib/utils";

export function TeamMembers({
  orgId,
  team,
  canManage,
}: {
  orgId: string;
  team: TeamDetailResponse;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: orgMembers } = useMemberList(orgId, {
    query: { enabled: canManage },
  });
  const [adding, setAdding] = useState("");

  const refresh = (updated: TeamDetailResponse) => {
    queryClient.setQueryData(getTeamGetQueryKey(orgId, team.id), updated);
    void queryClient.invalidateQueries({
      queryKey: getTeamListQueryKey(orgId),
    });
    void queryClient.invalidateQueries({
      predicate: (query) =>
        typeof query.queryKey[0] === "string" &&
        query.queryKey[0].startsWith(
          `/organizations/${orgId}/teams/${team.id}/`
        ),
    });
  };
  const fail = (fallback: string) => (error: unknown) =>
    toast.error(getApiErrorMessage(error, fallback));

  const add = useTeamMemberAdd({
    mutation: {
      onSuccess: (updated) => {
        refresh(updated);
        setAdding("");
      },
      onError: fail("Couldn't add them to the team."),
    },
  });
  const remove = useTeamMemberRemove({
    mutation: {
      onSuccess: refresh,
      onError: fail("Couldn't remove them from the team."),
    },
  });
  const setLead = useTeamUpdate({
    mutation: {
      onSuccess: (updated) => {
        refresh(updated);
        toast.success(
          updated.lead
            ? `${fullName(updated.lead)} now leads ${updated.name}`
            : "Lead removed"
        );
      },
      onError: fail("Couldn't change the lead."),
    },
  });

  const onTeam = new Set(team.members.map((member) => member.id));
  const candidates = (orgMembers ?? []).filter(
    (member) => !onTeam.has(member.user.id)
  );

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex flex-col gap-2 rounded-xl border bg-background p-4 sm:flex-row sm:items-center">
          <NativeSelect
            className="w-full sm:flex-1"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
            aria-label="Add a member to this team"
          >
            <NativeSelectOption value="">
              {candidates.length
                ? "Add someone to the team…"
                : "Everyone is already on this team"}
            </NativeSelectOption>
            {candidates.map((member) => (
              <NativeSelectOption key={member.user.id} value={member.user.id}>
                {fullName(member.user)}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <Button
            disabled={!adding || add.isPending}
            onClick={() =>
              add.mutate({
                organizationId: orgId,
                teamId: team.id,
                userId: adding,
              })
            }
          >
            <UserPlus className="size-4" />
            Add to team
          </Button>
        </div>
      )}

      <ul className="divide-y rounded-xl border bg-background">
        {team.members.length === 0 && (
          <li className="px-5 py-8 text-center text-sm text-muted-foreground">
            Nobody is on this team yet.
          </li>
        )}
        {team.members.map((member) => (
          <MemberItem
            key={member.id}
            member={member}
            isLead={team.lead?.id === member.id}
            canManage={canManage}
            busy={remove.isPending || setLead.isPending}
            onMakeLead={() =>
              setLead.mutate({
                organizationId: orgId,
                teamId: team.id,
                data: { lead_user_id: member.id },
              })
            }
            onClearLead={() =>
              setLead.mutate({
                organizationId: orgId,
                teamId: team.id,
                data: { lead_user_id: null },
              })
            }
            onRemove={() =>
              remove.mutate({
                organizationId: orgId,
                teamId: team.id,
                userId: member.id,
              })
            }
          />
        ))}
      </ul>
    </div>
  );
}

function MemberItem({
  member,
  isLead,
  canManage,
  busy,
  onMakeLead,
  onClearLead,
  onRemove,
}: {
  member: UserSummary;
  isLead: boolean;
  canManage: boolean;
  busy: boolean;
  onMakeLead: () => void;
  onClearLead: () => void;
  onRemove: () => void;
}) {
  return (
    <li className="flex items-center gap-3 px-4 py-3 sm:px-5">
      <Avatar
        firstName={member.first_name}
        lastName={member.last_name}
        className="size-8"
      />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          {fullName(member)}
          {isLead && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-200">
              <Star className="size-3" /> Lead
            </span>
          )}
        </p>
        <p className="truncate text-xs text-muted-foreground">{member.email}</p>
      </div>
      {canManage && (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Manage ${fullName(member)}`}
              />
            }
            disabled={busy}
          >
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {isLead ? (
              <DropdownMenuItem onClick={onClearLead}>
                Remove as lead
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onClick={onMakeLead}>
                Make team lead
              </DropdownMenuItem>
            )}
            <DropdownMenuItem variant="destructive" onClick={onRemove}>
              Remove from team
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </li>
  );
}
