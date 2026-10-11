import { useEffect } from "react";
import { Outlet, createFileRoute } from "@tanstack/react-router";
import { useOrganizationGet } from "@/api/endpoints/organizations/organizations";
import { AppShell } from "@/components/app-shell";
import {
  ErrorState,
  NotFoundState,
  PageSkeleton,
  SuspendedState,
} from "@/components/states";
import { OrgProvider, rememberOrg } from "@/contexts/org-context";
import { getApiErrorCode, getApiErrorStatus } from "@/lib/api-error";

// Every organization page renders inside this layout. The organization (and
// the caller's role in it) comes from the API; if the caller isn't a member,
// or the organization is suspended, the page says so instead of rendering.
export const Route = createFileRoute("/_main/orgs/$orgId")({
  component: OrganizationLayout,
});

function OrganizationLayout() {
  const { orgId } = Route.useParams();
  const {
    data: organization,
    error,
    isLoading,
    refetch,
  } = useOrganizationGet(orgId, { query: { retry: false } });

  useEffect(() => {
    if (organization) {
      rememberOrg(organization.id);
    }
  }, [organization]);

  let content;
  if (isLoading) {
    content = <PageSkeleton />;
  } else if (organization) {
    content = (
      <OrgProvider organization={organization}>
        <Outlet />
      </OrgProvider>
    );
  } else if (getApiErrorCode(error) === "organization_suspended") {
    content = <SuspendedState />;
  } else if (getApiErrorStatus(error) === 404) {
    content = (
      <NotFoundState
        title="Organization not found"
        description="It doesn't exist, or you're not a member of it."
      />
    );
  } else {
    content = <ErrorState onRetry={() => void refetch()} />;
  }

  return <AppShell orgId={orgId}>{content}</AppShell>;
}
