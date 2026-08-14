import { useNavigate } from "react-router-dom";
import { Cloud, Network, RefreshCw, Waves } from "lucide-react";
import {
  CPAAccountCard,
  OllamaAccountCard,
  OpenGoAccountCard,
} from "@/components/quota/QuotaCards";
import { useQuota } from "@/contexts/QuotaContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ReactNode } from "react";

function AccountSection({
  title,
  icon,
  description,
  emptyHint,
  successCount,
  totalCount,
  loading,
  hasData,
  onRefresh,
  children,
}: {
  title: string;
  icon: ReactNode;
  description: string;
  emptyHint: string;
  successCount: number;
  totalCount: number;
  loading: boolean;
  hasData: boolean;
  onRefresh: () => void;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
            {icon}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {totalCount > 0 && hasData && (
            <Badge variant={successCount > 0 ? "success" : "warning"}>
              {successCount}/{totalCount} 账号可用
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading && !hasData}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>
      </div>
      {totalCount > 0 ? (
        children
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">{emptyHint}</CardContent>
        </Card>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const {
    ollamaAccounts,
    openGoAccounts,
    cpaChannels,
    configReady,
    ollamaLoading,
    openGoLoading,
    ollamaHasData,
    openGoHasData,
    ollamaError,
    openGoError,
    refreshOllama,
    refreshOpenGo,
  } = useQuota();

  const cpaAccountCount = cpaChannels.reduce((total, channel) => total + channel.accounts.length, 0);
  const totalCount = ollamaAccounts.length + openGoAccounts.length + cpaAccountCount;
  const isEmpty = configReady && totalCount === 0;

  if (!configReady) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <RefreshCw className="mr-2 h-5 w-5 animate-spin" />
        正在加载…
      </div>
    );
  }

  if (isEmpty) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          暂无账号。请前往
          <button
            type="button"
            className="mx-1 text-cyan-700 underline"
            onClick={() => navigate("/admin/accounts")}
          >
            账号管理
          </button>
          添加，或首次启动时从 config.json 导入。
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-10">
      {(ollamaError || openGoError) && (
        <div className="space-y-2">
          {ollamaError && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              Ollama：{ollamaError}
            </div>
          )}
          {openGoError && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              OpenCode Go：{openGoError}
            </div>
          )}
        </div>
      )}

      <AccountSection
        title="Ollama Cloud"
        icon={<Cloud className="h-4 w-4" />}
        description="5 小时限额 / 周限额"
        emptyHint="未配置 Ollama 账号"
        successCount={ollamaAccounts.filter((a) => a.success).length}
        totalCount={ollamaAccounts.length}
        loading={ollamaLoading}
        hasData={ollamaHasData}
        onRefresh={() => void refreshOllama()}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {ollamaAccounts.map((account) => (
            <OllamaAccountCard
              key={account.public_id}
              account={account}
              loading={ollamaLoading && !ollamaHasData}
            />
          ))}
        </div>
      </AccountSection>

      <AccountSection
        title="CPA / CLIProxyAPI"
        icon={<Network className="h-4 w-4" />}
        description="按渠道展示 Codex 账号套餐与缓存额度"
        emptyHint="未配置可用的 CPA 渠道或账号"
        successCount={cpaChannels.reduce(
          (total, channel) => total + channel.accounts.filter((account) => account.success).length,
          0
        )}
        totalCount={cpaAccountCount}
        loading={openGoLoading}
        hasData={cpaAccountCount > 0}
        onRefresh={() => void refreshOpenGo()}
      >
        <div className="space-y-6">
          {cpaChannels.map((channel) => (
            <div key={channel.public_id} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-medium text-slate-800">{channel.name}</h3>
                </div>
                <div className="flex items-center gap-2">
                  {channel.stale && <Badge variant="warning">渠道缓存已陈旧</Badge>}
                  <Badge variant={channel.success ? "success" : "danger"}>
                    {channel.success ? "同步正常" : "同步异常"}
                  </Badge>
                </div>
              </div>
              {channel.error && !channel.success && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {channel.error}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {channel.accounts.map((account) => (
                  <CPAAccountCard key={account.public_id} account={account} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </AccountSection>

      <AccountSection
        title="OpenCode Go"
        icon={<Waves className="h-4 w-4" />}
        description="5 小时 / 周 / 月额度"
        emptyHint="未配置 OpenCode Go 账号"
        successCount={openGoAccounts.filter((a) => a.success).length}
        totalCount={openGoAccounts.length}
        loading={openGoLoading}
        hasData={openGoHasData}
        onRefresh={() => void refreshOpenGo()}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {openGoAccounts.map((account) => (
            <OpenGoAccountCard
              key={account.public_id}
              account={account}
              loading={openGoLoading && !openGoHasData}
            />
          ))}
        </div>
      </AccountSection>
    </div>
  );
}
