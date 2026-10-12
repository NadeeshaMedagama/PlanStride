import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useMemberList } from "@/api/endpoints/members/members";
import {
  getTeamListQueryKey,
  useTeamCreate,
  useTeamUpdate,
} from "@/api/endpoints/teams/teams";
import type { TeamDetailResponse } from "@/api/model";
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
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api-error";
import { fullName } from "@/lib/utils";

// Create a team, or edit an existing team's name and description. Leads and
// members of an existing team are managed on the team page.
export function TeamFormDialog({
  orgId,
  open,
  onOpenChange,
  team,
  onSaved,
}: {
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team?: TeamDetailResponse;
  onSaved?: (team: TeamDetailResponse) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {/* Mounted per opening, so the form always starts from `team`. */}
        {open && (
          <TeamForm
            orgId={orgId}
            team={team}
            onClose={() => onOpenChange(false)}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function TeamForm({
  orgId,
  team,
  onClose,
  onSaved,
}: {
  orgId: string;
  team?: TeamDetailResponse;
  onClose: () => void;
  onSaved?: (team: TeamDetailResponse) => void;
}) {
  const queryClient = useQueryClient();
  const editing = Boolean(team);
  const { data: members } = useMemberList(orgId, {
    query: { enabled: !editing },
  });
  const [name, setName] = useState(team?.name ?? "");
  const [description, setDescription] = useState(team?.description ?? "");
  const [leadId, setLeadId] = useState("");
  const [memberIds, setMemberIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const done = async (saved: TeamDetailResponse) => {
    await queryClient.invalidateQueries({
      queryKey: getTeamListQueryKey(orgId),
    });
    toast.success(editing ? "Team updated" : `${saved.name} created`);
    onClose();
    onSaved?.(saved);
  };
  const fail = (err: unknown) =>
    setError(getApiErrorMessage(err, "Couldn't save the team."));
  const create = useTeamCreate({
    mutation: { onSuccess: done, onError: fail },
  });
  const update = useTeamUpdate({
    mutation: { onSuccess: done, onError: fail },
  });
  const pending = create.isPending || update.isPending;

  const submit = () => {
    setError(null);
    if (team) {
      update.mutate({
        organizationId: orgId,
        teamId: team.id,
        data: { name: name.trim(), description: description.trim() || null },
      });
    } else {
      create.mutate({
        organizationId: orgId,
        data: {
          name: name.trim(),
          description: description.trim() || null,
          lead_user_id: leadId || null,
          member_ids: memberIds,
        },
      });
    }
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>{editing ? "Edit team" : "New team"}</DialogTitle>
        <DialogDescription>
          {editing
            ? "Rename the team or change what it's for."
            : "The lead approves the plans of everyone on the team."}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="team-name">
            Name
          </label>
          <Input
            id="team-name"
            autoFocus
            maxLength={80}
            placeholder="e.g. Payments"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="team-description">
            What the team works on{" "}
            <span className="text-muted-foreground">(optional)</span>
          </label>
          <Textarea
            id="team-description"
            rows={2}
            maxLength={280}
            placeholder="e.g. Checkout, billing and payouts."
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        {!editing && (
          <>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="team-lead">
                Lead
              </label>
              <NativeSelect
                id="team-lead"
                className="w-full"
                value={leadId}
                onChange={(event) => setLeadId(event.target.value)}
              >
                <NativeSelectOption value="">No lead yet</NativeSelectOption>
                {(members ?? []).map((member) => (
                  <NativeSelectOption
                    key={member.user.id}
                    value={member.user.id}
                  >
                    {fullName(member.user)}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Members</p>
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border p-2">
                {(members ?? []).map((member) => {
                  const id = member.user.id;
                  const isLead = id === leadId;
                  return (
                    <label
                      key={id}
                      className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
                    >
                      <Checkbox
                        checked={isLead || memberIds.includes(id)}
                        disabled={isLead}
                        onCheckedChange={(checked) =>
                          setMemberIds((current) =>
                            checked
                              ? [...current, id]
                              : current.filter((candidate) => candidate !== id)
                          )
                        }
                      />
                      <span className="flex-1">{fullName(member.user)}</span>
                      {isLead && (
                        <span className="text-xs text-muted-foreground">
                          Lead
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>

      <DialogFooter>
        <Button variant="ghost" onClick={onClose} disabled={pending}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={!name.trim() || pending}>
          {pending && <Spinner />}
          {editing ? "Save" : "Create team"}
        </Button>
      </DialogFooter>
    </>
  );
}
