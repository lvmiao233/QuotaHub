import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, RefreshCw, Table2 } from "lucide-react";
import {
  HorizontalModelBar,
  ModelLegend,
  StackedDailyBarChart,
} from "@/components/charts/ModelCharts";
import { useQuota } from "@/contexts/QuotaContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type DailyModelStat, type DailyStat } from "@/lib/api";
import {
  loadDailyModelStatsCache,
  loadDailyStatsCache,
  saveDailyModelStatsCache,
  saveDailyStatsCache,
} from "@/lib/quota-cache";
import {
  aggregateOllamaModelsByWindow,
  aggregateOpenCodeModelsByCost,
  computeOllamaCycleRemaining,
  computeOpenCodeCycleRemaining,
} from "@/lib/quota-stats";
import { buildModelColorMap, cn } from "@/lib/utils";

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function StatBar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.max(4, (value / max) * 100) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className="h-full rounded-full bg-cyan-500" style={{ width: `${width}%` }} />
    </div>
  );
}

function DailyViewToggle({
  view,
  onChange,
}: {
  view: "table" | "chart";
  onChange: (view: "table" | "chart") => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5">
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs",
          view === "table" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
        )}
        onClick={() => onChange("table")}
      >
        <Table2 className="h-3.5 w-3.5" />
        表格
      </button>
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs",
          view === "chart" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
        )}
        onClick={() => onChange("chart")}
      >
        <BarChart3 className="h-3.5 w-3.5" />
        图表
      </button>
    </div>
  );
}

