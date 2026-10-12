import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { keepPreviousData } from "@tanstack/react-query";
import { Building2, Search } from "lucide-react";
import { useOrganizationList } from "@/api/endpoints/organizations/organizations";
import type { OrganizationListStatus } from "@/api/model";
import { OrganizationStatus } from "@/components/organizations/organization-status";
import { PageTitle } from "@/components/stat-tile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounced } from "@/hooks/use-debounced";
import { formatAgo, fullName } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;
const FILTERS: { value: OrganizationListStatus | undefined; label: string }[] =
  [
    { value: undefined, label: "All" },
    { value: "active", label: "Active" },
    { value: "suspended", label: "Suspended" },
  ];

export const Route = createFileRoute("/_main/organizations/")({
  head: () => ({ meta: [{ title: "Organizations · PlanStride Internal" }] }),
  component: OrganizationsPage,
});

function OrganizationsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<OrganizationListStatus | undefined>();
  const [page, setPage] = useState(0);
  const query = useDebounced(search.trim(), 250);
  const { data, isLoading, isError, isFetching } = useOrganizationList(
    {
      search: query || undefined,
      status,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    },
    { query: { placeholderData: keepPreviousData } }
  );
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <>
      <PageTitle
        title="Organizations"
        description="Every customer, most recently active first. Plan content is not available here by design."
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative sm:w-72">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by name"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
            aria-label="Search organizations"
          />
        </div>
        <div className="flex gap-1" role="group" aria-label="Status">
          {FILTERS.map((filter) => (
            <Button
              key={filter.label}
              size="sm"
              variant={filter.value === status ? "secondary" : "ghost"}
              aria-pressed={filter.value === status}
              onClick={() => {
                setStatus(filter.value);
                setPage(0);
              }}
            >
              {filter.label}
            </Button>
          ))}
        </div>
      </div>

      <div
        className={cn(
          "overflow-x-auto rounded-xl border bg-background transition-opacity",
          isFetching && !isLoading && "opacity-60"
        )}
      >
        <table className="w-full min-w-[800px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Organization</th>
              <th className="px-3 py-2.5 font-medium">Owner</th>
              <th className="px-3 py-2.5 text-right font-medium">Members</th>
              <th className="px-3 py-2.5 text-right font-medium">Teams</th>
              <th className="px-3 py-2.5 text-right font-medium">Plans</th>
              <th className="px-3 py-2.5 font-medium">Last active</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading &&
              Array.from({ length: 4 }).map((_, row) => (
                <tr key={row}>
                  {Array.from({ length: 7 }).map((__, cell) => (
                    <td key={cell} className="px-4 py-3">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}
            {isError && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-destructive"
                >
                  Couldn&apos;t load organizations.
                </td>
              </tr>
            )}
            {data && items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  <Building2 className="mx-auto mb-2 size-6" />
                  No organizations match.
                </td>
              </tr>
            )}
            {items.map((organization) => (
              <tr key={organization.id} className="hover:bg-muted/40">
                <td className="px-4 py-3">
                  <Link
                    to="/organizations/$organizationId"
                    params={{ organizationId: organization.id }}
                    className="font-medium hover:underline"
                  >
                    {organization.name}
                  </Link>
                </td>
                <td className="px-3 py-3 text-muted-foreground">
                  {organization.owners.map(fullName).join(", ") || "—"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {organization.member_count}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {organization.team_count}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {organization.plan_count}
                </td>
                <td className="px-3 py-3 text-muted-foreground">
                  {formatAgo(organization.last_active_at)}
                </td>
                <td className="px-4 py-3">
                  <OrganizationStatus suspendedAt={organization.suspended_at} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of{" "}
            {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={(page + 1) * PAGE_SIZE >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
