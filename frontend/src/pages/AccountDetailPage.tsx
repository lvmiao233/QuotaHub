import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { QuotaWindowRow, QuotaLoadingSkeleton } from "@/components/quota/QuotaCards";
import { UsageTable } from "@/components/usage/UsageTable";
import { applyOpenCodeCascade } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type AdminQuotaAccount, type OpenCodeAccount } from "@/lib/api";

type DetailTab = "quota" | "usage";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<DetailTab>("quota");
  const [account, setAccount] = useState<OpenCodeAccount | null>(null);
  const [quota, setQuota] = useState<AdminQuotaAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAccount = useCallback(async () => {
    if (!id) return;
    const accounts = await api.listOpenCodeAccounts();
    setAccount(accounts.find((a) => a.id === id) || null);
  }, [id]);

  const refreshQuota = useCallback(async () => {
    if (!id) return;
    setQuotaLoading(true);
    try {
      setQuota(await api.openCodeQuota(id));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setQuotaLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      setLoading(true);
      try {
        await loadAccount();
        await refreshQuota();
      } finally {
        setLoading(false);
      }
    })();
  }, [id, loadAccount, refreshQuota]);

  if (!id) {
    return <p className="text-sm text-rose-600">无效账号 ID</p>;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <RefreshCw className="mr-2 h-5 w-5 animate-spin" />
        加载中…
      </div>
    );
  }

  if (!account) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-rose-600">账号不存在</p>
        <Link to="/admin/accounts" className="text-sm text-cyan-700 underline">
          返回账号列表
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" asChild>
          <Link to="/admin/accounts">
            <ArrowLeft className="h-4 w-4" />
            返回
          </Link>
        </Button>
        <div>
          <h2 className="text-lg font-semibold text-slate-800">{account.name}</h2>
          <p className="font-mono text-xs text-muted-foreground">
            {account.resolved_workspace_id || account.workspace_id}
          </p>
        </div>
        <Badge variant={account.enabled ? "success" : "warning"}>
          {account.enabled ? "启用" : "停用"}
        </Badge>
      </div>

      <Tabs>
        <TabsList>
          <TabsTrigger active={tab === "quota"} onClick={() => setTab("quota")}>
            额度
          </TabsTrigger>
          <TabsTrigger active={tab === "usage"} onClick={() => setTab("usage")}>
            使用记录
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "quota" && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between">
            <div>
              <CardTitle className="text-base">缓存额度</CardTitle>
            </div>
            <Button
              variant="outline"
              size="sm"
              title="重新读取后端快照，不触发上游采集"
              onClick={() => void refreshQuota()}
              disabled={quotaLoading}
            >
              <RefreshCw className={`h-4 w-4 ${quotaLoading ? "animate-spin" : ""}`} />
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
            {quotaLoading && !quota?.windows?.length ? (
              <QuotaLoadingSkeleton rows={3} />
            ) : (
              <>
                {quota?.windows &&
                  applyOpenCodeCascade(quota.windows).map((window) => (
                    <QuotaWindowRow key={window.label} window={window} />
                  ))}
                {quota?.updated_at && (
                  <p className="text-[11px] text-muted-foreground">
                    更新于 {new Date(quota.updated_at).toLocaleString("zh-CN")}
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "usage" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">使用记录</CardTitle>
          </CardHeader>
          <CardContent>
            <UsageTable accountId={id} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
