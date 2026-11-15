import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  placeholderMistralAccounts,
  placeholderOllamaAccounts,
  placeholderOpenGoAccounts,
  type AppConfigResponse,
  type MistralQuotaAccount,
  type OllamaQuotaAccount,
  type QuotaAccount,
  type RefreshSettings,
} from "@/lib/api";
import {
  loadMistralQuotaCache,
  loadOllamaQuotaCache,
  loadOpenCodeQuotaCache,
  saveMistralQuotaCache,
  saveOllamaQuotaCache,
  saveOpenCodeQuotaCache,
} from "@/lib/quota-cache";
import { sortOllamaAccountsByQuota, sortOpenCodeAccountsByQuota } from "@/lib/quota-sort";

const DEFAULT_REFRESH: AppConfigResponse["refresh"] = {
  ollama: { auto_refresh: true, interval_sec: 300 },
  opencode_go: { auto_refresh: true, interval_sec: 60 },
  mistral: { auto_refresh: true, interval_sec: 300 },
};

type QuotaContextValue = {
  ollamaAccounts: OllamaQuotaAccount[];
  mistralAccounts: MistralQuotaAccount[];
  openGoAccounts: QuotaAccount[];
  refreshConfig: AppConfigResponse["refresh"];
  configReady: boolean;
  ollamaLoading: boolean;
  mistralLoading: boolean;
  openGoLoading: boolean;
  ollamaError: string;
  mistralError: string;
  openGoError: string;
  ollamaHasData: boolean;
  mistralHasData: boolean;
  openGoHasData: boolean;
  refreshOllama: () => Promise<void>;
  refreshMistral: () => Promise<void>;
  refreshOpenGo: () => Promise<void>;
  refreshAll: () => Promise<void>;
  reloadRefreshConfig: () => Promise<void>;
};

const QuotaContext = createContext<QuotaContextValue | null>(null);

function sortMistralAccountsByQuota<T extends MistralQuotaAccount>(accounts: T[]): T[] {
  return sortOllamaAccountsByQuota(accounts);
}

