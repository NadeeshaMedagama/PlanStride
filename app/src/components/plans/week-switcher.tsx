import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  currentWeekStart,
  describeWeek,
  formatWeekRange,
  shiftWeek,
} from "@/lib/week";

export function WeekSwitcher({
  week,
  onChange,
}: {
  week: string;
  onChange: (week: string) => void;
}) {
  const isCurrent = week === currentWeekStart();
  return (
    <div className="flex items-center gap-1">
      <Button
        variant="outline"
        size="icon"
        aria-label="Previous week"
        onClick={() => onChange(shiftWeek(week, -1))}
      >
        <ChevronLeft />
      </Button>
      <div className="min-w-36 px-2 text-center">
        <p className="text-sm font-medium">{describeWeek(week)}</p>
        <p className="text-xs text-muted-foreground">{formatWeekRange(week)}</p>
      </div>
      <Button
        variant="outline"
        size="icon"
        aria-label="Next week"
        onClick={() => onChange(shiftWeek(week, 1))}
      >
        <ChevronRight />
      </Button>
      {!isCurrent && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange(currentWeekStart())}
        >
          This week
        </Button>
      )}
    </div>
  );
}
