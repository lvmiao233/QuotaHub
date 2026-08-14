import { useCallback, useEffect, useMemo, useState } from "react";
import { LoaderCircle, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { api, type AppConfigResponse, type QuotaSyncSettings, type UsageSyncSettings } from "@/lib/api";
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
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

export default function SettingsPage() {
  const [config, setConfig] = useState<AppConfigResponse | null>(null);
  const [ollama, setOllama] = useState<QuotaSyncSettings>({ auto_sync: true, interval_sec: 1800 });
  const [opencode, setOpencode] = useState<QuotaSyncSettings>({ auto_sync: true, interval_sec: 1800 });
  const [usage, setUsage] = useState<UsageSyncSettings>({
    auto_sync: true,
    interval_sec: 300,
    backfill_pages_per_request: 5,
    max_pages_per_incremental: 10,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const apply = useCallback((next: AppConfigResponse) => {
    setConfig(next);
    setOllama(next.quota_sync.ollama);
    setOpencode(next.quota_sync.opencode_go);
    setUsage(next.usage_sync);
  }, []);

  useEffect(() => {
    void api
      .config()
      .then(apply)
      .catch((error: Error) => showToast(error.message, "error"))
      .finally(() => setLoading(false));
  }, [apply]);

  const quotaChanged = Boolean(
    config &&
      JSON.stringify({ ollama, opencode }) !==
        JSON.stringify({
          ollama: config.quota_sync.ollama,
          opencode: config.quota_sync.opencode_go,
        })
  );
  const usageChanged = Boolean(
    config && JSON.stringify(usage) !== JSON.stringify(config.usage_sync)
  );
  const hasChanges = quotaChanged || usageChanged;
  const validationError = useMemo(() => {
    const validInteger = (value: number) => Number.isInteger(value) && Number.isFinite(value);
    if (
      !validInteger(ollama.interval_sec) ||
      !validInteger(opencode.interval_sec) ||
      ollama.interval_sec < 300 ||
      opencode.interval_sec < 300
    ) {
      return "额度采集间隔不能小于 300 秒";
    }
    if (!validInteger(usage.interval_sec) || usage.interval_sec < 15) {
      return "使用记录同步间隔不能小于 15 秒";
    }
    if (
      !validInteger(usage.backfill_pages_per_request) ||
      usage.backfill_pages_per_request < 1 ||
      usage.backfill_pages_per_request > 50
    ) {
      return "每次补拉页数必须在 1 到 50 之间";
    }
    if (
      !validInteger(usage.max_pages_per_incremental) ||
      usage.max_pages_per_incremental < 1 ||
      usage.max_pages_per_incremental > 100
    ) {
      return "增量同步页数上限必须在 1 到 100 之间";
    }
    return "";
  }, [ollama.interval_sec, opencode.interval_sec, usage]);

  const persist = useCallback(async () => {
    if (saving || !hasChanges || validationError) return;
    setSaving(true);
    try {
      const updated = await api.updateConfig({
        ...(quotaChanged
          ? { quota_sync: { ollama, opencode_go: opencode } }
          : {}),
        ...(usageChanged ? { usage_sync: usage } : {}),
      });
      apply(updated);
      showToast("设置已保存");
    } catch (error) {
      showToast((error as Error).message, "error");
    } finally {
      setSaving(false);
    }
  }, [saving, hasChanges, validationError, quotaChanged, usageChanged, ollama, opencode, usage, apply]);

  if (loading) return <p className="text-sm text-muted-foreground">加载中…</p>;

  return (
    <div className="space-y-6">
      <fieldset disabled={saving} className="space-y-6">
        <Card>
        <CardHeader>
          <CardTitle className="text-base">Ollama 后台额度采集</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="启用后台采集"
            checked={ollama.auto_sync}
            onChange={(auto_sync) => setOllama((previous) => ({ ...previous, auto_sync }))}
          />
          <NumberRow
            label="采集间隔（秒）"
            value={ollama.interval_sec}
            min={300}
            onChange={(interval_sec) =>
              setOllama((previous) => ({ ...previous, interval_sec: Math.max(300, interval_sec) }))
            }
          />
        </CardContent>
        </Card>

        <Card>
        <CardHeader>
          <CardTitle className="text-base">OpenCode Go 后台额度采集</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="启用后台采集"
            checked={opencode.auto_sync}
            onChange={(auto_sync) => setOpencode((previous) => ({ ...previous, auto_sync }))}
          />
          <NumberRow
            label="采集间隔（秒）"
            value={opencode.interval_sec}
            min={300}
            onChange={(interval_sec) =>
              setOpencode((previous) => ({ ...previous, interval_sec: Math.max(300, interval_sec) }))
            }
          />
        </CardContent>
        </Card>

        <Card>
        <CardHeader>
          <CardTitle className="text-base">OpenCode 使用记录同步</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow
            label="自动同步"
            checked={usage.auto_sync}
            onChange={(auto_sync) => setUsage((previous) => ({ ...previous, auto_sync }))}
          />
          <NumberRow
            label="同步间隔（秒）"
            value={usage.interval_sec}
            min={15}
            onChange={(interval_sec) => setUsage((previous) => ({ ...previous, interval_sec }))}
          />
          <NumberRow
            label="每次补拉页数"
            value={usage.backfill_pages_per_request}
            min={1}
            max={50}
            onChange={(backfill_pages_per_request) =>
              setUsage((previous) => ({ ...previous, backfill_pages_per_request }))
            }
          />
          <NumberRow
            label="增量同步页数上限"
            value={usage.max_pages_per_incremental}
            min={1}
            max={100}
            onChange={(max_pages_per_incremental) =>
              setUsage((previous) => ({ ...previous, max_pages_per_incremental }))
            }
          />
        </CardContent>
        </Card>
      </fieldset>

      {validationError && hasChanges && (
        <p className="text-sm text-rose-600">{validationError}</p>
      )}

      <div className="flex justify-end">
        <Button
          type="button"
          onClick={() => void persist()}
          disabled={!config || !hasChanges || Boolean(validationError) || saving}
        >
          {saving ? (
            <LoaderCircle className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          保存设置
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">采集策略说明</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>公开页面和刷新按钮只读取 SQLite 快照，不会直接请求上游。</p>
          <p>CPA 渠道使用各自的采集间隔，在「账号管理」的 CPA 页签中配置。</p>
          <p>已从 config.json 导入账号：{config?.accounts_imported ? "是" : "否"}</p>
        </CardContent>
      </Card>
    </div>
  );
}
