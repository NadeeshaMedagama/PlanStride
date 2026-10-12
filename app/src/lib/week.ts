import { addDays, addWeeks, format, isSameYear, startOfWeek } from "date-fns";

// Plans are keyed by the Monday of their week, as a calendar date
// ("2026-10-12"). Dates are handled in the browser's local time: "this week"
// is the week the member is living in.

export function toIsoDate(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function fromIsoDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
}

export function weekStartOf(date: Date): string {
  return toIsoDate(startOfWeek(date, { weekStartsOn: 1 }));
}

export function currentWeekStart(): string {
  return weekStartOf(new Date());
}

export function shiftWeek(weekStart: string, weeks: number): string {
  return toIsoDate(addWeeks(fromIsoDate(weekStart), weeks));
}

export function isMonday(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && fromIsoDate(value).getDay() === 1;
}

// "Oct 12 – 16" (or "Sep 28 – Oct 2", with the year when it isn't this year).
export function formatWeekRange(weekStart: string): string {
  const monday = fromIsoDate(weekStart);
  const friday = addDays(monday, 4);
  const sameMonth = monday.getMonth() === friday.getMonth();
  const range = sameMonth
    ? `${format(monday, "MMM d")} – ${format(friday, "d")}`
    : `${format(monday, "MMM d")} – ${format(friday, "MMM d")}`;
  return isSameYear(monday, new Date())
    ? range
    : `${range}, ${format(friday, "yyyy")}`;
}

// "This week", "Next week", "Last week", or the date range.
export function describeWeek(weekStart: string): string {
  const current = currentWeekStart();
  if (weekStart === current) {
    return "This week";
  }
  if (weekStart === shiftWeek(current, 1)) {
    return "Next week";
  }
  if (weekStart === shiftWeek(current, -1)) {
    return "Last week";
  }
  return `Week of ${formatWeekRange(weekStart)}`;
}

// Mirrors the API's planning window: last week up to four weeks ahead.
export function canStartPlan(weekStart: string): boolean {
  const current = currentWeekStart();
  return (
    weekStart >= shiftWeek(current, -1) && weekStart <= shiftWeek(current, 4)
  );
}

export function formatDateTime(value: string): string {
  return format(new Date(value), "EEE MMM d, HH:mm");
}

export function formatDate(value: string): string {
  return format(new Date(value), "MMM d, yyyy");
}
