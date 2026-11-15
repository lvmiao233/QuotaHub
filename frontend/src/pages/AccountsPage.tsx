import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Pencil, Plus, Trash2, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type MistralAccount, type OllamaAccount, type OpenCodeAccount } from "@/lib/api";

type Tab = "ollama" | "opencode" | "mistral";

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
  const [workspaceId, setWorkspaceId] = useState(initial?.workspace_id || "");
  const [authCookie, setAuthCookie] = useState(initial?.auth_cookie || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        name,
        workspace_id: workspaceId,
        show_rolling: initial?.show_rolling ?? true,
        show_weekly: initial?.show_weekly ?? true,
        show_monthly: initial?.show_monthly ?? true,
        enabled: initial?.enabled ?? true,
      };
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
          <Label htmlFor="oc-ws">组织 ID（wrk_…）</Label>
          <Input
            id="oc-ws"
            value={workspaceId}
            onChange={(e) => setWorkspaceId(e.target.value)}
            placeholder="wrk_01KE6TCEZM2BRT6XWCR3K7TADE"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="oc-cookie">Console Cookie{initial?.id ? "（留空则不修改）" : ""}</Label>
          <Textarea
            id="oc-cookie"
            value={authCookie}
            onChange={(e) => setAuthCookie(e.target.value)}
            placeholder="__Host-console_session=st_…（可附带 auth=…）"
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
      const payload: Record<string, unknown> = {
        name,
        show_session: initial?.show_session ?? true,
        show_weekly: initial?.show_weekly ?? true,
        enabled: initial?.enabled ?? true,
      };
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

function MistralForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<MistralAccount> & { api_key?: string };
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name || "");
  const [apiKey, setApiKey] = useState(initial?.api_key || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      if (!initial?.id && !apiKey.trim()) {
        throw new Error("请填写 API Key");
      }
      const payload: Record<string, unknown> = {
        name,
        show_monthly: initial?.show_monthly ?? true,
        enabled: initial?.enabled ?? true,
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
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
        <CardTitle className="text-base">{initial?.id ? "编辑 Mistral 账号" : "添加 Mistral 账号"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="mi-name">名称</Label>
          <Input id="mi-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="mi-key">Mistral API Key{initial?.id ? "（留空则不修改）" : ""}</Label>
          <Input
            id="mi-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="console.mistral.ai 创建，需有组织用量权限"
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

export default function AccountsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("ollama");
  const [openCodeAccounts, setOpenCodeAccounts] = useState<OpenCodeAccount[]>([]);
  const [ollamaAccounts, setOllamaAccounts] = useState<OllamaAccount[]>([]);
  const [mistralAccounts, setMistralAccounts] = useState<MistralAccount[]>([]);
  const [editingOpenCode, setEditingOpenCode] = useState<OpenCodeAccount | "new" | null>(null);
  const [editingOllama, setEditingOllama] = useState<OllamaAccount | "new" | null>(null);
  const [editingMistral, setEditingMistral] = useState<MistralAccount | "new" | null>(null);

  const load = useCallback(async () => {
    const cfg = await api.config();
    setOpenCodeAccounts(cfg.opencode_accounts);
    setOllamaAccounts(cfg.ollama_accounts);
    setMistralAccounts(cfg.mistral_accounts ?? []);
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

  const deleteMistral = async (id: string) => {
    if (!confirm("确定删除该账号？")) return;
    await api.deleteMistralAccount(id);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs>
          <TabsList>
            <TabsTrigger active={tab === "ollama"} onClick={() => setTab("ollama")}>
              Ollama
            </TabsTrigger>
            <TabsTrigger active={tab === "opencode"} onClick={() => setTab("opencode")}>
              OpenCode Go
            </TabsTrigger>
            <TabsTrigger active={tab === "mistral"} onClick={() => setTab("mistral")}>
              Mistral
            </TabsTrigger>
          </TabsList>
        </Tabs>
        {!editingOllama && tab === "ollama" && (
          <Button size="sm" onClick={() => setEditingOllama("new")}>
            <Plus className="h-4 w-4" />
            添加账号
          </Button>
        )}
        {!editingOpenCode && tab === "opencode" && (
          <Button size="sm" onClick={() => setEditingOpenCode("new")}>
            <Plus className="h-4 w-4" />
            添加账号
          </Button>
        )}
        {!editingMistral && tab === "mistral" && (
          <Button size="sm" onClick={() => setEditingMistral("new")}>
            <Plus className="h-4 w-4" />
            添加账号
          </Button>
        )}
      </div>

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
                    <Badge variant={account.enabled ? "success" : "warning"}>
                      {account.enabled ? "启用" : "停用"}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/accounts/opencode/${account.id}`)}
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

      {tab === "mistral" && (
        <div className="space-y-4">
          {editingMistral && (
            <MistralForm
              initial={editingMistral === "new" ? undefined : editingMistral}
              onSave={async (data) => {
                if (editingMistral === "new") {
                  await api.createMistralAccount(data);
                } else {
                  await api.updateMistralAccount(editingMistral.id, data);
                }
                setEditingMistral(null);
                await load();
              }}
              onCancel={() => setEditingMistral(null)}
            />
          )}
          <div className="grid gap-3">
            {mistralAccounts.map((account) => (
              <Card key={account.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div>
                    <p className="font-medium">{account.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {account.api_key_masked || "未配置 API Key"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={account.enabled ? "success" : "warning"}>
                      {account.enabled ? "启用" : "停用"}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={() => setEditingMistral(account)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void deleteMistral(account.id)}>
                      <Trash2 className="h-4 w-4 text-rose-600" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
