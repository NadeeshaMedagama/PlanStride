import { format, formatDistanceToNowStrict } from "date-fns";

const compact = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const plain = new Intl.NumberFormat("en");

// 1,284 / 12.9K / 4.2M: big counts stay readable at a glance.
export function formatCount(value: number): string {
  return value >= 10_000 ? compact.format(value) : plain.format(value);
}

export function formatPercent(part: number, whole: number): string {
  if (whole === 0) {
    return "—";
  }
  const percent = (part / whole) * 100;
  return `${percent < 10 && percent > 0 ? percent.toFixed(1) : Math.round(percent)}%`;
}

export function formatDate(value: string): string {
  return format(new Date(value), "MMM d, yyyy");
}

export function formatDateTime(value: string): string {
  return format(new Date(value), "MMM d, HH:mm");
}

export function formatAgo(value: string | null): string {
  return value ? `${formatDistanceToNowStrict(new Date(value))} ago` : "never";
}

export function fullName(person: {
  first_name: string;
  last_name: string;
}): string {
  return `${person.first_name} ${person.last_name}`;
}
