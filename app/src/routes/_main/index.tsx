import { Navigate, createFileRoute } from "@tanstack/react-router";
import { useOrganizationList } from "@/api/endpoints/organizations/organizations";
import FullScreenLoader from "@/components/FullScreenLoader";
import { ErrorState } from "@/components/states";
import { lastOrg } from "@/contexts/org-context";

// `/` isn't a page: it sends you to the organization you used last (or the
// first one you belong to), or to onboarding if you have none yet.
export const Route = createFileRoute("/_main/")({ component: Home });

function Home() {
  const {
    data: organizations,
    isLoading,
    isError,
    refetch,
  } = useOrganizationList();

  if (isLoading) {
    return <FullScreenLoader />;
  }
  if (isError || !organizations) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <ErrorState onRetry={() => void refetch()} />
      </div>
    );
  }
  if (organizations.length === 0) {
    return <Navigate to="/welcome" replace />;
  }

  const remembered = lastOrg();
  const target =
    organizations.find((org) => org.id === remembered && !org.is_suspended) ??
    organizations.find((org) => !org.is_suspended) ??
    organizations[0];
  return (
    <Navigate
      to="/orgs/$orgId/week"
      params={{ orgId: target?.id ?? "" }}
      replace
    />
  );
}
