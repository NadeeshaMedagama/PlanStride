import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router";
import { QueryProvider } from "@/components/QueryProvider";
import { UserProvider } from "@/contexts/user-context";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NotFoundState } from "@/components/states";
import appCss from "@/styles.css?url";

// Document shell for the whole app. In SPA mode this is what gets prerendered
// into `_shell.html`, so everything here runs before any route does.
export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "PlanStride" },
      {
        name: "description",
        content:
          "Plan your week, get it approved and track it to Friday with PlanStride.",
      },
      { name: "theme-color", content: "#059669" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", href: "/favicon.ico", sizes: "48x48" },
      { rel: "icon", href: "/icon.svg", type: "image/svg+xml" },
      { rel: "apple-touch-icon", href: "/apple-touch-icon.png" },
    ],
  }),
  shellComponent: RootDocument,
  notFoundComponent: () => (
    <div className="flex min-h-screen items-center justify-center p-6">
      <NotFoundState />
    </div>
  ),
});

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body className="antialiased">
        <QueryProvider>
          <UserProvider>
            <TooltipProvider>
              {children}
              <Toaster />
            </TooltipProvider>
          </UserProvider>
        </QueryProvider>
        <Scripts />
      </body>
    </html>
  );
}
