import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Link2 } from "lucide-react";
import {
  getInvitationListQueryKey,
  useInvitationCreate,
} from "@/api/endpoints/invitations/invitations";
import type { InvitationCreateRequestRole } from "@/api/model";
import { Button } from "@/components/ui/button";
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
import { getApiErrorMessage } from "@/lib/api-error";

// Invite links are single-use and last 7 days. The server keeps only a hash
// of the token, so the link can be shown exactly once: here.
export function InviteDialog({
  orgId,
  open,
  onOpenChange,
}: {
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<InvitationCreateRequestRole>("member");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const create = useInvitationCreate({
    mutation: {
      onSuccess: async (invitation) => {
        setLink(`${window.location.origin}/join/${invitation.token}`);
        await queryClient.invalidateQueries({
          queryKey: getInvitationListQueryKey(orgId),
        });
      },
    },
  });

  const close = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      setLink(null);
      setCopied(false);
      setRole("member");
      create.reset();
    }
  };

  const copy = async () => {
    if (!link) {
      return;
    }
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // Clipboard can be blocked; the link is selectable in the field.
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Invite someone</DialogTitle>
          <DialogDescription>
            {link
              ? "Send this link to the person you're inviting. It works once and expires in 7 days. Copy it now: for security, we can't show it again."
              : "Create a link to share with one person. They'll sign up (or sign in) and join with the role you pick."}
          </DialogDescription>
        </DialogHeader>

        {link ? (
          <div className="flex gap-2">
            <Input
              readOnly
              value={link}
              onFocus={(event) => event.target.select()}
              aria-label="Invite link"
            />
            <Button
              onClick={() => void copy()}
              variant={copied ? "secondary" : "default"}
            >
              {copied ? (
                <Check className="size-4" />
              ) : (
                <Copy className="size-4" />
              )}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        ) : (
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="invite-role">
              They join as
            </label>
            <NativeSelect
              id="invite-role"
              className="w-full"
              value={role}
              onChange={(event) =>
                setRole(event.target.value as InvitationCreateRequestRole)
              }
            >
              <NativeSelectOption value="member">
                Member: plans their own weeks
              </NativeSelectOption>
              <NativeSelectOption value="admin">
                Admin: also manages members and teams
              </NativeSelectOption>
            </NativeSelect>
          </div>
        )}

        {create.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getApiErrorMessage(
              create.error,
              "Couldn't create the invite link."
            )}
          </p>
        )}

        <DialogFooter>
          {link ? (
            <Button variant="outline" onClick={() => close(false)}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => close(false)}>
                Cancel
              </Button>
              <Button
                disabled={create.isPending}
                onClick={() =>
                  create.mutate({ organizationId: orgId, data: { role } })
                }
              >
                {create.isPending ? <Spinner /> : <Link2 className="size-4" />}
                Create invite link
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
