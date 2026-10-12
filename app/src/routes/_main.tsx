import { Outlet, createFileRoute } from "@tanstack/react-router";
import { AuthGuard } from "@/components/AuthGuard";

// Pathless layout route: every route file under `src/routes/_main/` renders
// behind the auth guard, without `_main` appearing in the URL. Public pages
// (/login, /signup, /join) live outside it. Organization pages add the app
// chrome in `_main/orgs/$orgId.tsx`.
export const Route = createFileRoute("/_main")({ component: MainLayout });

function MainLayout() {
  return (
    <AuthGuard>
      <Outlet />
    </AuthGuard>
  );
}
