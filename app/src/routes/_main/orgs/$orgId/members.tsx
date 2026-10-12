import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserMinus, UserPlus } from "lucide-react";
import {
  getMemberListQueryKey,
  useMemberList,
  useMemberRemove,
  useMemberUpdate,
} from "@/api/endpoints/members/members";
import {
  getInvitationListQueryKey,
  useInvitationList,
  useInvitationRevoke,
} from "@/api/endpoints/invitations/invitations";
import { getOrganizationGetQueryKey } from "@/api/endpoints/organizations/organizations";
import type { MemberResponse, MemberUpdateRequestRole } from "@/api/model";
import { Avatar } from "@/components/app-shell";
import { InviteDialog } from "@/components/members/invite-dialog";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/states";
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
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { useCurrentUser } from "@/contexts/user-context";
import { useOrg } from "@/contexts/org-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/week";
import { cn, fullName } from "@/lib/utils";

export const Route = createFileRoute("/_main/orgs/$orgId/members")({
  head: () => ({ meta: [{ title: "Members · PlanStride" }] }),
  component: MembersPage,
});

const ROLE_LABEL: Record<MemberUpdateRequestRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};
const WITH_ARTICLE: Record<MemberUpdateRequestRole, string> = {
  owner: "an owner",
  admin: "an admin",
  member: "a member",
};

function MembersPage() {
  const { orgId, organization, isManager } = useOrg();
  const user = useCurrentUser();
  const queryClient = useQueryClient();
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<MemberResponse | null>(null);
  const { data: members, isLoading, isError, refetch } = useMemberList(orgId);

  const refreshMembers = () => {
    void queryClient.invalidateQueries({
      queryKey: getMemberListQueryKey(orgId),
    });
    void queryClient.invalidateQueries({
      queryKey: getOrganizationGetQueryKey(orgId),
    });
  };
  const changeRole = useMemberUpdate({
    mutation: {
      onSuccess: (member) => {
        refreshMembers();
        toast.success(
          `${fullName(member.user)} is now ${WITH_ARTICLE[member.role]}`
        );
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't change the role.")),
    },
  });
  const remove = useMemberRemove({
    mutation: {
      onSuccess: () => {
        refreshMembers();
        toast.success("Removed from the organization");
        setRemoving(null);
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't remove them.")),
    },
  });

  const viewerIsOwner = organization.role === "owner";
  const owners = (members ?? []).filter((member) => member.role === "owner");
  // Mirrors the API's rules so the UI only offers what will work: admins
  // can't touch owners or create new ones, and the last owner stays an owner.
  const canEdit = (member: MemberResponse) =>
    isManager &&
    (viewerIsOwner || member.role !== "owner") &&
    !(member.role === "owner" && owners.length === 1);

  return (
    <>
      <PageHeader
        title="Members"
        description={`${organization.member_count} people in ${organization.name}. Owners and admins manage members and teams; members plan their own weeks.`}
      >
        {isManager && (
          <Button onClick={() => setInviting(true)}>
            <UserPlus className="size-4" />
            Invite someone
          </Button>
        )}
      </PageHeader>

      {isLoading && <PageSkeleton />}
      {isError && <ErrorState onRetry={() => void refetch()} />}
      {members && (
        <ul className="divide-y rounded-xl border bg-background">
          {members.map((member) => (
            <li
              key={member.user.id}
              className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:px-5"
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <Avatar
                  firstName={member.user.first_name}
                  lastName={member.user.last_name}
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {fullName(member.user)}
                    {member.user.id === user?.id && (
                      <span className="font-normal text-muted-foreground">
                        {" "}
                        (you)
                      </span>
                    )}
                    {!member.is_active && (
                      <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                        Deactivated
                      </span>
                    )}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {member.user.email}
                    {member.teams.length > 0 &&
                      ` · ${member.teams.map((team) => team.name).join(", ")}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {canEdit(member) ? (
                  <NativeSelect
                    size="sm"
                    value={member.role}
                    disabled={changeRole.isPending}
                    aria-label={`Role for ${fullName(member.user)}`}
                    onChange={(event) =>
                      changeRole.mutate({
                        organizationId: orgId,
                        userId: member.user.id,
                        data: {
                          role: event.target.value as MemberUpdateRequestRole,
                        },
                      })
                    }
                  >
                    {viewerIsOwner && (
                      <NativeSelectOption value="owner">
                        Owner
                      </NativeSelectOption>
                    )}
                    <NativeSelectOption value="admin">Admin</NativeSelectOption>
                    <NativeSelectOption value="member">
                      Member
                    </NativeSelectOption>
                  </NativeSelect>
                ) : (
                  <RoleBadge role={member.role} />
                )}
                {canEdit(member) && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Remove ${fullName(member.user)}`}
                    onClick={() => setRemoving(member)}
                  >
                    <UserMinus />
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {isManager && <Invitations orgId={orgId} />}

      <InviteDialog orgId={orgId} open={inviting} onOpenChange={setInviting} />
      <AlertDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {removing ? fullName(removing.user) : ""} from{" "}
              {organization.name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              They lose access straight away and come off every team, including
              any they lead. Their past plans stay in the team history.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (removing) {
                  remove.mutate({
                    organizationId: orgId,
                    userId: removing.user.id,
                  });
                }
              }}
            >
              {remove.isPending ? "Removing…" : "Remove"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function RoleBadge({ role }: { role: MemberUpdateRequestRole }) {
  return (
    <span
      className={cn(
        "rounded-full px-2.5 py-0.5 text-xs font-medium",
        role === "owner"
          ? "bg-primary/10 text-primary"
          : role === "admin"
            ? "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200"
            : "bg-muted text-muted-foreground"
      )}
    >
      {ROLE_LABEL[role]}
    </span>
  );
}

function Invitations({ orgId }: { orgId: string }) {
  const queryClient = useQueryClient();
  const { data: invitations } = useInvitationList(orgId);
  const revoke = useInvitationRevoke({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getInvitationListQueryKey(orgId),
        });
        toast.success("Invite link revoked");
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't revoke the link.")),
    },
  });

  if (!invitations || invitations.length === 0) {
    return null;
  }
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">Invite links</h2>
      <ul className="divide-y rounded-xl border bg-background">
        {invitations.map((invitation) => (
          <li
            key={invitation.id}
            className="flex items-center gap-3 px-4 py-3 text-sm sm:px-5"
          >
            <div className="min-w-0 flex-1">
              <p>
                {invitation.role === "admin" ? "Admin" : "Member"} invite
                {invitation.created_by && (
                  <span className="text-muted-foreground">
                    {" "}
                    by {fullName(invitation.created_by)}
                  </span>
                )}
              </p>
              <p className="text-xs text-muted-foreground">
                {invitation.status === "accepted" && invitation.accepted_by
                  ? `Used by ${fullName(invitation.accepted_by)}`
                  : invitation.status === "pending"
                    ? `Expires ${formatDate(invitation.expires_at)}`
                    : `Created ${formatDate(invitation.created_at)}`}
              </p>
            </div>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                invitation.status === "pending"
                  ? "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200"
                  : invitation.status === "accepted"
                    ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
                    : "bg-muted text-muted-foreground"
              )}
            >
              {invitation.status}
            </span>
            {invitation.status === "pending" && (
              <Button
                variant="ghost"
                size="sm"
                disabled={revoke.isPending}
                onClick={() =>
                  revoke.mutate({
                    organizationId: orgId,
                    invitationId: invitation.id,
                  })
                }
              >
                Revoke
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