export function QuotaProvider({ children }: { children: ReactNode }) {
  const [ollamaAccounts, setOllamaAccounts] = useState<OllamaQuotaAccount[]>(() =>
    sortOllamaAccountsByQuota(loadOllamaQuotaCache<OllamaQuotaAccount>() ?? [])
  );
  const [mistralAccounts, setMistralAccounts] = useState<MistralQuotaAccount[]>(() =>
    sortMistralAccountsByQuota(loadMistralQuotaCache<MistralQuotaAccount>() ?? [])
  );
  const [openGoAccounts, setOpenGoAccounts] = useState<QuotaAccount[]>(() =>
    sortOpenCodeAccountsByQuota(loadOpenCodeQuotaCache<QuotaAccount>() ?? [])
  );
  const [refreshConfig, setRefreshConfig] = useState(DEFAULT_REFRESH);
  const [configReady, setConfigReady] = useState(false);
  const [ollamaLoading, setOllamaLoading] = useState(false);
  const [mistralLoading, setMistralLoading] = useState(false);
  const [openGoLoading, setOpenGoLoading] = useState(false);
  const [ollamaError, setOllamaError] = useState("");
  const [mistralError, setMistralError] = useState("");
  const [openGoError, setOpenGoError] = useState("");

  const ollamaHasData = ollamaAccounts.some((a) => a.updated_at || a.error);
  const mistralHasData = mistralAccounts.some((a) => a.updated_at || a.error);
  const openGoHasData = openGoAccounts.some((a) => a.updated_at || a.error);

  const refreshOllama = useCallback(async () => {
    setOllamaLoading(true);
    try {
      const data = sortOllamaAccountsByQuota(await api.ollamaQuota());
      setOllamaAccounts(data);
      saveOllamaQuotaCache(data);
      setOllamaError("");
    } catch (e) {
      setOllamaError((e as Error).message);
    } finally {
      setOllamaLoading(false);
    }
  }, []);

  const refreshMistral = useCallback(async () => {
    setMistralLoading(true);
    try {
      const data = sortMistralAccountsByQuota(await api.mistralQuota());
      setMistralAccounts(data);
      saveMistralQuotaCache(data);
      setMistralError("");
    } catch (e) {
      setMistralError((e as Error).message);
    } finally {
      setMistralLoading(false);
    }
  }, []);

  const refreshOpenGo = useCallback(async () => {
    setOpenGoLoading(true);
    try {
      const data = sortOpenCodeAccountsByQuota(await api.quota());
      setOpenGoAccounts(data);
      saveOpenCodeQuotaCache(data);
      setOpenGoError("");
    } catch (e) {
      setOpenGoError((e as Error).message);
    } finally {
      setOpenGoLoading(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshOllama(), refreshMistral(), refreshOpenGo()]);
  }, [refreshOllama, refreshMistral, refreshOpenGo]);

  const reloadRefreshConfig = useCallback(async () => {
    try {
      const cfg = await api.config();
      setRefreshConfig(cfg.refresh);
    } catch {
      /* keep current */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cachedOllama = loadOllamaQuotaCache<OllamaQuotaAccount>();
      const cachedMistral = loadMistralQuotaCache<MistralQuotaAccount>();
      const cachedOpenGo = loadOpenCodeQuotaCache<QuotaAccount>();
      try {
        const cfg = await api.config();
        if (cancelled) return;
        setRefreshConfig({
          ...DEFAULT_REFRESH,
          ...cfg.refresh,
          mistral: cfg.refresh.mistral ?? DEFAULT_REFRESH.mistral,
        });
        if (!cachedOllama?.length) {
          setOllamaAccounts(sortOllamaAccountsByQuota(placeholderOllamaAccounts(cfg.ollama_accounts)));
        }
        if (!cachedMistral?.length) {
          setMistralAccounts(sortMistralAccountsByQuota(placeholderMistralAccounts(cfg.mistral_accounts ?? [])));
        }
        if (!cachedOpenGo?.length) {
          setOpenGoAccounts(sortOpenCodeAccountsByQuota(placeholderOpenGoAccounts(cfg.opencode_accounts)));
        }
      } catch {
        if (!cancelled) setRefreshConfig(DEFAULT_REFRESH);
      } finally {
        if (!cancelled) setConfigReady(true);
      }
      if (!cancelled) {
        void refreshAll();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const settings: RefreshSettings = refreshConfig.ollama;
    if (!settings.auto_refresh) return;
    const id = window.setInterval(() => void refreshOllama(), settings.interval_sec * 1000);
    return () => window.clearInterval(id);
  }, [refreshConfig.ollama, refreshOllama]);

  useEffect(() => {
    const settings: RefreshSettings = refreshConfig.mistral ?? DEFAULT_REFRESH.mistral;
    if (!settings.auto_refresh) return;
    const id = window.setInterval(() => void refreshMistral(), settings.interval_sec * 1000);
    return () => window.clearInterval(id);
  }, [refreshConfig.mistral, refreshMistral]);

  useEffect(() => {
    const settings: RefreshSettings = refreshConfig.opencode_go;
    if (!settings.auto_refresh) return;
    const id = window.setInterval(() => void refreshOpenGo(), settings.interval_sec * 1000);
    return () => window.clearInterval(id);
  }, [refreshConfig.opencode_go, refreshOpenGo]);

  const value = useMemo(
    () => ({
      ollamaAccounts,
      mistralAccounts,
      openGoAccounts,
      refreshConfig,
      configReady,
      ollamaLoading,
      mistralLoading,
      openGoLoading,
      ollamaError,
      mistralError,
      openGoError,
      ollamaHasData,
      mistralHasData,
      openGoHasData,
      refreshOllama,
      refreshMistral,
      refreshOpenGo,
      refreshAll,
      reloadRefreshConfig,
    }),
    [
      ollamaAccounts,
      mistralAccounts,
      openGoAccounts,
      refreshConfig,
      configReady,
      ollamaLoading,
      mistralLoading,
      openGoLoading,
      ollamaError,
      mistralError,
      openGoError,
      ollamaHasData,
      mistralHasData,
      openGoHasData,
      refreshOllama,
      refreshMistral,
      refreshOpenGo,
      refreshAll,
      reloadRefreshConfig,
    ]
  );

  return <QuotaContext.Provider value={value}>{children}</QuotaContext.Provider>;
}

export function useQuota() {
  const ctx = useContext(QuotaContext);
  if (!ctx) throw new Error("useQuota must be used within QuotaProvider");
  return ctx;
}