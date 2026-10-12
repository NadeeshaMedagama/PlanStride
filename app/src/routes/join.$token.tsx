import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Users } from "lucide-react";
import {
  useInvitationAccept,
  useInvitationPreview,
} from "@/api/endpoints/invitations/invitations";
import { getOrganizationListQueryKey } from "@/api/endpoints/organizations/organizations";
import { Logo } from "@/components/Logo";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useUser } from "@/contexts/user-context";
import { getApiErrorMessage } from "@/lib/api-error";

// Where an invite link lands. Signed in: one click to join. Signed out:
// create an account (which joins in the same step) or sign in first.
export const Route = createFileRoute("/join/$token")({
  head: () => ({ meta: [{ title: "Join your team · PlanStride" }] }),
  component: Join,
});

function Join() {
  const { token } = Route.useParams();
  const { isAuthenticated, isLoading: authLoading, user } = useUser();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const preview = useInvitationPreview(token, { query: { retry: false } });
  const accept = useInvitationAccept({
    mutation: {
      onSuccess: async (organization) => {
        await queryClient.invalidateQueries({
          queryKey: getOrganizationListQueryKey(),
        });
        navigate({
          to: "/orgs/$orgId/week",
          params: { orgId: organization.id },
        });
      },
    },
  });

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto h-9" />
        <div className="mt-8 rounded-xl border bg-background p-6 text-left shadow-sm">
          {(preview.isLoading || authLoading) && (
            <div className="space-y-3">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}

          {preview.isError && (
            <div className="flex gap-3">
              <CircleAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
              <div>
                <h1 className="font-medium">
                  This invite link doesn&apos;t work
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {getApiErrorMessage(
                    preview.error,
                    "It may have expired or already been used."
                  )}{" "}
                  Ask whoever sent it for a new link.
                </p>
                <Link
                  to="/"
                  className={buttonVariants({
                    variant: "outline",
                    className: "mt-4",
                  })}
                >
                  Go to PlanStride
                </Link>
              </div>
            </div>
          )}

          {preview.data && !authLoading && (
            <>
              <div className="flex items-center gap-3">
                <span className="flex size-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Users className="size-5" />
                </span>
                <div>
                  <h1 className="font-semibold">
                    Join {preview.data.organization_name}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {preview.data.invited_by
                      ? `${preview.data.invited_by} invited you`
                      : "You've been invited"}{" "}
                    as {preview.data.role === "admin" ? "an admin" : "a member"}
                    .
                  </p>
                </div>
              </div>

              {isAuthenticated ? (
                <div className="mt-6 space-y-3">
                  <Button
                    className="h-11 w-full"
                    disabled={accept.isPending}
                    onClick={() => accept.mutate({ token })}
                  >
                    {accept.isPending
                      ? "Joining…"
                      : `Join as ${user?.first_name ?? "you"}`}
                  </Button>
                  {accept.isError && (
                    <p role="alert" className="text-sm text-destructive">
                      {getApiErrorMessage(
                        accept.error,
                        "Couldn't join. Try again."
                      )}
                    </p>
                  )}
                </div>
              ) : (
                <div className="mt-6 grid gap-2">
                  <Link
                    to="/signup"
                    search={{ invite: token }}
                    className={buttonVariants({ className: "h-11" })}
                  >
                    Create an account to join
                  </Link>
                  <Link
                    to="/login"
                    search={{ redirect: `/join/${token}` }}
                    className={buttonVariants({
                      variant: "outline",
                      className: "h-11",
                    })}
                  >
                    I already have an account
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
