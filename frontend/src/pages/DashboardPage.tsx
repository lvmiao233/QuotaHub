import { useNavigate } from "react-router-dom";
import { Cloud, RefreshCw, Sparkles, Waves } from "lucide-react";
import {
  MistralAccountCard,
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
    mistralAccounts,
    openGoAccounts,
    configReady,
    ollamaLoading,
    mistralLoading,
    openGoLoading,
    ollamaHasData,
    mistralHasData,
    openGoHasData,
    ollamaError,
    mistralError,
    openGoError,
    refreshOllama,
    refreshMistral,
    refreshOpenGo,
  } = useQuota();

  const totalCount = ollamaAccounts.length + mistralAccounts.length + openGoAccounts.length;
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
            onClick={() => navigate("/accounts")}
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
      {(ollamaError || mistralError || openGoError) && (
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
          {mistralError && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              Mistral：{mistralError}
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
              key={account.account_id || account.name}
              account={account}
              loading={ollamaLoading && !ollamaHasData}
            />
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
              key={account.account_id || account.name}
              account={account}
              loading={openGoLoading && !openGoHasData}
              onClick={
                account.account_id
                  ? () => navigate(`/accounts/opencode/${account.account_id}`)
                  : undefined
              }
            />
          ))}
        </div>
      </AccountSection>

      <AccountSection
        title="Mistral"
        icon={<Sparkles className="h-4 w-4" />}
        description="月额度"
        emptyHint="未配置 Mistral 账号"
        successCount={mistralAccounts.filter((a) => a.success).length}
        totalCount={mistralAccounts.length}
        loading={mistralLoading}
        hasData={mistralHasData}
        onRefresh={() => void refreshMistral()}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {mistralAccounts.map((account) => (
            <MistralAccountCard
              key={account.account_id || account.name}
              account={account}
              loading={mistralLoading && !mistralHasData}
            />
          ))}
        </div>
      </AccountSection>
    </div>
  );
}
