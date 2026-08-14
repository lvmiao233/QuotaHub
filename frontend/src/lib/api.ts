export interface RefreshSettings {
  auto_refresh: boolean;
  interval_sec: number;
}

export interface QuotaSyncSettings {
  auto_sync: boolean;
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

export interface AppConfigResponse {
  refresh: {
    ollama: RefreshSettings;
    opencode_go: RefreshSettings;
  };
  quota_sync: {
    ollama: QuotaSyncSettings;
    opencode_go: QuotaSyncSettings;
  };
  usage_sync: UsageSyncSettings;
  accounts_imported: boolean;
  opencode_accounts: OpenCodeAccount[];
  ollama_accounts: OllamaAccount[];
}

export interface QuotaWindow {
  label: string;
  used: number;
  remaining: number;
  total: number;
  unit: string;
  reset_at: string;
  reset_in_sec: number;
  duration_sec?: number;
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

export interface PublicQuotaAccount {
  index: number;
  public_id: string;
  name: string;
  success: boolean;
  stale?: boolean;
  updated_at: string;
  last_attempt_at?: string | null;
  windows?: QuotaWindow[];
  error?: string;
}

export interface OllamaQuotaAccount extends PublicQuotaAccount {
  plan?: string;
}

export interface AdminQuotaAccount extends PublicQuotaAccount {
  account_id: string;
  enabled: boolean;
}

export interface CPAQuotaAccount {
  public_id: string;
  account: string;
  plan: string;
  success: boolean;
  stale: boolean;
  updated_at: string;
  last_attempt_at?: string | null;
  quota_source?: "response_header" | "active_api";
  observed_at?: string;
  windows: QuotaWindow[];
  error?: string;
}

export interface PublicCPAChannel {
  public_id: string;
  name: string;
  success: boolean;
  stale: boolean;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
  error?: string;
  accounts: CPAQuotaAccount[];
}

export interface AdminCPAChannel extends PublicCPAChannel {
  id: string;
  url: string;
  enabled: boolean;
  interval_sec: number;
  created_at: string;
  updated_at: string;
}

export interface PublicQuotaResponse {
  opencode: PublicQuotaAccount[];
  ollama: OllamaQuotaAccount[];
  cpa_channels: PublicCPAChannel[];
}

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
    public_id: string;
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
    public_id: string;
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
  cpa: {
    channel_count: number;
    account_count: number;
    success_count: number;
    stale_count: number;
    plans: Record<string, number>;
  };
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
  };
  quota_sync?: {
    ollama?: Partial<QuotaSyncSettings>;
    opencode_go?: Partial<QuotaSyncSettings>;
  };
  usage_sync?: Partial<UsageSyncSettings>;
}

function cookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) return decodeURIComponent(item.slice(prefix.length));
  }
  return "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const method = (init?.method || "GET").toUpperCase();
  if (path.startsWith("/api/admin/") && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("quotahub_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const resp = await fetch(path, { ...init, headers, credentials: "same-origin" });
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
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  publicQuota: () => request<PublicQuotaResponse>("/api/public/quota"),
  analyticsOverview: () => request<AnalyticsOverviewResponse>("/api/public/overview"),
  opencodeDailyStats: (days = 30) =>
    request<{ days: number; stats: DailyStat[] }>(`/api/public/analytics/opencode/daily?days=${days}`),
  opencodeDailyModelStats: (days = 30) =>
    request<{ days: number; stats: DailyModelStat[] }>(
      `/api/public/analytics/opencode/daily/models?days=${days}`
    ),
  health: () => request<{ status: string }>("/api/health"),

  adminLogin: (token: string) =>
    request<{ authenticated: boolean; csrf_token: string }>("/api/admin/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }),
  adminSession: () => request<{ authenticated: boolean }>("/api/admin/auth/session"),
  adminLogout: () => request<{ ok: boolean }>("/api/admin/auth/logout", { method: "POST" }),

  config: () => request<AppConfigResponse>("/api/admin/config"),
  updateConfig: (body: ServiceConfigUpdateBody) =>
    request<AppConfigResponse>("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listAllUsage: (params?: { offset?: number; limit?: number; account_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.offset != null) query.set("offset", String(params.offset));
    if (params?.limit != null) query.set("limit", String(params.limit));
    if (params?.account_id) query.set("account_id", params.account_id);
    const qs = query.toString();
    return request<AllUsageListResponse>(`/api/admin/usage/all${qs ? `?${qs}` : ""}`);
  },

  listOpenCodeAccounts: () => request<OpenCodeAccount[]>("/api/admin/accounts/opencode"),
  createOpenCodeAccount: (body: Record<string, unknown>) =>
    request<OpenCodeAccount>("/api/admin/accounts/opencode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateOpenCodeAccount: (id: string, body: Record<string, unknown>) =>
    request<OpenCodeAccount>(`/api/admin/accounts/opencode/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteOpenCodeAccount: (id: string) =>
    request<{ ok: boolean }>(`/api/admin/accounts/opencode/${id}`, { method: "DELETE" }),
  testOpenCodeAccount: (id: string) =>
    request<{ success: boolean; workspace_id?: string; error?: string }>(
      `/api/admin/accounts/opencode/${id}/test`,
      { method: "POST" }
    ),
  openCodeQuota: (id: string) =>
    request<AdminQuotaAccount>(`/api/admin/accounts/opencode/${id}/quota`),
  listUsage: (id: string, params?: { offset?: number; limit?: number; key_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.offset != null) query.set("offset", String(params.offset));
    if (params?.limit != null) query.set("limit", String(params.limit));
    if (params?.key_id) query.set("key_id", params.key_id);
    const qs = query.toString();
    return request<UsageListResponse>(
      `/api/admin/accounts/opencode/${id}/usage${qs ? `?${qs}` : ""}`
    );
  },
  syncUsage: (id: string) =>
    request<SyncResult>(`/api/admin/accounts/opencode/${id}/usage/sync`, { method: "POST" }),
  backfillUsage: (id: string, pages = 5) =>
    request<SyncResult>(`/api/admin/accounts/opencode/${id}/usage/backfill?pages=${pages}`, {
      method: "POST",
    }),

  listOllamaAccounts: () => request<OllamaAccount[]>("/api/admin/accounts/ollama"),
  createOllamaAccount: (body: Record<string, unknown>) =>
    request<OllamaAccount>("/api/admin/accounts/ollama", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateOllamaAccount: (id: string, body: Record<string, unknown>) =>
    request<OllamaAccount>(`/api/admin/accounts/ollama/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteOllamaAccount: (id: string) =>
    request<{ ok: boolean }>(`/api/admin/accounts/ollama/${id}`, { method: "DELETE" }),

  listCPAChannels: () => request<AdminCPAChannel[]>("/api/admin/cpa/channels"),
  createCPAChannel: (body: Record<string, unknown>) =>
    request<AdminCPAChannel>("/api/admin/cpa/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateCPAChannel: (id: string, body: Record<string, unknown>) =>
    request<AdminCPAChannel>(`/api/admin/cpa/channels/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteCPAChannel: (id: string) =>
    request<{ ok: boolean }>(`/api/admin/cpa/channels/${id}`, { method: "DELETE" }),
};
