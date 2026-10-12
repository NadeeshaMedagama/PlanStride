import { useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useGetCurrentUser } from "@/api/endpoints/users/users";
import { PUBLIC_ROUTES } from "@/lib/routes";

// Resolves the current session from GET /users/self (authenticated via the
// httponly access_token cookie) and redirects to /login when a protected
// route is hit without a valid session, remembering where the user was going.
export function useAuth() {
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;
  const [isInitialMount, setIsInitialMount] = useState(true);

  const {
    data: user,
    isLoading: queryLoading,
    error,
    refetch,
  } = useGetCurrentUser({
    query: {
      retry: false,
      staleTime: 0,
      gcTime: 0,
    },
  });

  useEffect(() => {
    if (!queryLoading) {
      if (error) {
        // Only redirect to login from protected routes; public routes such
        // as /login must render without a session.
        const isMetaRoute = PUBLIC_ROUTES.some((route) =>
          pathname.startsWith(route)
        );

        if (!isMetaRoute) {
          const redirect = pathname === "/" ? undefined : location.href;
          navigate({ to: "/login", search: { redirect }, replace: true });
          return undefined;
        }
      }
      // Small buffer to prevent UI flash while the auth check settles.
      const timer = setTimeout(() => {
        setIsInitialMount(false);
      }, 100);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [queryLoading, error, navigate, pathname, location.href]);

  const isLoading = queryLoading || isInitialMount;
  const isAuthenticated = !isLoading && !error && !!user;
  const isUnauthenticated = !isLoading && (!!error || !user);

  return {
    user,
    isLoading,
    error,
    isAuthenticated,
    isUnauthenticated,
    refetch,
  };
}

// Only same-site paths are followed after sign-in, never an absolute URL.
export function safeRedirect(target: string | undefined): string {
  return target && target.startsWith("/") && !target.startsWith("//")
    ? target
    : "/";
}
