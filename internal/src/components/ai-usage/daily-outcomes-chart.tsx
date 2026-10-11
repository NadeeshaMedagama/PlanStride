import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { CircleCheck, CircleX, Clock, type LucideIcon } from "lucide-react";
import type { AIUsageDay } from "@/api/model";
import { Button } from "@/components/ui/button";

// AI calls per day, stacked by outcome. Outcomes are states, so they wear the
// reserved status colours (good / warning / critical), always paired with an
// icon and a label, and every value is also in the table view.
type OutcomeKey = "succeeded" | "rate_limited" | "failed";

const SERIES: {
  key: OutcomeKey;
  label: string;
  icon: LucideIcon;
  color: string;
}[] = [
  {
    key: "succeeded",
    label: "Succeeded",
    icon: CircleCheck,
    color: "var(--viz-good)",
  },
  {
    key: "rate_limited",
    label: "Rate limited",
    icon: Clock,
    color: "var(--viz-warning)",
  },
  {
    key: "failed",
    label: "Failed",
    icon: CircleX,
    color: "var(--viz-critical)",
  },
];

const PLOT_HEIGHT = 200;
const MARGIN = { top: 8, right: 8, bottom: 26, left: 36 };
const GAP = 2; // surface gap between stacked segments
const RADIUS = 4; // rounded data-end, square at the baseline

function niceCeiling(value: number): number {
  if (value <= 4) {
    return 4;
  }
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step =
    [1, 2, 2.5, 5, 10].find((candidate) => candidate * magnitude >= value) ??
    10;
  return step * magnitude;
}

function roundedTop(
  x: number,
  y: number,
  width: number,
  height: number
): string {
  const r = Math.min(RADIUS, height, width / 2);
  return [
    `M${x},${y + height}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${y + height}`,
    "Z",
  ].join(" ");
}

function dayLabel(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return format(new Date(year ?? 1970, (month ?? 1) - 1, date ?? 1), "MMM d");
}

