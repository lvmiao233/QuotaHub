const OLLAMA_KEY = "quotahub:cache:ollama-quota";
const MISTRAL_KEY = "quotahub:cache:mistral-quota";
const OPENCODE_KEY = "quotahub:cache:opencode-quota";
const DAILY_KEY = "quotahub:cache:daily-stats";
const DAILY_MODEL_KEY = "quotahub:cache:daily-model-stats";

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

export function loadOllamaQuotaCache<T>(): T[] | null {
  return readJson<T[]>(OLLAMA_KEY);
}

export function saveOllamaQuotaCache(data: unknown[]): void {
  writeJson(OLLAMA_KEY, data);
}

export function loadMistralQuotaCache<T>(): T[] | null {
  return readJson<T[]>(MISTRAL_KEY);
}

export function saveMistralQuotaCache(data: unknown[]): void {
  writeJson(MISTRAL_KEY, data);
}

export function loadOpenCodeQuotaCache<T>(): T[] | null {
  return readJson<T[]>(OPENCODE_KEY);
}

export function saveOpenCodeQuotaCache(data: unknown[]): void {
  writeJson(OPENCODE_KEY, data);
}

export function loadDailyStatsCache<T>(): T[] | null {
  return readJson<T[]>(DAILY_KEY);
}

export function saveDailyStatsCache(data: unknown[]): void {
  writeJson(DAILY_KEY, data);
}

export function loadDailyModelStatsCache<T>(): T[] | null {
  return readJson<T[]>(DAILY_MODEL_KEY);
}

export function saveDailyModelStatsCache(data: unknown[]): void {
  writeJson(DAILY_MODEL_KEY, data);
}