function DailyStatsCard({
  title,
  stats,
  modelStats,
  mode,
  loading,
  view,
  onViewChange,
}: {
  title: string;
  stats: DailyStat[];
  modelStats: DailyModelStat[];
  mode: "cost" | "count";
  loading: boolean;
  view: "table" | "chart";
  onViewChange: (view: "table" | "chart") => void;
}) {
  const maxValue = Math.max(
    ...stats.map((s) => (mode === "cost" ? s.total_cost_usd : s.request_count)),
    1
  );
  const colorMap = useMemo(
    () => buildModelColorMap(modelStats.map((row) => row.model)),
    [modelStats]
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{title}</CardTitle>
          <DailyViewToggle view={view} onChange={onViewChange} />
        </div>
      </CardHeader>
      <CardContent>
        {loading && stats.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">加载中…</p>
        ) : stats.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">暂无数据</p>
        ) : view === "chart" ? (
          <StackedDailyBarChart
            rows={modelStats}
            mode={mode}
            formatValue={mode === "cost" ? formatCost : (v) => v.toLocaleString()}
            colorMap={colorMap}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>日期</TableHead>
                <TableHead className="text-right">{mode === "cost" ? "金额" : "次数"}</TableHead>
                <TableHead className="w-32" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.map((row) => {
                const value = mode === "cost" ? row.total_cost_usd : row.request_count;
                return (
                  <TableRow key={row.date}>
                    <TableCell className="text-sm">{row.date}</TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {mode === "cost" ? formatCost(value) : value.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <StatBar value={value} max={maxValue} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const {
    ollamaAccounts,
    openGoAccounts,
    cpaChannels,
    ollamaHasData,
    openGoHasData,
    ollamaLoading,
    openGoLoading,
    refreshAll,
  } = useQuota();

  const [dailyStats, setDailyStats] = useState<DailyStat[]>(
    () => loadDailyStatsCache<DailyStat>() ?? []
  );
  const [dailyModelStats, setDailyModelStats] = useState<DailyModelStat[]>(
    () => loadDailyModelStatsCache<DailyModelStat>() ?? []
  );
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState("");
  const [dailyView, setDailyView] = useState<"table" | "chart">("chart");

  const cpaSummary = useMemo(() => {
    const accounts = cpaChannels.flatMap((channel) => channel.accounts);
    const plans = new Map<string, number>();
    accounts.forEach((account) => plans.set(account.plan, (plans.get(account.plan) || 0) + 1));
    return {
      accountCount: accounts.length,
      successCount: accounts.filter((account) => account.success).length,
      staleCount: accounts.filter((account) => account.stale).length,
      plans: [...plans.entries()],
    };
  }, [cpaChannels]);

  const ollamaCycles = useMemo(
    () => computeOllamaCycleRemaining(ollamaAccounts),
    [ollamaAccounts]
  );
  const opencodeCycles = useMemo(
    () => computeOpenCodeCycleRemaining(openGoAccounts),
    [openGoAccounts]
  );

  const sessionModels = useMemo(
    () => aggregateOllamaModelsByWindow(ollamaAccounts, "Session"),
    [ollamaAccounts]
  );
  const weeklyModels = useMemo(
    () => aggregateOllamaModelsByWindow(ollamaAccounts, "Weekly"),
    [ollamaAccounts]
  );
  const opencodeCostModels = useMemo(
    () =>
      aggregateOpenCodeModelsByCost(dailyModelStats).map((item) => ({
        model: item.model,
        requests: item.requests,
        share_percent: item.share_percent,
        title: `${item.model}\n${item.requests.toLocaleString()} 次\n${formatCost(item.cost_usd)}`,
      })),
    [dailyModelStats]
  );

  const ollamaModelNames = useMemo(() => {
    const set = new Set<string>();
    sessionModels.forEach((m) => set.add(m.model));
    weeklyModels.forEach((m) => set.add(m.model));
    return [...set];
  }, [sessionModels, weeklyModels]);

  const ollamaColorMap = useMemo(() => buildModelColorMap(ollamaModelNames), [ollamaModelNames]);
  const opencodeColorMap = useMemo(
    () => buildModelColorMap(opencodeCostModels.map((m) => m.model)),
    [opencodeCostModels]
  );

  const ollamaCycleModels: Record<string, typeof sessionModels> = useMemo(
    () => ({
      Session: sessionModels,
      Weekly: weeklyModels,
    }),
    [sessionModels, weeklyModels]
  );

  const loadDaily = useCallback(async () => {
    setDailyLoading(true);
    setDailyError("");
    try {
      const [dailyData, modelData] = await Promise.all([
        api.opencodeDailyStats(30),
        api.opencodeDailyModelStats(30),
      ]);
      setDailyStats(dailyData.stats);
      setDailyModelStats(modelData.stats);
      saveDailyStatsCache(dailyData.stats);
      saveDailyModelStatsCache(modelData.stats);
    } catch (e) {
      setDailyError((e as Error).message);
    } finally {
      setDailyLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDaily();
  }, [loadDaily]);

  const quotaRefreshing = ollamaLoading || openGoLoading;

  return (
    <div className="relative space-y-6 pb-16">
      {dailyError && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          使用统计：{dailyError}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">CPA / CLIProxyAPI 概览</CardTitle>
        </CardHeader>
        <CardContent>
          {cpaSummary.accountCount === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无 CPA 账号快照</p>
          ) : (
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant="default">{cpaChannels.length} 个渠道</Badge>
              <Badge variant="success">
                {cpaSummary.successCount}/{cpaSummary.accountCount} 个账号正常
              </Badge>
              {cpaSummary.staleCount > 0 && (
                <Badge variant="warning">{cpaSummary.staleCount} 个缓存已陈旧</Badge>
              )}
              {cpaSummary.plans.map(([plan, count]) => (
                <Badge key={plan} variant="default">{plan} · {count}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Ollama 模型次数统计</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {!ollamaHasData ? (
            <p className="py-4 text-center text-sm text-muted-foreground">等待额度数据…</p>
          ) : sessionModels.length === 0 && weeklyModels.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无模型数据</p>
          ) : (
            <>
              {ollamaCycles.map((cycle) => (
                <HorizontalModelBar
                  key={cycle.label}
                  label={cycle.displayLabel}
                  used={cycle.used}
                  total={cycle.total}
                  models={ollamaCycleModels[cycle.label] ?? []}
                  colorMap={ollamaColorMap}
                />
              ))}
              <ModelLegend models={ollamaModelNames} colorMap={ollamaColorMap} />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">OpenCode 模型金额统计</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {!openGoHasData ? (
            <p className="py-4 text-center text-sm text-muted-foreground">等待额度数据…</p>
          ) : opencodeCycles.every((c) => c.total === 0) ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无额度数据</p>
          ) : (
            <>
              {opencodeCycles.map((cycle) => (
                <HorizontalModelBar
                  key={cycle.label}
                  label={cycle.displayLabel}
                  used={cycle.used}
                  total={cycle.total}
                  models={opencodeCostModels}
                  colorMap={opencodeColorMap}
                />
              ))}
              {opencodeCostModels.length > 0 && (
                <ModelLegend
                  models={opencodeCostModels.map((m) => m.model)}
                  colorMap={opencodeColorMap}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <DailyStatsCard
          title="OpenCode 分日期金额"
          stats={dailyStats}
          modelStats={dailyModelStats}
          mode="cost"
          loading={dailyLoading}
          view={dailyView}
          onViewChange={setDailyView}
        />
        <DailyStatsCard
          title="OpenCode 分日期次数"
          stats={dailyStats}
          modelStats={dailyModelStats}
          mode="count"
          loading={dailyLoading}
          view={dailyView}
          onViewChange={setDailyView}
        />
      </div>

      <Button
        className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full shadow-lg"
        size="icon"
        onClick={() => {
          void refreshAll();
          void loadDaily();
        }}
        disabled={quotaRefreshing && !ollamaHasData}
        title="刷新"
      >
        <RefreshCw className={`h-5 w-5 ${quotaRefreshing ? "animate-spin" : ""}`} />
      </Button>
    </div>
  );
}
