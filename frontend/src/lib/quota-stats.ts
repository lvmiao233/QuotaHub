import type { OllamaModelUsage, OllamaQuotaAccount, PublicQuotaAccount } from "@/lib/api";
import { applyOpenCodeCascade } from "@/lib/utils";

export type CycleQuota = {
  label: string;
  displayLabel: string;
  remaining: number;
  total: number;
  used: number;
};

const OLLAMA_CYCLES: Array<{ label: string; displayLabel: string }> = [
  { label: "Session", displayLabel: "5 小时限额" },
  { label: "Weekly", displayLabel: "周限额" },
];

const OPENCODE_CYCLES: Array<{ label: string; displayLabel: string }> = [
  { label: "5h Rolling", displayLabel: "5 小时滚动" },
  { label: "Weekly", displayLabel: "周额度" },
  { label: "Monthly", displayLabel: "月额度" },
];

export function planMultiplier(plan: string): number {
  return plan.toLowerCase().includes("max") ? 5 : 1;
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

function isOllamaWeeklyExhausted(account: OllamaQuotaAccount): boolean {
  const weekly = account.windows?.find((w) => w.label === "Weekly");
  return weekly != null && weekly.used >= 100;
}

function sumOllamaCycle(accounts: OllamaQuotaAccount[], label: string): CycleQuota {
  let remaining = 0;
  let total = 0;

  for (const account of accounts) {
    if (!account.success) continue;
    const window = account.windows?.find((w) => w.label === label);
    if (!window) continue;

    const multiplier = planMultiplier(account.plan || "");
    const capacity = 100 * multiplier;
    total += capacity;

    if (label === "Session" && isOllamaWeeklyExhausted(account)) {
      continue;
    }
    remaining += window.remaining * multiplier;
  }

  remaining = round1(remaining);
  total = round1(total);
  return {
    label,
    displayLabel: OLLAMA_CYCLES.find((c) => c.label === label)?.displayLabel ?? label,
    remaining,
    total,
    used: round1(Math.max(0, total - remaining)),
  };
}

function sumOpenCodeCycle(accounts: PublicQuotaAccount[], label: string): CycleQuota {
  let remaining = 0;
  let total = 0;

  for (const account of accounts) {
    if (!account.success) continue;
    const windows = account.windows ?? [];
    const cascaded = applyOpenCodeCascade(windows);
    const window = cascaded.find((w) => w.label === label);
    if (!window) continue;

    total += 100;
    remaining += window.blocked ? 0 : window.remaining;
  }

  remaining = round1(remaining);
  total = round1(total);
  return {
    label,
    displayLabel: OPENCODE_CYCLES.find((c) => c.label === label)?.displayLabel ?? label,
    remaining,
    total,
    used: round1(Math.max(0, total - remaining)),
  };
}

export function computeOllamaCycleRemaining(accounts: OllamaQuotaAccount[]): CycleQuota[] {
  return OLLAMA_CYCLES.map(({ label }) => sumOllamaCycle(accounts, label));
}

export function computeOpenCodeCycleRemaining(accounts: PublicQuotaAccount[]): CycleQuota[] {
  return OPENCODE_CYCLES.map(({ label }) => sumOpenCodeCycle(accounts, label));
}

export function aggregateOllamaModelsByWindow(
  accounts: OllamaQuotaAccount[],
  windowLabel: string
): OllamaModelUsage[] {
  const totals = new Map<string, number>();
  for (const account of accounts) {
    if (!account.success) continue;
    const window = account.windows?.find((w) => w.label === windowLabel);
    if (!window?.models?.length) continue;
    for (const model of window.models) {
      if (!model.model) continue;
      totals.set(model.model, (totals.get(model.model) ?? 0) + model.requests);
    }
  }
  const grandTotal = [...totals.values()].reduce((a, b) => a + b, 0) || 1;
  return [...totals.entries()]
    .map(([model, requests]) => ({
      model,
      requests,
      share_percent: round1((requests / grandTotal) * 100),
    }))
    .sort((a, b) => b.requests - a.requests || a.model.localeCompare(b.model));
}

export function formatQuotaRatio(remaining: number, total: number): string {
  return `${remaining}% / ${total}%`;
}

export type OpenCodeModelCostStat = {
  model: string;
  requests: number;
  cost_usd: number;
  share_percent: number;
};

export function aggregateOpenCodeModelsByCost(
  modelStats: Array<{ model: string; total_cost_usd: number; request_count: number }>
): OpenCodeModelCostStat[] {
  const totals = new Map<string, { cost: number; requests: number }>();
  for (const row of modelStats) {
    const cur = totals.get(row.model) ?? { cost: 0, requests: 0 };
    cur.cost += row.total_cost_usd;
    cur.requests += row.request_count;
    totals.set(row.model, cur);
  }
  const grandCost = [...totals.values()].reduce((sum, item) => sum + item.cost, 0) || 1;
  return [...totals.entries()]
    .map(([model, { cost, requests }]) => ({
      model,
      requests,
      cost_usd: cost,
      share_percent: round1((cost / grandCost) * 100),
    }))
    .sort((a, b) => b.cost_usd - a.cost_usd || a.model.localeCompare(b.model));
}
