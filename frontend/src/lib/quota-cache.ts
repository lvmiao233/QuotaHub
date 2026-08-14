import type {
  OllamaModelUsage,
  OllamaQuotaAccount,
  PublicQuotaAccount,
  QuotaWindow,
} from "@/lib/api";

const CACHE_PREFIX = "quotahub:v2:cache:";
const OLLAMA_KEY = `${CACHE_PREFIX}ollama-quota`;
const OPENCODE_KEY = `${CACHE_PREFIX}opencode-quota`;
const DAILY_KEY = `${CACHE_PREFIX}daily-stats`;
const DAILY_MODEL_KEY = `${CACHE_PREFIX}daily-model-stats`;
const LEGACY_KEYS = [
  "quotahub:cache:ollama-quota",
  "quotahub:cache:opencode-quota",
  "quotahub:cache:daily-stats",
  "quotahub:cache:daily-model-stats",
];

let legacyRemoved = false;

function storage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

function removeLegacyCache(): void {
  if (legacyRemoved) return;
  legacyRemoved = true;
  try {
    const target = storage();
    LEGACY_KEYS.forEach((key) => target?.removeItem(key));
  } catch {
    /* ignore unavailable storage */
  }
}

function readJson(key: string): unknown {
  removeLegacyCache();
  try {
    const raw = storage()?.getItem(key);
    return raw ? (JSON.parse(raw) as unknown) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  removeLegacyCache();
  try {
    storage()?.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sanitizeModel(value: unknown): OllamaModelUsage | null {
  if (!isRecord(value) || typeof value.model !== "string") return null;
  const requests = numberValue(value.requests);
  if (requests === null) return null;
  const model: OllamaModelUsage = { model: value.model, requests };
  const share = numberValue(value.share_percent);
  if (share !== null) model.share_percent = share;
  if (typeof value.title === "string") model.title = value.title;
  return model;
}

function sanitizeWindow(value: unknown): QuotaWindow | null {
  if (!isRecord(value) || typeof value.label !== "string") return null;
  const used = numberValue(value.used);
  const remaining = numberValue(value.remaining);
  const total = numberValue(value.total);
  const resetIn = numberValue(value.reset_in_sec);
  if (used === null || remaining === null || total === null || resetIn === null) return null;
  const window: QuotaWindow = {
    label: value.label,
    used,
    remaining,
    total,
    unit: typeof value.unit === "string" ? value.unit : "%",
    reset_at: typeof value.reset_at === "string" ? value.reset_at : "",
    reset_in_sec: resetIn,
  };
  const duration = numberValue(value.duration_sec);
  if (duration !== null) window.duration_sec = duration;
  if (typeof value.status_text === "string") window.status_text = value.status_text;
  if (typeof value.blocked === "boolean") window.blocked = value.blocked;
  if (typeof value.blocked_by === "string") window.blocked_by = value.blocked_by;
  const effective = numberValue(value.effective_remaining);
  if (effective !== null) window.effective_remaining = effective;
  if (Array.isArray(value.models)) {
    window.models = value.models.map(sanitizeModel).filter((item) => item !== null);
  }
  return window;
}

function sanitizePublicAccount(value: unknown, index: number): PublicQuotaAccount | null {
  if (
    !isRecord(value) ||
    typeof value.public_id !== "string" ||
    !value.public_id ||
    typeof value.name !== "string" ||
    typeof value.success !== "boolean"
  ) {
    return null;
  }
  const account: PublicQuotaAccount = {
    index: numberValue(value.index) ?? index,
    public_id: value.public_id,
    name: value.name,
    success: value.success,
    stale: value.stale === true,
    updated_at: typeof value.updated_at === "string" ? value.updated_at : "",
    windows: Array.isArray(value.windows)
      ? value.windows.map(sanitizeWindow).filter((item) => item !== null)
      : [],
  };
  if (typeof value.last_attempt_at === "string" || value.last_attempt_at === null) {
    account.last_attempt_at = value.last_attempt_at;
  }
  if (typeof value.error === "string") account.error = value.error;
  return account;
}

function readQuotaCache<T>(
  key: string,
  sanitizer: (value: unknown, index: number) => T | null
): T[] | null {
  const raw = readJson(key);
  if (!Array.isArray(raw)) return null;
  const sanitized = raw.map(sanitizer).filter((item) => item !== null);
  writeJson(key, sanitized);
  return sanitized;
}

export function loadOllamaQuotaCache(): OllamaQuotaAccount[] | null {
  return readQuotaCache(OLLAMA_KEY, (value, index) => {
    const account = sanitizePublicAccount(value, index);
    if (!account) return null;
    return {
      ...account,
      ...(isRecord(value) && typeof value.plan === "string" ? { plan: value.plan } : {}),
    };
  });
}

export function saveOllamaQuotaCache(data: OllamaQuotaAccount[]): void {
  writeJson(
    OLLAMA_KEY,
    data.map((item, index) => loadSafeOllama(item, index)).filter((item) => item !== null)
  );
}

function loadSafeOllama(value: unknown, index: number): OllamaQuotaAccount | null {
  const account = sanitizePublicAccount(value, index);
  if (!account) return null;
  return {
    ...account,
    ...(isRecord(value) && typeof value.plan === "string" ? { plan: value.plan } : {}),
  };
}

export function loadOpenCodeQuotaCache(): PublicQuotaAccount[] | null {
  return readQuotaCache(OPENCODE_KEY, sanitizePublicAccount);
}

export function saveOpenCodeQuotaCache(data: PublicQuotaAccount[]): void {
  writeJson(
    OPENCODE_KEY,
    data.map(sanitizePublicAccount).filter((item) => item !== null)
  );
}

export function loadDailyStatsCache<T>(): T[] | null {
  const value = readJson(DAILY_KEY);
  return Array.isArray(value) ? (value as T[]) : null;
}

export function saveDailyStatsCache(data: unknown[]): void {
  writeJson(DAILY_KEY, data);
}

export function loadDailyModelStatsCache<T>(): T[] | null {
  const value = readJson(DAILY_MODEL_KEY);
  return Array.isArray(value) ? (value as T[]) : null;
}

export function saveDailyModelStatsCache(data: unknown[]): void {
  writeJson(DAILY_MODEL_KEY, data);
}