export function DailyOutcomesChart({ days }: { days: AIUsageDay[] }) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const element = container.current;
    if (!element) {
      return undefined;
    }
    const observer = new ResizeObserver(([entry]) => {
      if (entry) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const totals = Object.fromEntries(
    SERIES.map(({ key }) => [key, days.reduce((sum, day) => sum + day[key], 0)])
  ) as Record<OutcomeKey, number>;
  const busiest = Math.max(
    0,
    ...days.map((d) => d.succeeded + d.rate_limited + d.failed)
  );
  const yMax = niceCeiling(busiest);
  const ticks = [0, yMax / 2, yMax];

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right);
  const band = days.length ? plotWidth / days.length : 0;
  const barWidth = Math.max(3, Math.min(24, band * 0.62));
  const scale = (value: number) => (value / yMax) * PLOT_HEIGHT;
  const labelEvery = Math.max(1, Math.ceil(days.length / 6));
  const activeDay = active !== null ? days[active] : undefined;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ul
          className="flex flex-wrap gap-x-5 gap-y-1 text-sm"
          aria-label="Legend"
        >
          {SERIES.map(({ key, label, icon: Icon, color }) => (
            <li key={key} className="flex items-center gap-1.5">
              <span
                className="size-2.5 rounded-sm"
                style={{ background: color }}
                aria-hidden
              />
              <Icon className="size-3.5 text-muted-foreground" aria-hidden />
              <span className="text-muted-foreground">{label}</span>
              <span className="font-medium">
                {totals[key].toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowTable((value) => !value)}
        >
          {showTable ? "Show chart" : "Show as table"}
        </Button>
      </div>

      {showTable ? (
        <div className="max-h-80 overflow-y-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background">
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">Day</th>
                {SERIES.map(({ key, label }) => (
                  <th key={key} className="px-3 py-2 text-right font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y tabular-nums">
              {days.map((day) => (
                <tr key={day.day}>
                  <td className="px-3 py-1.5">{dayLabel(day.day)}</td>
                  {SERIES.map(({ key }) => (
                    <td key={key} className="px-3 py-1.5 text-right">
                      {day[key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={container} className="relative">
          {busiest === 0 && (
            <p className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
              No AI calls in this period.
            </p>
          )}
          {width > 0 && (
            <svg
              width={width}
              height={MARGIN.top + PLOT_HEIGHT + MARGIN.bottom}
              role="img"
              aria-label="AI calls per day by outcome"
              onPointerLeave={() => setActive(null)}
            >
              <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
                {ticks.map((tick) => {
                  const y = PLOT_HEIGHT - scale(tick);
                  return (
                    <g key={tick}>
                      <line
                        x1={0}
                        x2={plotWidth}
                        y1={y}
                        y2={y}
                        stroke={
                          tick === 0 ? "var(--viz-axis)" : "var(--viz-grid)"
                        }
                        strokeWidth={1}
                        shapeRendering="crispEdges"
                      />
                      <text
                        x={-8}
                        y={y}
                        dy="0.32em"
                        textAnchor="end"
                        className="fill-muted-foreground text-[11px] tabular-nums"
                      >
                        {tick.toLocaleString()}
                      </text>
                    </g>
                  );
                })}

                {days.map((day, index) => {
                  const x = index * band + (band - barWidth) / 2;
                  const segments = SERIES.filter(({ key }) => day[key] > 0);
                  let top = PLOT_HEIGHT;
                  const dimmed = active !== null && active !== index;
                  return (
                    <g key={day.day} opacity={dimmed ? 0.45 : 1}>
                      {segments.map(({ key, color }, position) => {
                        const height = scale(day[key]);
                        const y = top - height;
                        top = y;
                        // The gap comes out of the upper segment of each pair.
                        const drawn = Math.max(
                          0,
                          height - (position > 0 ? GAP : 0)
                        );
                        const isTop = position === segments.length - 1;
                        return isTop ? (
                          <path
                            key={key}
                            d={roundedTop(x, y, barWidth, drawn)}
                            fill={color}
                          />
                        ) : (
                          <rect
                            key={key}
                            x={x}
                            y={y}
                            width={barWidth}
                            height={drawn}
                            fill={color}
                          />
                        );
                      })}
                      <rect
                        x={index * band}
                        y={0}
                        width={band}
                        height={PLOT_HEIGHT}
                        fill="transparent"
                        tabIndex={0}
                        className="cursor-pointer outline-none focus-visible:stroke-ring"
                        aria-label={`${dayLabel(day.day)}: ${day.succeeded} succeeded, ${day.rate_limited} rate limited, ${day.failed} failed`}
                        onPointerEnter={() => setActive(index)}
                        onFocus={() => setActive(index)}
                        onBlur={() => setActive(null)}
                      />
                      {index % labelEvery === 0 && (
                        <text
                          x={index * band + band / 2}
                          y={PLOT_HEIGHT + 18}
                          textAnchor="middle"
                          className="fill-muted-foreground text-[11px]"
                        >
                          {dayLabel(day.day)}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
          )}
          {activeDay && active !== null && (
            <div
              className="pointer-events-none absolute top-2 z-10 min-w-40 rounded-lg border bg-popover px-3 py-2 text-sm shadow-md"
              style={{
                left: Math.min(
                  Math.max(0, MARGIN.left + active * band + band / 2 - 80),
                  Math.max(0, width - 170)
                ),
              }}
            >
              <p className="mb-1 text-xs text-muted-foreground">
                {dayLabel(activeDay.day)}
              </p>
              {SERIES.map(({ key, label, color }) => (
                <p key={key} className="flex items-center gap-2">
                  <span
                    className="h-0.5 w-3 rounded-full"
                    style={{ background: color }}
                    aria-hidden
                  />
                  <span className="font-semibold tabular-nums">
                    {activeDay[key]}
                  </span>
                  <span className="text-muted-foreground">{label}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
