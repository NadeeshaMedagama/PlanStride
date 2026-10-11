import { Outlet, createFileRoute } from "@tanstack/react-router";
import { AuthGuard } from "@/components/AuthGuard";
import { InternalShell } from "@/components/internal-shell";

// Pathless layout route: every route file under `src/routes/_main/` renders
// inside this chrome and behind the auth guard, without `_main` appearing in
// the URL. Public pages (e.g. /login) live outside it.
export const Route = createFileRoute("/_main")({ component: MainLayout });

function MainLayout() {
  return (
    <AuthGuard>
      <InternalShell>
        <Outlet />
      </InternalShell>
    </AuthGuard>
  );
}
