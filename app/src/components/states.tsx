import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import {
  CircleAlert,
  Compass,
  Lock,
  PauseCircle,
  type LucideIcon,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StateProps {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children?: ReactNode;
  className?: string;
}

// One shape for every "nothing to show here" moment: empty lists, missing
// pages, places the caller isn't allowed to go.
export function StateMessage({
  icon: Icon,
  title,
  description,
  children,
  className,
}: StateProps) {
  return (
    <Empty className={cn("border bg-background py-12", className)}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle className="text-base">{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {children && <EmptyContent>{children}</EmptyContent>}
    </Empty>
  );
}

export function NotFoundState({
  title = "We couldn't find that",
  description = "It may have been removed, or the link is wrong.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <StateMessage icon={Compass} title={title} description={description}>
      <Link to="/" className={buttonVariants({ variant: "outline" })}>
        Back to my week
      </Link>
    </StateMessage>
  );
}

export function ForbiddenState({ description }: { description: ReactNode }) {
  return (
    <StateMessage
      icon={Lock}
      title="You don't have access to this"
      description={description}
    />
  );
}

export function SuspendedState({
  organizationName,
}: {
  organizationName?: string;
}) {
  return (
    <StateMessage
      icon={PauseCircle}
      title={`${organizationName ?? "This organization"} is suspended`}
      description="Your organization's account has been paused by PlanStride. Plans are safe and nothing has been deleted. Ask your organization's owner to contact support to restore access."
    />
  );
}

export function ErrorState({
  description = "Something went wrong loading this page.",
  onRetry,
}: {
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <StateMessage
      icon={CircleAlert}
      title="That didn't load"
      description={description}
    >
      {onRetry && (
        <button
          type="button"
          className={buttonVariants({ variant: "outline" })}
          onClick={onRetry}
        >
          Try again
        </button>
      )}
    </StateMessage>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="space-y-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <Skeleton className="h-40 w-full rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children && (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      )}
    </div>
  );
}
