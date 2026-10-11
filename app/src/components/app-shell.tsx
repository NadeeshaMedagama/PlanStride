import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck,
  Check,
  ChevronsUpDown,
  ClipboardCheck,
  History,
  LogOut,
  Menu,
  Plus,
  Settings,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import { logout } from "@/api/endpoints/auth/auth";
import {
  getOrganizationListQueryKey,
  useOrganizationCreate,
  useOrganizationList,
} from "@/api/endpoints/organizations/organizations";
import { useReviewQueue } from "@/api/endpoints/reviews/reviews";
import { useTeamList } from "@/api/endpoints/teams/teams";
import { useCurrentUser } from "@/contexts/user-context";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { getApiErrorMessage } from "@/lib/api-error";
import { cn, fullName, initials } from "@/lib/utils";

type NavPath =
  | "/orgs/$orgId/week"
  | "/orgs/$orgId/history"
  | "/orgs/$orgId/reviews"
  | "/orgs/$orgId/teams"
  | "/orgs/$orgId/members"
  | "/orgs/$orgId/settings";

interface NavItem {
  to: NavPath;
  label: string;
  icon: LucideIcon;
}

const PLANNING: NavItem[] = [
  { to: "/orgs/$orgId/week", label: "My week", icon: CalendarCheck },
  { to: "/orgs/$orgId/history", label: "History", icon: History },
];
const ORGANIZATION: NavItem[] = [
  { to: "/orgs/$orgId/teams", label: "Teams", icon: Users },
  { to: "/orgs/$orgId/members", label: "Members", icon: UserRound },
  { to: "/orgs/$orgId/settings", label: "Settings", icon: Settings },
];

// The chrome around every organization page: a sidebar on desktop and a
// slide-out menu on phones.
export function AppShell({
  orgId,
  children,
}: {
  orgId: string;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-background md:flex">
        <SidebarContent orgId={orgId} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b bg-background px-4 md:hidden">
          <Link
            to="/orgs/$orgId/week"
            params={{ orgId }}
            aria-label="PlanStride"
          >
            <Logo className="h-6" />
          </Link>
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger
              render={
                <Button variant="ghost" size="icon" aria-label="Open menu" />
              }
            >
              <Menu />
            </SheetTrigger>
            <SheetContent
              side="left"
              className="w-72 p-0"
              showCloseButton={false}
            >
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SidebarContent
                orgId={orgId}
                onNavigate={() => setMenuOpen(false)}
              />
            </SheetContent>
          </Sheet>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

function SidebarContent({
  orgId,
  onNavigate,
}: {
  orgId: string;
  onNavigate?: () => void;
}) {
  const { data: teams } = useTeamList(orgId);
  const leadsATeam = (teams ?? []).some((team) => team.is_lead);
  const { data: queue } = useReviewQueue(orgId, {
    query: { enabled: leadsATeam },
  });
  const waiting = queue?.length ?? 0;

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Link
          to="/orgs/$orgId/week"
          params={{ orgId }}
          aria-label="PlanStride home"
          onClick={onNavigate}
        >
          <Logo className="h-7" />
        </Link>
      </div>

      <div className="px-3">
        <OrgSwitcher orgId={orgId} onNavigate={onNavigate} />
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        <NavGroup label="Planning">
          {PLANNING.map((item) => (
            <NavLink
              key={item.to}
              item={item}
              orgId={orgId}
              onNavigate={onNavigate}
            />
          ))}
          {leadsATeam && (
            <NavLink
              item={{
                to: "/orgs/$orgId/reviews",
                label: "Reviews",
                icon: ClipboardCheck,
              }}
              orgId={orgId}
              onNavigate={onNavigate}
              badge={waiting > 0 ? waiting : undefined}
            />
          )}
        </NavGroup>
        <NavGroup label="Organization">
          {ORGANIZATION.map((item) => (
            <NavLink
              key={item.to}
              item={item}
              orgId={orgId}
              onNavigate={onNavigate}
            />
          ))}
        </NavGroup>
      </nav>

      <UserFooter />
    </div>
  );
}

function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="px-3 pb-1.5 text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function NavLink({
  item,
  orgId,
  onNavigate,
  badge,
}: {
  item: NavItem;
  orgId: string;
  onNavigate?: () => void;
  badge?: number;
}) {
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      params={{ orgId }}
      onClick={onNavigate}
      className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
      activeProps={{ className: "bg-muted text-foreground" }}
    >
      <Icon className="size-4" />
      <span className="flex-1">{item.label}</span>
      {badge !== undefined && (
        <Badge className="h-5 min-w-5 justify-center px-1.5 tabular-nums">
          {badge}
        </Badge>
      )}
    </Link>
  );
}

