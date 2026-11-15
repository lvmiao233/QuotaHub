import type { ReactNode } from "react";
import type { OllamaModelUsage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ModelLegend({
  models,
  colorMap,
}: {
  models: string[];
  colorMap: Map<string, string>;
}) {
  if (models.length === 0) return null;
  const sorted = [...models].sort();
  return (
    <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5 pt-3.5">
      {sorted.map((model) => (
        <div key={model} className="flex items-center gap-1.5 text-xs text-slate-600">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: colorMap.get(model) }}
          />
          <span>{model}</span>
        </div>
      ))}
    </div>
  );
}

export function QuotaCycleBarsGrid({ count, children }: { count: number; children: ReactNode }) {
  const gridClass =
    count >= 3
      ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
      : count === 2
        ? "grid-cols-1 md:grid-cols-2"
        : "grid-cols-1";
  return <div className={cn("grid w-full gap-x-4 gap-y-3.5", gridClass)}>{children}</div>;
}

export function HorizontalModelBar({
  label,
  used,
  total,
  models,
  colorMap,
  subtitle,
}: {
  label: string;
  used?: number;
  total?: number;
  models: OllamaModelUsage[];
  colorMap: Map<string, string>;
  subtitle?: string;
}) {
  const visibleModels = models.filter((m) => m.requests > 0);
  const showUsage = used != null && total != null && total > 0;
  const fillWidth = showUsage ? Math.max(0, Math.min(100, (used / total) * 100)) : 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        {showUsage ? (
          <span className="shrink-0 tabular-nums text-xs text-slate-600">
            已用 {round1(used)}/{round1(total)}%
          </span>
        ) : (
          subtitle && <span className="text-xs text-muted-foreground">{subtitle}</span>
        )}
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-200">
        {visibleModels.length > 0 ? (
          <div className="flex h-full overflow-hidden" style={{ width: `${fillWidth}%` }}>
            {visibleModels.map((model) => (
              <div
                key={model.model}
                className="h-full min-w-[2px] shrink-0 border-r border-white/80 last:border-r-0"
                style={{
                  width: `${Math.max(model.share_percent ?? 0, 0.5)}%`,
                  backgroundColor: colorMap.get(model.model),
                }}
                title={model.title ?? `${model.model}: ${model.requests} 次`}
              />
            ))}
          </div>
        ) : (
          <div className="h-full rounded-full bg-slate-400" style={{ width: `${fillWidth}%` }} />
        )}
      </div>
    </div>
  );
}

export type CostModelUsage = {
  model: string;
  requests: number;
  cost_usd: number;
  share_percent: number;
  title?: string;
};

export function HorizontalCostModelBar({
  label,
  used,
  total,
  models,
  colorMap,
}: {
  label: string;
  used?: number;
  total?: number;
  models: CostModelUsage[];
  colorMap: Map<string, string>;
}) {
  const visibleModels = models.filter((m) => m.cost_usd > 0);
  const showUsage = used != null && total != null && total > 0;
  const fillWidth = showUsage ? Math.max(0, Math.min(100, (used / total) * 100)) : 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        {showUsage && (
          <span className="shrink-0 tabular-nums text-xs text-slate-600">
            已用 {round1(used)}/{round1(total)}%
          </span>
        )}
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-200">
        {visibleModels.length > 0 ? (
          <div className="flex h-full overflow-hidden" style={{ width: `${fillWidth}%` }}>
            {visibleModels.map((model) => (
              <div
                key={model.model}
                className="h-full min-w-[2px] shrink-0 border-r border-white/80 last:border-r-0"
                style={{
                  width: `${Math.max(model.share_percent, 0.5)}%`,
                  backgroundColor: colorMap.get(model.model),
                }}
                title={
                  model.title ??
                  `${model.model}\n${model.requests} 次\n${formatCost(model.cost_usd)}`
                }
              />
            ))}
          </div>
        ) : (
          <div className="h-full rounded-full bg-slate-400" style={{ width: `${fillWidth}%` }} />
        )}
      </div>
    </div>
  );
}

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

export type DailyModelRow = {
  date: string;
  model: string;
  total_cost_usd: number;
  request_count: number;
};

export function collectModels(rows: DailyModelRow[]): string[] {
  const set = new Set<string>();
  for (const row of rows) set.add(row.model);
  return [...set].sort();
}

type DayBucket = {
  date: string;
  total: number;
  byModel: Map<string, number>;
};

function groupDailyByModel(rows: DailyModelRow[], mode: "cost" | "count"): DayBucket[] {
  const buckets = new Map<string, DayBucket>();
  for (const row of rows) {
    const value = mode === "cost" ? row.total_cost_usd : row.request_count;
    const bucket = buckets.get(row.date) ?? { date: row.date, total: 0, byModel: new Map() };
    bucket.total += value;
    bucket.byModel.set(row.model, (bucket.byModel.get(row.model) ?? 0) + value);
    buckets.set(row.date, bucket);
  }
  return [...buckets.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function StackedDailyBarChart({
  rows,
  mode,
  formatValue,
  colorMap,
}: {
  rows: DailyModelRow[];
  mode: "cost" | "count";
  formatValue: (value: number) => string;
  colorMap: Map<string, string>;
}) {
  const models = collectModels(rows);
  const days = groupDailyByModel(rows, mode);
  const maxTotal = Math.max(...days.map((d) => d.total), 1);
  const chartHeight = 180;

  if (days.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">暂无数据</p>;
  }

  return (
    <div>
      <div className="flex items-end gap-1 overflow-x-auto pb-1" style={{ minHeight: chartHeight + 24 }}>
        {days.map((day) => {
          const barHeightPx = Math.max(4, (day.total / maxTotal) * chartHeight);
          return (
            <div
              key={day.date}
              className="flex min-w-[28px] flex-1 flex-col items-center justify-end"
              style={{ height: chartHeight + 20 }}
            >
              <div
                className="flex w-full max-w-10 flex-col-reverse overflow-hidden rounded-t"
                style={{ height: barHeightPx }}
                title={`${day.date}: ${formatValue(day.total)}`}
              >
                {models.map((model) => {
                  const value = day.byModel.get(model) ?? 0;
                  if (value <= 0) return null;
                  const segmentHeight = (value / day.total) * 100;
                  return (
                    <div
                      key={model}
                      style={{
                        height: `${segmentHeight}%`,
                        backgroundColor: colorMap.get(model),
                        minHeight: segmentHeight > 0 ? 2 : 0,
                      }}
                      title={`${model}: ${formatValue(value)}`}
                    />
                  );
                })}
              </div>
              <span className="mt-1 truncate text-[10px] text-muted-foreground">{day.date.slice(5)}</span>
            </div>
          );
        })}
      </div>
      <ModelLegend models={models} colorMap={colorMap} />
    </div>
  );
}
