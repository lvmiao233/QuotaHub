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
  type OllamaQuotaAccount,
  type PublicCPAChannel,
  type PublicQuotaAccount,
} from "@/lib/api";
import {
  loadOllamaQuotaCache,
  loadOpenCodeQuotaCache,
  saveOllamaQuotaCache,
  saveOpenCodeQuotaCache,
} from "@/lib/quota-cache";
import { sortOllamaAccountsByQuota, sortOpenCodeAccountsByQuota } from "@/lib/quota-sort";

type QuotaContextValue = {
  ollamaAccounts: OllamaQuotaAccount[];
  openGoAccounts: PublicQuotaAccount[];
  cpaChannels: PublicCPAChannel[];
  configReady: boolean;
  ollamaLoading: boolean;
  openGoLoading: boolean;
  ollamaError: string;
  openGoError: string;
  ollamaHasData: boolean;
  openGoHasData: boolean;
  refreshOllama: () => Promise<void>;
  refreshOpenGo: () => Promise<void>;
  refreshAll: () => Promise<void>;
};

const QuotaContext = createContext<QuotaContextValue | null>(null);

export function QuotaProvider({ children }: { children: ReactNode }) {
  const [ollamaAccounts, setOllamaAccounts] = useState<OllamaQuotaAccount[]>(() =>
    sortOllamaAccountsByQuota(loadOllamaQuotaCache() ?? [])
  );
  const [openGoAccounts, setOpenGoAccounts] = useState<PublicQuotaAccount[]>(() =>
    sortOpenCodeAccountsByQuota(loadOpenCodeQuotaCache() ?? [])
  );
  const [cpaChannels, setCpaChannels] = useState<PublicCPAChannel[]>([]);
  const [configReady, setConfigReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ollamaHasData = ollamaAccounts.some((account) => account.updated_at || account.error);
  const openGoHasData = openGoAccounts.some((account) => account.updated_at || account.error);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.publicQuota();
      const ollama = sortOllamaAccountsByQuota(data.ollama);
      const opencode = sortOpenCodeAccountsByQuota(data.opencode);
      setOllamaAccounts(ollama);
      setOpenGoAccounts(opencode);
      setCpaChannels(data.cpa_channels);
      saveOllamaQuotaCache(ollama);
      saveOpenCodeQuotaCache(opencode);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setConfigReady(true);
    }
  }, []);

  useEffect(() => {
    void refreshAll();
    const id = window.setInterval(() => void refreshAll(), 60_000);
    return () => window.clearInterval(id);
  }, [refreshAll]);

  const value = useMemo(
    () => ({
      ollamaAccounts,
      openGoAccounts,
      cpaChannels,
      configReady,
      ollamaLoading: loading,
      openGoLoading: loading,
      ollamaError: error,
      openGoError: error,
      ollamaHasData,
      openGoHasData,
      refreshOllama: refreshAll,
      refreshOpenGo: refreshAll,
      refreshAll,
    }),
    [
      ollamaAccounts,
      openGoAccounts,
      cpaChannels,
      configReady,
      loading,
      error,
      ollamaHasData,
      openGoHasData,
      refreshAll,
    ]
  );

  return <QuotaContext.Provider value={value}>{children}</QuotaContext.Provider>;
}

export function useQuota() {
  const value = useContext(QuotaContext);
  if (!value) throw new Error("useQuota must be used within QuotaProvider");
  return value;
}
