import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  KeyRound,
  MoreHorizontal,
  Pencil,
  Search,
  ShieldCheck,
  UserCheck,
  UserX,
} from "lucide-react";
import {
  getUserListQueryKey,
  useUserList,
  useUserUpdate,
} from "@/api/endpoints/users/users";
import type { InternalUserResponse } from "@/api/model";
import { useCurrentUser } from "@/contexts/user-context";
import { useDebounced } from "@/hooks/use-debounced";
import { ChangePasswordDialog } from "@/components/users/change-password-dialog";
import { UserFormDialog } from "@/components/users/user-form-dialog";
import { PageTitle } from "@/components/stat-tile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getApiErrorMessage } from "@/lib/api-error";
import { formatAgo, fullName } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

export const Route = createFileRoute("/_main/users")({
  head: () => ({ meta: [{ title: "Users · PlanStride Internal" }] }),
  component: UsersPage,
});

function UsersPage() {
  const currentUser = useCurrentUser();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [editUser, setEditUser] = useState<InternalUserResponse | null>(null);
  const [passwordUser, setPasswordUser] = useState<InternalUserResponse | null>(
    null
  );
  const [statusUser, setStatusUser] = useState<InternalUserResponse | null>(
    null
  );
  const query = useDebounced(search.trim(), 250);

  const { data, isLoading, isError, isFetching } = useUserList(
    { search: query || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    { query: { placeholderData: keepPreviousData } }
  );
  const setActive = useUserUpdate({
    mutation: {
      onSuccess: async (user) => {
        await queryClient.invalidateQueries({
          queryKey: getUserListQueryKey(),
        });
        toast.success(
          user.is_active
            ? `${fullName(user)} can sign in again`
            : `${fullName(user)} is deactivated and signed out everywhere`
        );
        setStatusUser(null);
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "That didn't work.")),
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <>
      <PageTitle
        title="Users"
        description="Every account across all organizations. Staff access is granted only with manage.py create-user --admin."
      />

      <div className="relative sm:w-80">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search by name or email"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(0);
          }}
          aria-label="Search users"
        />
      </div>

      <div
        className={cn(
          "overflow-x-auto rounded-xl border bg-background transition-opacity",
          isFetching && !isLoading && "opacity-60"
        )}
      >
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Name</th>
              <th className="px-3 py-2.5 font-medium">Organizations</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium">Last sign-in</th>
              <th className="w-12 px-4 py-2.5">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading &&
              Array.from({ length: 5 }).map((_, row) => (
                <tr key={row}>
                  {Array.from({ length: 5 }).map((__, cell) => (
                    <td key={cell} className="px-4 py-3">
                      <Skeleton className="h-4 w-24" />
                    </td>
                  ))}
                </tr>
              ))}
            {isError && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-10 text-center text-destructive"
                >
                  Couldn&apos;t load users.
                </td>
              </tr>
            )}
            {data && items.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  No users match &ldquo;{query}&rdquo;.
                </td>
              </tr>
            )}
            {items.map((user) => {
              const isSelf = currentUser?.id === user.id;
              return (
                <tr key={user.id} className="hover:bg-muted/40">
                  <td className="px-4 py-3">
                    <p className="flex items-center gap-2 font-medium">
                      {fullName(user)}
                      {isSelf && (
                        <span className="text-xs font-normal text-muted-foreground">
                          (you)
                        </span>
                      )}
                      {user.is_platform_staff && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                          <ShieldCheck className="size-3" /> Staff
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {user.email}
                    </p>
                  </td>
                  <td className="px-3 py-3">
                    {user.memberships.length === 0 ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {user.memberships.map((membership) => (
                          <Link
                            key={membership.organization_id}
                            to="/organizations/$organizationId"
                            params={{
                              organizationId: membership.organization_id,
                            }}
                            className={cn(
                              "rounded-md border px-2 py-0.5 text-xs hover:bg-muted",
                              membership.is_suspended &&
                                "border-amber-300 text-amber-800"
                            )}
                          >
                            {membership.organization_name}{" "}
                            <span className="text-muted-foreground">
                              · {membership.role}
                            </span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {user.is_active ? (
                      <span className="text-emerald-700 dark:text-emerald-400">
                        Active
                      </span>
                    ) : (
                      <span className="text-muted-foreground">Deactivated</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {formatAgo(user.last_login_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Manage ${fullName(user)}`}
                          />
                        }
                      >
                        <MoreHorizontal />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-52">
                        <DropdownMenuItem onClick={() => setEditUser(user)}>
                          <Pencil className="size-4" /> Edit details
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setPasswordUser(user)}>
                          <KeyRound className="size-4" /> Set a new password
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {user.is_active ? (
                          <DropdownMenuItem
                            variant="destructive"
                            disabled={isSelf}
                            onClick={() => setStatusUser(user)}
                          >
                            <UserX className="size-4" /> Deactivate
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onClick={() => setStatusUser(user)}>
                            <UserCheck className="size-4" /> Reactivate
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              );
            })}
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

      <UserFormDialog
        user={editUser}
        open={editUser !== null}
        onOpenChange={(open) => !open && setEditUser(null)}
      />
      <ChangePasswordDialog
        user={passwordUser}
        open={passwordUser !== null}
        onOpenChange={(open) => !open && setPasswordUser(null)}
      />
      <AlertDialog
        open={statusUser !== null}
        onOpenChange={(open) => !open && setStatusUser(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {statusUser?.is_active ? "Deactivate" : "Reactivate"}{" "}
              {statusUser ? fullName(statusUser) : ""}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {statusUser?.is_active
                ? "They're signed out of every surface at their next request and can't sign in again. Their memberships and plans stay as they are."
                : "They'll be able to sign in again, with the same memberships as before."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={setActive.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant={statusUser?.is_active ? "destructive" : "default"}
              disabled={setActive.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (statusUser) {
                  setActive.mutate({
                    userId: statusUser.id,
                    data: { is_active: !statusUser.is_active },
                  });
                }
              }}
            >
              {statusUser?.is_active ? "Deactivate" : "Reactivate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