function OrgSwitcher({
  orgId,
  onNavigate,
}: {
  orgId: string;
  onNavigate?: () => void;
}) {
  const navigate = useNavigate();
  const { data: organizations } = useOrganizationList();
  const [creating, setCreating] = useState(false);
  const current = organizations?.find((org) => org.id === orgId);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="outline"
              className="h-auto w-full justify-between gap-2 px-3 py-2 text-left"
            />
          }
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {current?.name ?? "Organization"}
            </span>
            <span className="block text-xs text-muted-foreground capitalize">
              {current ? current.role : "Loading…"}
            </span>
          </span>
          <ChevronsUpDown className="size-4 text-muted-foreground" />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-60">
          <DropdownMenuGroup>
            <DropdownMenuLabel>Organizations</DropdownMenuLabel>
            {(organizations ?? []).map((org) => (
              <DropdownMenuItem
                key={org.id}
                onClick={() => {
                  onNavigate?.();
                  navigate({
                    to: "/orgs/$orgId/week",
                    params: { orgId: org.id },
                  });
                }}
              >
                <span className="flex-1 truncate">{org.name}</span>
                {org.is_suspended && (
                  <span className="text-xs text-muted-foreground">
                    Suspended
                  </span>
                )}
                {org.id === orgId && <Check className="size-4" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            New organization
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <CreateOrganizationDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(id) => {
          onNavigate?.();
          navigate({ to: "/orgs/$orgId/week", params: { orgId: id } });
        }}
      />
    </>
  );
}

export function CreateOrganizationDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (organizationId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useOrganizationCreate({
    mutation: {
      onSuccess: async (organization) => {
        await queryClient.invalidateQueries({
          queryKey: getOrganizationListQueryKey(),
        });
        onOpenChange(false);
        setName("");
        onCreated(organization.id);
      },
      onError: (err) =>
        setError(getApiErrorMessage(err, "Couldn't create the organization.")),
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            create.mutate({ data: { name } });
          }}
        >
          <DialogHeader>
            <DialogTitle>New organization</DialogTitle>
            <DialogDescription>
              You&apos;ll be its owner. Invite your team once it&apos;s set up.
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            placeholder="e.g. Northwind Labs"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-label="Organization name"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={name.trim().length < 2 || create.isPending}
            >
              {create.isPending ? "Creating…" : "Create organization"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function UserFooter() {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logoutMutation = useMutation({
    mutationFn: async () => {
      await logout();
    },
    onSettled: () => {
      // Drop every cached query so the next session starts clean, then leave.
      queryClient.clear();
      navigate({ to: "/login" });
    },
  });

  return (
    <div className="border-t p-3">
      {user && (
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          <Avatar firstName={user.first_name} lastName={user.last_name} />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{fullName(user)}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user.email}
            </p>
          </div>
        </div>
      )}
      <Button
        variant="ghost"
        className="mt-1 w-full justify-start text-muted-foreground hover:text-foreground"
        disabled={logoutMutation.isPending}
        onClick={() => logoutMutation.mutate()}
      >
        <LogOut className="size-4" />
        {logoutMutation.isPending ? "Signing out…" : "Sign out"}
      </Button>
    </div>
  );
}

export function Avatar({
  firstName,
  lastName,
  className,
}: {
  firstName: string;
  lastName: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
        className
      )}
    >
      {initials(firstName, lastName)}
    </span>
  );
}
