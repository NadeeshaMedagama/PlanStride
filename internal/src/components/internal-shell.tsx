import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Gauge,
  LogOut,
  Menu,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";
import { logout } from "@/api/endpoints/auth/auth";
import { useCurrentUser } from "@/contexts/user-context";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { fullName } from "@/lib/format";

type NavPath = "/overview" | "/organizations" | "/users" | "/ai-usage";

const NAV: { to: NavPath; label: string; icon: LucideIcon }[] = [
  { to: "/overview", label: "Overview", icon: Gauge },
  { to: "/organizations", label: "Organizations", icon: Building2 },
  { to: "/users", label: "Users", icon: Users },
  { to: "/ai-usage", label: "AI usage", icon: Sparkles },
];

// The back office is visibly not the product: a dark sidebar, an "Internal"
// badge, and a strip on every page saying who it's for and what it never shows.
export function InternalShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-muted/30">
      <div className="flex shrink-0 items-center justify-center gap-2 bg-amber-400 px-4 py-1.5 text-center text-xs font-medium text-amber-950">
        <ShieldCheck className="size-3.5 shrink-0" />
        Internal console · PlanStride staff only · Customer plan content is
        never shown here
      </div>
      <div className="flex min-h-0 flex-1">
        <aside className="dark hidden w-60 shrink-0 bg-background text-foreground md:flex">
          <SidebarContent />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="dark flex h-14 items-center justify-between bg-background px-4 text-foreground md:hidden">
            <InternalLogo />
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
                className="dark w-64 p-0"
                showCloseButton={false}
              >
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <SidebarContent onNavigate={() => setMenuOpen(false)} />
              </SheetContent>
            </Sheet>
          </header>
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function InternalLogo() {
  return (
    <Link
      to="/overview"
      className="flex items-center gap-2"
      aria-label="PlanStride Internal"
    >
      <Logo className="h-6" />
      <span className="rounded border border-amber-400/40 bg-amber-400/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-widest text-amber-300 uppercase">
        Internal
      </span>
    </Link>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
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
    <div className="flex h-full w-full flex-col">
      <div className="flex h-16 items-center px-5">
        <InternalLogo />
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            onClick={onNavigate}
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
            activeProps={{ className: "bg-muted text-foreground" }}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        ))}
      </nav>
      <div className="border-t p-3">
        {user && (
          <div className="px-2 py-2">
            <p className="truncate text-sm font-medium">{fullName(user)}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user.email}
            </p>
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
    </div>
  );
}
