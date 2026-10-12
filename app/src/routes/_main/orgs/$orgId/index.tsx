import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_main/orgs/$orgId/")({
  beforeLoad: ({ params }) => {
    throw redirect({ to: "/orgs/$orgId/week", params });
  },
});
