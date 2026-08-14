import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { UsagePagination } from "@/components/usage/UsagePagination";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type UsageListResponse } from "@/lib/api";
import { useUsagePageSize } from "@/lib/usage-pagination";

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function formatSyncTime(iso: string | null): string {
  if (!iso) return "从未同步";
  return new Date(iso).toLocaleString("zh-CN");
}

export function UsageTable({ accountId }: { accountId: string }) {
  const [data, setData] = useState<UsageListResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [keyId, setKeyId] = useState("");
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [error, setError] = useState("");
  const [pageSize, setPageSize] = useUsagePageSize();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.listUsage(accountId, {
        offset,
        limit: pageSize,
        key_id: keyId || undefined,
      });
      setData(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [accountId, offset, keyId, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  const sync = async () => {
    setSyncing(true);
    setError("");
    try {
      await api.syncUsage(accountId);
      setOffset(0);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  };

  const backfill = async () => {
    setBackfilling(true);
    setError("");
    try {
      await api.backfillUsage(accountId, 5);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBackfilling(false);
    }
  };

  const syncInfo = data?.sync;
  const total = data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          本地 {total} 条
          {syncInfo?.last_sync_at && <> · 同步于 {formatSyncTime(syncInfo.last_sync_at)}</>}
          {syncInfo?.last_sync_status === "error" && syncInfo.last_sync_error && (
            <span className="ml-2 text-rose-600">{syncInfo.last_sync_error}</span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {data?.key_ids && data.key_ids.length > 1 && (
            <Select
              value={keyId || "__all__"}
              onValueChange={(value) => {
                setKeyId(value === "__all__" ? "" : value);
                setOffset(0);
              }}
            >
              <SelectTrigger className="h-9 w-[12rem]">
                <SelectValue placeholder="全部 Key" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">全部 Key</SelectItem>
                {data.key_ids.map((k) => (
                  <SelectItem key={k} value={k}>
                    {k}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" size="sm" onClick={() => void sync()} disabled={syncing}>
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            同步
          </Button>
          <Button variant="outline" size="sm" onClick={() => void backfill()} disabled={backfilling}>
            {backfilling ? "拉取中…" : "拉取更早"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>时间</TableHead>
            <TableHead>模型</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead className="text-right">Input</TableHead>
            <TableHead className="text-right">Output</TableHead>
            <TableHead className="text-right">费用</TableHead>
            <TableHead>Key</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading && !data?.records.length ? (
            <TableRow>
              <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                加载中…
              </TableCell>
            </TableRow>
          ) : data?.records.length ? (
            data.records.map((row) => (
              <TableRow key={row.usg_id}>
                <TableCell className="whitespace-nowrap text-xs">
                  {new Date(row.created_at).toLocaleString("zh-CN")}
                </TableCell>
                <TableCell>{row.model}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{row.provider || "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{row.input_tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">{row.output_tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">{formatCost(row.cost_usd)}</TableCell>
                <TableCell className="font-mono text-[10px] text-muted-foreground">
                  {row.key_id?.slice(0, 16)}…
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                暂无记录，点击「同步」或「拉取更早」
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <UsagePagination
        total={total}
        offset={offset}
        pageSize={pageSize}
        loading={loading}
        onOffsetChange={setOffset}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setOffset(0);
        }}
      />
    </div>
  );
}
