import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Link2, Plus } from "lucide-react";
import { Logo } from "@/components/Logo";
import { CreateOrganizationDialog } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { useCurrentUser } from "@/contexts/user-context";

// For signed-in users who belong to no organization: they signed up through
// an invite that was later revoked, or were removed from their last one.
export const Route = createFileRoute("/_main/welcome")({ component: Welcome });

function Welcome() {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto h-9" />
        <h1 className="mt-8 text-2xl font-semibold tracking-tight">
          {user ? `Welcome, ${user.first_name}` : "Welcome"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You&apos;re not in an organization yet. Plans live inside an
          organization, so start one or join your team&apos;s.
        </p>
        <div className="mt-8 grid gap-3 text-left">
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex items-start gap-3 rounded-xl border bg-background p-4 transition-colors hover:border-primary/40"
          >
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Plus className="size-4" />
            </span>
            <span>
              <span className="block text-sm font-medium">
                Start an organization
              </span>
              <span className="block text-sm text-muted-foreground">
                You&apos;ll be its owner and can invite your team.
              </span>
            </span>
          </button>
          <div className="flex items-start gap-3 rounded-xl border border-dashed bg-background/60 p-4">
            <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Link2 className="size-4" />
            </span>
            <span>
              <span className="block text-sm font-medium">Join your team</span>
              <span className="block text-sm text-muted-foreground">
                Ask an owner or admin of your organization for an invite link,
                then open it while signed in.
              </span>
            </span>
          </div>
        </div>
        <Button
          variant="link"
          className="mt-6"
          onClick={() => navigate({ to: "/" })}
        >
          I just joined, take me in
        </Button>
      </div>
      <CreateOrganizationDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(orgId) =>
          navigate({ to: "/orgs/$orgId/week", params: { orgId } })
        }
      />
    </div>
  );
}
