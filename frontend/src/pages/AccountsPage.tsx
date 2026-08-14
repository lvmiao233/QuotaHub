import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Network, Pencil, Plus, Trash2, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuotaWindowRow } from "@/components/quota/QuotaCards";
import { api, type AdminCPAChannel, type OllamaAccount, type OpenCodeAccount } from "@/lib/api";

type Tab = "opencode" | "ollama" | "cpa";

function OpenCodeForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<OpenCodeAccount> & { auth_cookie?: string };
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name || "");
  const [workspaceId, setWorkspaceId] = useState(initial?.workspace_id || "Default");
  const [authCookie, setAuthCookie] = useState(initial?.auth_cookie || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      if (!initial?.id || name.trim() !== initial.name) payload.name = name;
      if (!initial?.id || workspaceId.trim() !== initial.workspace_id) {
        payload.workspace_id = workspaceId;
      }
      if (authCookie.trim()) payload.auth_cookie = authCookie.trim();
      await onSave(payload);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{initial?.id ? "编辑 OpenCode 账号" : "添加 OpenCode 账号"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="oc-name">名称</Label>
          <Input id="oc-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="oc-ws">工作区 ID / 名称</Label>
          <Input id="oc-ws" value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="oc-cookie">auth Cookie{initial?.id ? "（留空则不修改）" : ""}</Label>
          <Textarea
            id="oc-cookie"
            value={authCookie}
            onChange={(e) => setAuthCookie(e.target.value)}
            placeholder="auth=Fe26.2**..."
          />
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex gap-2">
          <Button onClick={() => void submit()} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
          <Button variant="outline" onClick={onCancel}>
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function OllamaForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<OllamaAccount> & { session_cookie?: string };
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name || "");
  const [sessionCookie, setSessionCookie] = useState(initial?.session_cookie || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      if (!initial?.id || name.trim() !== initial.name) payload.name = name;
      if (sessionCookie.trim()) payload.session_cookie = sessionCookie.trim();
      await onSave(payload);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{initial?.id ? "编辑 Ollama 账号" : "添加 Ollama 账号"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="ol-name">名称</Label>
          <Input id="ol-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="ol-cookie">session Cookie{initial?.id ? "（留空则不修改）" : ""}</Label>
          <Textarea
            id="ol-cookie"
            value={sessionCookie}
            onChange={(e) => setSessionCookie(e.target.value)}
            placeholder="aid=...; __Secure-session=..."
          />
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex gap-2">
          <Button onClick={() => void submit()} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
          <Button variant="outline" onClick={onCancel}>
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function CPAChannelForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: AdminCPAChannel;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name || "");
  const [url, setUrl] = useState(initial?.url || "");
  const [managementKey, setManagementKey] = useState("");
  const [intervalSec, setIntervalSec] = useState(initial?.interval_sec || 1800);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const normalizedInterval = Math.max(300, intervalSec);
      const payload: Record<string, unknown> = {};
      if (!initial || name.trim() !== initial.name) payload.name = name;
      if (!initial || url.trim() !== initial.url) payload.url = url;
      if (!initial || normalizedInterval !== initial.interval_sec) {
        payload.interval_sec = normalizedInterval;
      }
      if (managementKey.trim()) payload.management_key = managementKey.trim();
      await onSave(payload);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{initial ? "编辑 CPA 渠道" : "添加 CPA 渠道"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="cpa-name">渠道名称</Label>
          <Input id="cpa-name" value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cpa-url">CLIProxyAPI URL</Label>
          <Input
            id="cpa-url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://proxy.example.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cpa-key">管理密钥{initial ? "（留空则不修改）" : ""}</Label>
          <Input
            id="cpa-key"
            type="password"
            value={managementKey}
            onChange={(event) => setManagementKey(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">密钥仅提交给 QuotaHub 后端，不会回传到浏览器。</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="cpa-interval">采集间隔（秒，最短 300）</Label>
          <Input
            id="cpa-interval"
            type="number"
            min={300}
            value={intervalSec}
            onChange={(event) => setIntervalSec(Number(event.target.value))}
          />
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex gap-2">
          <Button
            disabled={saving || !name.trim() || !url.trim() || (!initial && !managementKey.trim())}
            onClick={() => void submit()}
          >
            {saving ? "保存中…" : "保存"}
          </Button>
          <Button variant="outline" onClick={onCancel}>取消</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AccountsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("opencode");
  const [openCodeAccounts, setOpenCodeAccounts] = useState<OpenCodeAccount[]>([]);
  const [ollamaAccounts, setOllamaAccounts] = useState<OllamaAccount[]>([]);
  const [cpaChannels, setCpaChannels] = useState<AdminCPAChannel[]>([]);
  const [editingOpenCode, setEditingOpenCode] = useState<OpenCodeAccount | "new" | null>(null);
  const [editingOllama, setEditingOllama] = useState<OllamaAccount | "new" | null>(null);
  const [editingCPA, setEditingCPA] = useState<AdminCPAChannel | "new" | null>(null);

  const load = useCallback(async () => {
    const [cfg, channels] = await Promise.all([api.config(), api.listCPAChannels()]);
    setOpenCodeAccounts(cfg.opencode_accounts);
    setOllamaAccounts(cfg.ollama_accounts);
    setCpaChannels(channels);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const deleteOpenCode = async (id: string) => {
    if (!confirm("确定删除该账号？")) return;
    await api.deleteOpenCodeAccount(id);
    await load();
  };

  const deleteOllama = async (id: string) => {
    if (!confirm("确定删除该账号？")) return;
    await api.deleteOllamaAccount(id);
    await load();
  };

  const deleteCPA = async (id: string) => {
    if (!confirm("确定删除该 CPA 渠道及其额度快照？")) return;
    await api.deleteCPAChannel(id);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs>
          <TabsList>
            <TabsTrigger active={tab === "opencode"} onClick={() => setTab("opencode")}>
              OpenCode Go
            </TabsTrigger>
            <TabsTrigger active={tab === "ollama"} onClick={() => setTab("ollama")}>
              Ollama
            </TabsTrigger>
            <TabsTrigger active={tab === "cpa"} onClick={() => setTab("cpa")}>
              CPA / CLIProxyAPI
            </TabsTrigger>
          </TabsList>
        </Tabs>
        {!editingOpenCode && tab === "opencode" && (
          <Button size="sm" onClick={() => setEditingOpenCode("new")}>
            <Plus className="h-4 w-4" />
            添加账号
          </Button>
        )}
        {!editingOllama && tab === "ollama" && (
          <Button size="sm" onClick={() => setEditingOllama("new")}>
            <Plus className="h-4 w-4" />
            添加账号
          </Button>
        )}
        {!editingCPA && tab === "cpa" && (
          <Button size="sm" onClick={() => setEditingCPA("new")}>
            <Plus className="h-4 w-4" />
            添加渠道
          </Button>
        )}
      </div>

      {tab === "opencode" && (
        <div className="space-y-4">
          {editingOpenCode && (
            <OpenCodeForm
              initial={editingOpenCode === "new" ? undefined : editingOpenCode}
              onSave={async (data) => {
                if (editingOpenCode === "new") {
                  await api.createOpenCodeAccount(data);
                } else {
                  await api.updateOpenCodeAccount(editingOpenCode.id, data);
                }
                setEditingOpenCode(null);
                await load();
              }}
              onCancel={() => setEditingOpenCode(null)}
            />
          )}
          <div className="grid gap-3">
            {openCodeAccounts.map((account) => (
              <Card key={account.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div className="flex items-center gap-3">
                    <Waves className="h-5 w-5 text-slate-500" />
                    <div>
                      <p className="font-medium">{account.name}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {account.resolved_workspace_id || account.workspace_id}
                      </p>
                      <p className="text-xs text-muted-foreground">{account.auth_cookie_masked}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={account.enabled}
                      onCheckedChange={(enabled) =>
                        void api.updateOpenCodeAccount(account.id, { enabled }).then(load)
                      }
                    />
                    <Badge variant={account.enabled ? "success" : "warning"}>
                      {account.enabled ? "启用" : "停用"}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/admin/accounts/opencode/${account.id}`)}
                    >
                      详情
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setEditingOpenCode(account)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void deleteOpenCode(account.id)}>
                      <Trash2 className="h-4 w-4 text-rose-600" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {tab === "ollama" && (
        <div className="space-y-4">
          {editingOllama && (
            <OllamaForm
              initial={editingOllama === "new" ? undefined : editingOllama}
              onSave={async (data) => {
                if (editingOllama === "new") {
                  await api.createOllamaAccount(data);
                } else {
                  await api.updateOllamaAccount(editingOllama.id, data);
                }
                setEditingOllama(null);
                await load();
              }}
              onCancel={() => setEditingOllama(null)}
            />
          )}
          <div className="grid gap-3">
            {ollamaAccounts.map((account) => (
              <Card key={account.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div>
                    <p className="font-medium">{account.name}</p>
                    <p className="text-xs text-muted-foreground">{account.session_cookie_masked}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={account.enabled}
                      onCheckedChange={(enabled) =>
                        void api.updateOllamaAccount(account.id, { enabled }).then(load)
                      }
                    />
                    <Badge variant={account.enabled ? "success" : "warning"}>
                      {account.enabled ? "启用" : "停用"}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={() => setEditingOllama(account)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void deleteOllama(account.id)}>
                      <Trash2 className="h-4 w-4 text-rose-600" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {tab === "cpa" && (
        <div className="space-y-4">
          {editingCPA && (
            <CPAChannelForm
              initial={editingCPA === "new" ? undefined : editingCPA}
              onSave={async (data) => {
                if (editingCPA === "new") {
                  await api.createCPAChannel(data);
                } else {
                  await api.updateCPAChannel(editingCPA.id, data);
                }
                setEditingCPA(null);
                await load();
              }}
              onCancel={() => setEditingCPA(null)}
            />
          )}
          <div className="grid gap-4">
            {cpaChannels.map((channel) => (
              <Card key={channel.id}>
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <Network className="mt-0.5 h-5 w-5 text-slate-500" />
                      <div>
                        <CardTitle className="text-base">{channel.name}</CardTitle>
                        <p className="mt-1 text-xs text-muted-foreground">{channel.url}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          每 {Math.round(channel.interval_sec / 60)} 分钟采集 · {channel.accounts.length} 个账号
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={channel.enabled}
                        onCheckedChange={(enabled) =>
                          void api.updateCPAChannel(channel.id, { enabled }).then(load)
                        }
                      />
                      <Badge variant={channel.enabled ? "success" : "warning"}>
                        {channel.enabled ? "启用" : "停用"}
                      </Badge>
                      {channel.stale && <Badge variant="warning">陈旧</Badge>}
                      <Button variant="outline" size="sm" onClick={() => setEditingCPA(channel)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => void deleteCPA(channel.id)}>
                        <Trash2 className="h-4 w-4 text-rose-600" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {channel.error && !channel.success && (
                    <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {channel.error}
                    </p>
                  )}
                  {channel.accounts.length ? (
                    <div className="grid gap-2 md:grid-cols-2">
                      {channel.accounts.map((account) => (
                        <div key={account.public_id} className="space-y-3 rounded-xl border border-slate-200 p-3 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-medium">{account.account}</span>
                            <div className="flex items-center gap-2">
                              <Badge variant="default">{account.plan}</Badge>
                              {account.stale && <Badge variant="warning">陈旧</Badge>}
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {account.success ? "额度缓存正常" : account.error || "等待首次采集"}
                          </p>
                          {account.windows.length > 0 && (
                            <div className="space-y-3 border-t border-slate-100 pt-3">
                              {account.windows.map((window) => (
                                <QuotaWindowRow key={window.label} window={window} />
                              ))}
                            </div>
                          )}
                          {account.updated_at && (
                            <p className="text-[11px] text-muted-foreground">
                              最近成功采集于 {new Date(account.updated_at).toLocaleString("zh-CN")}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">等待后台发现 Codex 账号。</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
