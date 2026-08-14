import type {
  CPAQuotaAccount,
  OllamaModelUsage,
  PublicQuotaAccount,
  QuotaWindow,
} from "@/lib/api";
import { useEffect, useState } from "react";
import {
  applyOpenCodeCascade,
  formatPlanLabel,
  formatResetIn,
  buildModelColorMap,
  ollamaQuotaLabel,
  opencodeBlockedLabel,
  progressTone,
  quotaLabel,
  usageTone,
} from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

function useResetSeconds(quotaWindow: QuotaWindow): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!quotaWindow.reset_at || Number.isNaN(Date.parse(quotaWindow.reset_at))) return;
    const timer = globalThis.setInterval(() => setNow(Date.now()), 30_000);
    return () => globalThis.clearInterval(timer);
  }, [quotaWindow.reset_at]);

  if (quotaWindow.reset_at) {
    const resetAt = Date.parse(quotaWindow.reset_at);
    if (!Number.isNaN(resetAt)) {
      return Math.max(0, Math.ceil((resetAt - now) / 1000));
    }
  }
  return quotaWindow.reset_in_sec;
}

export function QuotaWindowRow({ window }: { window: QuotaWindow }) {
  const used = Math.round(window.used * 10) / 10;
  const blocked = Boolean(window.blocked);
  const resetSeconds = useResetSeconds(window);

  return (
    <div className={`space-y-2 ${blocked ? "opacity-60" : ""}`}>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-700">{quotaLabel(window.label)}</span>
        {blocked ? (
          <span className="text-xs text-rose-600">{opencodeBlockedLabel(window.blocked_by)}</span>
        ) : (
          <span className={usageTone(window.used)}>
            已用 <span className="font-semibold tabular-nums">{used}%</span>
          </span>
        )}
      </div>
      <Progress
        value={blocked ? 100 : window.used}
        indicatorClassName={blocked ? "bg-slate-300" : progressTone(window.used)}
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{blocked ? opencodeBlockedLabel(window.blocked_by) : `剩余 ${Math.round(window.remaining * 10) / 10}%`}</span>
        {!blocked && <span>{formatResetIn(resetSeconds)}</span>}
      </div>
    </div>
  );
}

function OpenCodeQuotaWindows({ windows }: { windows: QuotaWindow[] }) {
  const cascaded = applyOpenCodeCascade(windows);
  return (
    <>
      {cascaded.map((window) => (
        <QuotaWindowRow key={window.label} window={window} />
      ))}
    </>
  );
}

function OllamaSegmentedBar({ used, models }: { used: number; models: OllamaModelUsage[] }) {
  const fillWidth = Math.max(0, Math.min(100, used));
  const visibleModels = models.filter((m) => (m.share_percent ?? 0) > 0 || m.requests > 0);
  const colorMap = buildModelColorMap(models.map((m) => m.model));

  if (visibleModels.length === 0) {
    return (
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-slate-400 transition-all duration-500"
          style={{ width: `${fillWidth}%` }}
        />
      </div>
    );
  }

  return (
    <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
      <div className="flex h-full overflow-hidden" style={{ width: `${fillWidth}%` }}>
        {visibleModels.map((model) => (
          <div
            key={model.model}
            className="group/segment relative h-full min-w-[2px] shrink-0 cursor-default border-r border-white/80 last:border-r-0"
            style={{
              width: `${Math.max(model.share_percent ?? 0, 0.3)}%`,
              backgroundColor: colorMap.get(model.model),
            }}
            title={`${model.model}: ${model.requests} 次`}
          />
        ))}
      </div>
    </div>
  );
}

function OllamaQuotaWindowRow({ window }: { window: QuotaWindow }) {
  const used = Math.round(window.used * 10) / 10;
  const hasModels = Boolean(window.models && window.models.length > 0);
  const resetSeconds = useResetSeconds(window);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-700">{ollamaQuotaLabel(window.label)}</span>
        <span className={usageTone(window.used)}>
          已用 <span className="font-semibold tabular-nums">{used}%</span>
        </span>
      </div>
      {hasModels ? (
        <OllamaSegmentedBar used={window.used} models={window.models!} />
      ) : (
        <Progress value={window.used} indicatorClassName={progressTone(window.used)} />
      )}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>剩余 {Math.round(window.remaining * 10) / 10}%</span>
        <span>{formatResetIn(resetSeconds)}</span>
      </div>
    </div>
  );
}

export function QuotaLoadingSkeleton({ rows = 2 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="h-4 w-20 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-16 animate-pulse rounded bg-slate-200" />
          </div>
          <div className="h-2.5 animate-pulse rounded-full bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

export function OllamaAccountCard({
  account,
  loading,
  onClick,
}: {
  account: import("@/lib/api").OllamaQuotaAccount;
  loading?: boolean;
  onClick?: () => void;
}) {
  return (
    <Card className={onClick ? "cursor-pointer transition-shadow hover:shadow-md" : ""} onClick={onClick}>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{account.name}</CardTitle>
            <CardDescription className="mt-1">Ollama Cloud</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {!loading && account.plan && <Badge variant="default">{formatPlanLabel(account.plan)}</Badge>}
            {!loading && account.stale && <Badge variant="warning">缓存已陈旧</Badge>}
            <Badge variant={loading ? "default" : account.success ? "success" : "danger"}>
              {loading ? "加载中" : account.success ? "正常" : "异常"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <QuotaLoadingSkeleton rows={2} />
        ) : (
          <>
            {!account.success && account.error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {account.error}
              </div>
            )}
            {account.windows?.map((window) => (
              <OllamaQuotaWindowRow key={window.label} window={window} />
            ))}
            {account.updated_at && (
              <p className="text-[11px] text-muted-foreground">
                更新于 {new Date(account.updated_at).toLocaleString("zh-CN")}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function OpenGoAccountCard({
  account,
  loading,
  onClick,
}: {
  account: PublicQuotaAccount;
  loading?: boolean;
  onClick?: () => void;
}) {
  return (
    <Card className={onClick ? "cursor-pointer transition-shadow hover:shadow-md" : ""} onClick={onClick}>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{account.name}</CardTitle>
            <CardDescription className="mt-1">OpenCode Go</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {!loading && account.stale && <Badge variant="warning">缓存已陈旧</Badge>}
            <Badge variant={loading ? "default" : account.success ? "success" : "danger"}>
              {loading ? "加载中" : account.success ? "正常" : "异常"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <QuotaLoadingSkeleton rows={3} />
        ) : (
          <>
            {!account.success && account.error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {account.error}
              </div>
            )}
            {account.windows?.length ? (
              <OpenCodeQuotaWindows windows={account.windows} />
            ) : null}
            {account.updated_at && (
              <p className="text-[11px] text-muted-foreground">
                更新于 {new Date(account.updated_at).toLocaleString("zh-CN")}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function CPAAccountCard({ account }: { account: CPAQuotaAccount }) {
  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{account.account}</CardTitle>
            <CardDescription className="mt-1">CLIProxyAPI</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="default">{account.plan}</Badge>
            {account.stale && <Badge variant="warning">缓存已陈旧</Badge>}
            <Badge variant={account.success ? "success" : "danger"}>
              {account.success ? "正常" : "异常"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!account.success && account.error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {account.error}
          </div>
        )}
        {account.windows.map((window) => (
          <QuotaWindowRow key={window.label} window={window} />
        ))}
        {account.updated_at && (
          <p className="text-[11px] text-muted-foreground">
            最近成功采集于 {new Date(account.updated_at).toLocaleString("zh-CN")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
