export interface RefreshSettings {
  auto_refresh: boolean;
  interval_sec: number;
}

export interface UsageSyncSettings {
  auto_sync: boolean;
  interval_sec: number;
  backfill_pages_per_request: number;
  max_pages_per_incremental: number;
}

export interface OpenCodeAccount {
  id: string;
  name: string;
  workspace_id: string;
  resolved_workspace_id?: string | null;
  auth_cookie_masked: string;
  configured: boolean;
  show_rolling: boolean;
  show_weekly: boolean;
  show_monthly: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface OllamaAccount {
  id: string;
  name: string;
  session_cookie_masked: string;
  configured: boolean;
  show_session: boolean;
  show_weekly: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MistralAccount {
  id: string;
  name: string;
  api_key_masked: string;
  configured: boolean;
  show_monthly: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppConfigResponse {
  refresh: {
    ollama: RefreshSettings;
    opencode_go: RefreshSettings;
    mistral: RefreshSettings;
  };
  usage_sync: UsageSyncSettings;
  accounts_imported: boolean;
  opencode_accounts: OpenCodeAccount[];
  ollama_accounts: OllamaAccount[];
  mistral_accounts: MistralAccount[];
}

export interface QuotaWindow {
  label: string;
  used: number;
  remaining: number;
  total: number;
  unit: string;
  reset_at: string;
  reset_in_sec: number;
  status_text?: string;
  models?: OllamaModelUsage[];
  blocked?: boolean;
  blocked_by?: string;
  effective_remaining?: number;
}

export interface OllamaModelUsage {
  model: string;
  requests: number;
  share_percent?: number;
  title?: string;
}

export interface QuotaAccount {
  index: number;
  name: string;
  account_id?: string;
  workspace_id?: string;
  success: boolean;
  updated_at: string;
  windows?: QuotaWindow[];
  error?: string;
}

export interface OllamaQuotaAccount {
  index: number;
  name: string;
  account_id?: string;
  plan?: string;
  success: boolean;
  updated_at: string;
  windows?: QuotaWindow[];
  error?: string;
}

export type MistralQuotaAccount = OllamaQuotaAccount;

export interface UsageRecord {
  usg_id: string;
  created_at: string;
  model: string;
  provider?: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  key_id?: string | null;
  plan?: string | null;
}

export interface UsageSyncStatus {
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  last_inserted_count: number;
  deepest_page_fetched: number;
  total_records: number;
  oldest_record_at: string | null;
  newest_record_at: string | null;
}

export interface UsageListResponse {
  records: UsageRecord[];
  total: number;
  offset: number;
  limit: number;
  key_ids: string[];
  sync: UsageSyncStatus;
}

export interface SyncResult {
  inserted: number;
  pages_fetched: number;
  sync_at: string;
  error?: string;
}

export interface OllamaOverviewSummary {
  total_remaining_pro: number;
  total_capacity_pro: number;
  account_count: number;
  success_count: number;
  accounts: Array<{
    account_id?: string;
    name: string;
    plan: string;
    multiplier: number;
    remaining_pro: number;
    capacity_pro: number;
    success: boolean;
  }>;
}

export interface OpenCodeOverviewSummary {
  avg_effective_remaining: number;
  account_count: number;
  success_count: number;
  blocked_count: number;
  accounts: Array<{
    account_id?: string;
    name: string;
    success: boolean;
    effective_remaining: number;
    blocked: boolean;
    windows: QuotaWindow[];
  }>;
}

export interface AnalyticsOverviewResponse {
  ollama: OllamaOverviewSummary;
  opencode: OpenCodeOverviewSummary;
  ollama_models: Array<{ model: string; requests: number }>;
}

export interface DailyStat {
  date: string;
  total_cost_usd: number;
  request_count: number;
}

export interface DailyModelStat {
  date: string;
  model: string;
  total_cost_usd: number;
  request_count: number;
}

export interface AllUsageRecord extends UsageRecord {
  account_id: string;
  account_name: string;
}

export interface AllUsageListResponse {
  records: AllUsageRecord[];
  total: number;
  offset: number;
  limit: number;
  accounts: Array<{ id: string; name: string }>;
}

export interface ServiceConfigUpdateBody {
  refresh?: {
    ollama?: Partial<RefreshSettings>;
    opencode_go?: Partial<RefreshSettings>;
    mistral?: Partial<RefreshSettings>;
  };
  usage_sync?: Partial<UsageSyncSettings>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) {
    let detail = await resp.text();
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      detail = parsed.detail || detail;
    } catch {
      /* keep text */
    }
    throw new Error(detail || `请求失败 (${resp.status})`);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return resp.json() as Promise<T>;
}

export const api = {
  quota: () => request<QuotaAccount[]>("/api/quota"),
  ollamaQuota: () => request<OllamaQuotaAccount[]>("/api/ollama/quota"),
  mistralQuota: () => request<MistralQuotaAccount[]>("/api/mistral/quota"),
  config: () => request<AppConfigResponse>("/api/config"),
  updateConfig: (body: ServiceConfigUpdateBody) =>
    request<AppConfigResponse>("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  analyticsOverview: () => request<AnalyticsOverviewResponse>("/api/analytics/overview"),
  opencodeDailyStats: (days = 30) =>
    request<{ days: number; stats: DailyStat[] }>(`/api/analytics/opencode/daily?days=${days}`),
  opencodeDailyModelStats: (days = 30) =>
    request<{ days: number; stats: DailyModelStat[] }>(
      `/api/analytics/opencode/daily/models?days=${days}`
    ),
  listAllUsage: (params?: { offset?: number; limit?: number; account_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.offset != null) query.set("offset", String(params.offset));
    if (params?.limit != null) query.set("limit", String(params.limit));
    if (params?.account_id) query.set("account_id", params.account_id);
    const qs = query.toString();
    return request<AllUsageListResponse>(`/api/usage/all${qs ? `?${qs}` : ""}`);
  },
  health: () => request<{ status: string }>("/api/health"),

  listOpenCodeAccounts: () => request<OpenCodeAccount[]>("/api/accounts/opencode"),
  createOpenCodeAccount: (body: Record<string, unknown>) =>
    request<OpenCodeAccount>("/api/accounts/opencode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateOpenCodeAccount: (id: string, body: Record<string, unknown>) =>
    request<OpenCodeAccount>(`/api/accounts/opencode/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteOpenCodeAccount: (id: string) =>
    request<{ ok: boolean }>(`/api/accounts/opencode/${id}`, { method: "DELETE" }),
  testOpenCodeAccount: (id: string) =>
    request<{ success: boolean; workspace_id?: string; error?: string }>(
      `/api/accounts/opencode/${id}/test`,
      { method: "POST" }
    ),
  openCodeQuota: (id: string) => request<QuotaAccount>(`/api/accounts/opencode/${id}/quota`),
  listUsage: (id: string, params?: { offset?: number; limit?: number; key_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.offset != null) query.set("offset", String(params.offset));
    if (params?.limit != null) query.set("limit", String(params.limit));
    if (params?.key_id) query.set("key_id", params.key_id);
    const qs = query.toString();
    return request<UsageListResponse>(`/api/accounts/opencode/${id}/usage${qs ? `?${qs}` : ""}`);
  },
  syncUsage: (id: string) =>
    request<SyncResult>(`/api/accounts/opencode/${id}/usage/sync`, { method: "POST" }),
  backfillUsage: (id: string, pages = 5) =>
    request<SyncResult>(`/api/accounts/opencode/${id}/usage/backfill?pages=${pages}`, {
      method: "POST",
    }),

  listOllamaAccounts: () => request<OllamaAccount[]>("/api/accounts/ollama"),
  createOllamaAccount: (body: Record<string, unknown>) =>
    request<OllamaAccount>("/api/accounts/ollama", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateOllamaAccount: (id: string, body: Record<string, unknown>) =>
    request<OllamaAccount>(`/api/accounts/ollama/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteOllamaAccount: (id: string) =>
    request<{ ok: boolean }>(`/api/accounts/ollama/${id}`, { method: "DELETE" }),

  listMistralAccounts: () => request<MistralAccount[]>("/api/accounts/mistral"),
  createMistralAccount: (body: Record<string, unknown>) =>
    request<MistralAccount>("/api/accounts/mistral", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateMistralAccount: (id: string, body: Record<string, unknown>) =>
    request<MistralAccount>(`/api/accounts/mistral/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteMistralAccount: (id: string) =>
    request<{ ok: boolean }>(`/api/accounts/mistral/${id}`, { method: "DELETE" }),
};

export function placeholderOpenGoAccounts(accounts: OpenCodeAccount[]): QuotaAccount[] {
  return accounts.map((account, index) => ({
    index,
    account_id: account.id,
    name: account.name,
    workspace_id: account.resolved_workspace_id || account.workspace_id,
    success: false,
    updated_at: "",
  }));
}

export function placeholderOllamaAccounts(accounts: OllamaAccount[]): OllamaQuotaAccount[] {
  return accounts.map((account, index) => ({
    index,
    account_id: account.id,
    name: account.name,
    success: false,
    updated_at: "",
  }));
}

export function placeholderMistralAccounts(accounts: MistralAccount[]): MistralQuotaAccount[] {
  return accounts.map((account, index) => ({
    index,
    account_id: account.id,
    name: account.name,
    success: false,
    updated_at: "",
  }));
}
