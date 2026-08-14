import type { OllamaQuotaAccount, PublicQuotaAccount, QuotaWindow } from "@/lib/api";
import { applyOpenCodeCascade } from "@/lib/utils";

function isOllamaWeeklyExhausted(windows: QuotaWindow[]): boolean {
  const weekly = windows.find((w) => w.label === "Weekly");
  return weekly != null && weekly.used >= 100;
}

export function hasUsableOllamaQuota(account: OllamaQuotaAccount): boolean {
  if (!account.success || account.error) return false;
  const windows = account.windows ?? [];
  if (windows.length === 0) return false;

  const weeklyExhausted = isOllamaWeeklyExhausted(windows);
  for (const window of windows) {
    if (window.label === "Session" && weeklyExhausted) continue;
    if (window.remaining > 0) return true;
  }
  return false;
}

export function hasUsableOpenCodeQuota(account: PublicQuotaAccount): boolean {
  if (!account.success || account.error) return false;
  const windows = account.windows ?? [];
  if (windows.length === 0) return false;

  const cascaded = applyOpenCodeCascade(windows);
  return cascaded.some((window) => !window.blocked && window.remaining > 0);
}

export function sortOllamaAccountsByQuota<T extends OllamaQuotaAccount>(accounts: T[]): T[] {
  return accounts
    .map((account, order) => ({ account, order }))
    .sort((a, b) => {
      const aHas = hasUsableOllamaQuota(a.account);
      const bHas = hasUsableOllamaQuota(b.account);
      if (aHas !== bHas) return aHas ? -1 : 1;
      return a.order - b.order;
    })
    .map(({ account }) => account);
}

export function sortOpenCodeAccountsByQuota<T extends PublicQuotaAccount>(accounts: T[]): T[] {
  return accounts
    .map((account, order) => ({ account, order }))
    .sort((a, b) => {
      const aHas = hasUsableOpenCodeQuota(a.account);
      const bHas = hasUsableOpenCodeQuota(b.account);
      if (aHas !== bHas) return aHas ? -1 : 1;
      return a.order - b.order;
    })
    .map(({ account }) => account);
}
