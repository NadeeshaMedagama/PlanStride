import { CircleCheck, PauseCircle } from "lucide-react";

export function OrganizationStatus({
  suspendedAt,
}: {
  suspendedAt: string | null;
}) {
  return suspendedAt ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-200">
      <PauseCircle className="size-3.5" /> Suspended
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
      <CircleCheck className="size-3.5" /> Active
    </span>
  );
}
