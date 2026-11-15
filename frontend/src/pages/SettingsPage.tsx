import { useCallback, useEffect, useRef, useState } from "react";
import { useQuota } from "@/contexts/QuotaContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { api, type AppConfigResponse, type RefreshSettings, type UsageSyncSettings } from "@/lib/api";
import { showToast } from "@/lib/toast";

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span>{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function NumberRow({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4 text-sm">
      <span>{label}</span>
      <input
        type="number"
        className="h-9 w-28 rounded-lg border border-slate-200 px-2 text-right"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

function settingsSnapshot(
  refreshOllama: RefreshSettings,
  refreshMistral: RefreshSettings,
  refreshOpenGo: RefreshSettings,
  usageSync: UsageSyncSettings
): string {
  return JSON.stringify({ refreshOllama, refreshMistral, refreshOpenGo, usageSync });
}

export default function SettingsPage() {
  const { reloadRefreshConfig } = useQuota();
  const [config, setConfig] = useState<AppConfigResponse | null>(null);
  const [refreshOllama, setRefreshOllama] = useState<RefreshSettings>({ auto_refresh: true, interval_sec: 300 });
  const [refreshMistral, setRefreshMistral] = useState<RefreshSettings>({ auto_refresh: true, interval_sec: 300 });
  const [refreshOpenGo, setRefreshOpenGo] = useState<RefreshSettings>({ auto_refresh: true, interval_sec: 60 });
  const [usageSync, setUsageSync] = useState<UsageSyncSettings>({
    auto_sync: true,
    interval_sec: 300,
    backfill_pages_per_request: 5,
    max_pages_per_incremental: 10,
  });
  const [loading, setLoading] = useState(true);
  const readyRef = useRef(false);
  const lastSavedRef = useRef("");
  const saveTimerRef = useRef<number | undefined>(undefined);
  const savingRef = useRef(false);

  const applyServerConfig = useCallback((cfg: AppConfigResponse) => {
    setConfig(cfg);
    setRefreshOllama(cfg.refresh.ollama);
    setRefreshMistral(cfg.refresh.mistral ?? { auto_refresh: true, interval_sec: 300 });
    setRefreshOpenGo(cfg.refresh.opencode_go);
    setUsageSync(cfg.usage_sync);
    lastSavedRef.current = settingsSnapshot(
      cfg.refresh.ollama,
      cfg.refresh.mistral ?? { auto_refresh: true, interval_sec: 300 },
      cfg.refresh.opencode_go,
      cfg.usage_sync
    );
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await api.config();
      applyServerConfig(cfg);
    } catch (e) {
      showToast((e as Error).message, "error");
    } finally {
      setLoading(false);
      readyRef.current = true;
    }
  }, [applyServerConfig]);

  const persist = useCallback(async () => {
    if (savingRef.current) return;
    const snapshot = settingsSnapshot(refreshOllama, refreshMistral, refreshOpenGo, usageSync);
    if (snapshot === lastSavedRef.current) return;

    savingRef.current = true;
    try {
      const updated = await api.updateConfig({
        refresh: {
          ollama: refreshOllama,
          mistral: refreshMistral,
          opencode_go: refreshOpenGo,
        },
        usage_sync: usageSync,
      });
      applyServerConfig(updated);
      await reloadRefreshConfig();
      showToast("设置已保存");
    } catch (e) {
      showToast((e as Error).message, "error");
    } finally {
      savingRef.current = false;
    }
  }, [refreshOllama, refreshMistral, refreshOpenGo, usageSync, reloadRefreshConfig, applyServerConfig]);

  const scheduleSave = useCallback(() => {
    if (!readyRef.current) return;
    window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      void persist();
    }, 600);
  }, [persist]);

  useEffect(() => {
    void load();
    return () => window.clearTimeout(saveTimerRef.current);
  }, [load]);

  useEffect(() => {
    if (!readyRef.current) return;
    const snapshot = settingsSnapshot(refreshOllama, refreshMistral, refreshOpenGo, usageSync);
    if (snapshot === lastSavedRef.current) return;
    scheduleSave();
  }, [refreshOllama, refreshMistral, refreshOpenGo, usageSync, scheduleSave]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">加载中…</p>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ollama 额度自动刷新</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="自动刷新"
            checked={refreshOllama.auto_refresh}
            onChange={(value) => setRefreshOllama((prev) => ({ ...prev, auto_refresh: value }))}
          />
          <NumberRow
            label="刷新间隔（秒）"
            value={refreshOllama.interval_sec}
            min={15}
            onChange={(value) => setRefreshOllama((prev) => ({ ...prev, interval_sec: value }))}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">OpenCode Go 额度自动刷新</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="自动刷新"
            checked={refreshOpenGo.auto_refresh}
            onChange={(value) => setRefreshOpenGo((prev) => ({ ...prev, auto_refresh: value }))}
          />
          <NumberRow
            label="刷新间隔（秒）"
            value={refreshOpenGo.interval_sec}
            min={15}
            onChange={(value) => setRefreshOpenGo((prev) => ({ ...prev, interval_sec: value }))}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Mistral 额度自动刷新</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="自动刷新"
            checked={refreshMistral.auto_refresh}
            onChange={(value) => setRefreshMistral((prev) => ({ ...prev, auto_refresh: value }))}
          />
          <NumberRow
            label="刷新间隔（秒）"
            value={refreshMistral.interval_sec}
            min={15}
            onChange={(value) => setRefreshMistral((prev) => ({ ...prev, interval_sec: value }))}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">使用记录同步</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="自动同步"
            checked={usageSync.auto_sync}
            onChange={(value) => setUsageSync((prev) => ({ ...prev, auto_sync: value }))}
          />
          <NumberRow
            label="同步间隔（秒）"
            value={usageSync.interval_sec}
            min={15}
            onChange={(value) => setUsageSync((prev) => ({ ...prev, interval_sec: value }))}
          />
          <NumberRow
            label="每次补拉页数"
            value={usageSync.backfill_pages_per_request}
            min={1}
            max={50}
            onChange={(value) => setUsageSync((prev) => ({ ...prev, backfill_pages_per_request: value }))}
          />
          <NumberRow
            label="增量同步页数上限"
            value={usageSync.max_pages_per_incremental}
            min={1}
            max={100}
            onChange={(value) => setUsageSync((prev) => ({ ...prev, max_pages_per_incremental: value }))}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">账号导入</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p>已从 config.json 导入：{config?.accounts_imported ? "是" : "否"}</p>
          <p className="mt-2">导入后请在「账号管理」页面维护账号。</p>
        </CardContent>
      </Card>
    </div>
  );
}
