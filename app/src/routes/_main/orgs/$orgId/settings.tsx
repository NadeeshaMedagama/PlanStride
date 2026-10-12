import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getOrganizationGetQueryKey,
  getOrganizationListQueryKey,
  useOrganizationUpdate,
} from "@/api/endpoints/organizations/organizations";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useOrg } from "@/contexts/org-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/week";

export const Route = createFileRoute("/_main/orgs/$orgId/settings")({
  head: () => ({ meta: [{ title: "Settings · PlanStride" }] }),
  component: SettingsPage,
});

const ROLE_DESCRIPTIONS = {
  owner:
    "You can do everything: manage members (including other owners), teams and settings.",
  admin:
    "You manage members, teams and settings. Only owners can change owners.",
  member: "You plan your own weeks. Owners and admins manage the organization.",
} as const;

function SettingsPage() {
  const { orgId, organization, isManager } = useOrg();
  const queryClient = useQueryClient();
  const [name, setName] = useState(organization.name);
  const rename = useOrganizationUpdate({
    mutation: {
      onSuccess: (updated) => {
        queryClient.setQueryData(getOrganizationGetQueryKey(orgId), updated);
        void queryClient.invalidateQueries({
          queryKey: getOrganizationListQueryKey(),
        });
        toast.success("Organization renamed");
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Couldn't rename it.")),
    },
  });
  const changed = name.trim() !== organization.name && name.trim().length >= 2;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Your organization on PlanStride."
      />

      <section className="rounded-xl border bg-background">
        <div className="border-b px-5 py-4">
          <h2 className="font-medium">Organization</h2>
          <p className="text-sm text-muted-foreground">
            Created {formatDate(organization.created_at)} ·{" "}
            {organization.member_count} members · {organization.team_count}{" "}
            teams
          </p>
        </div>
        <form
          className="flex flex-col gap-3 p-5 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            rename.mutate({
              organizationId: orgId,
              data: { name: name.trim() },
            });
          }}
        >
          <div className="flex-1 space-y-1.5">
            <label htmlFor="org-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="org-name"
              value={name}
              maxLength={120}
              disabled={!isManager}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          {isManager && (
            <Button type="submit" disabled={!changed || rename.isPending}>
              {rename.isPending ? "Saving…" : "Save"}
            </Button>
          )}
        </form>
      </section>

      <section className="rounded-xl border bg-background px-5 py-4">
        <h2 className="font-medium">Your role: {organization.role}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {ROLE_DESCRIPTIONS[organization.role]}
        </p>
      </section>
    </>
  );
}
