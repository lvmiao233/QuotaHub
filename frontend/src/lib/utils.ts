import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatResetIn(seconds: number): string {
  if (seconds <= 0) return "即将重置";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) {
    return `${days}天${hours}小时${minutes}分钟后重置`;
  }
  if (hours > 0) return `${hours} 小时 ${minutes} 分钟后重置`;
  if (minutes > 0) return `${minutes} 分钟后重置`;
  return `${seconds} 秒后重置`;
}

export function quotaLabel(label: string): string {
  switch (label) {
    case "5h Rolling":
      return "5 小时滚动";
    case "Weekly":
      return "周额度";
    case "Monthly":
      return "月额度";
    case "Session":
      return "5 小时限额";
    default:
      return label;
  }
}

export function ollamaQuotaLabel(label: string): string {
  switch (label) {
    case "Session":
      return "5 小时限额";
    case "Weekly":
      return "周限额";
    default:
      return quotaLabel(label);
  }
}

/** Ollama 页面会带回与「已用 x%」重复的英文周期文案，仅保留有限额提示等有用信息。 */
export function ollamaStatusTextVisible(statusText: string): boolean {
  const text = statusText.trim();
  if (!text) return false;
  if (/^\d+(\.\d+)?%\s*used$/i.test(text)) return false;
  return true;
}

export function formatPlanLabel(plan: string): string {
  const trimmed = plan.trim();
  if (!trimmed) return trimmed;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
}

const OLLAMA_MODEL_COLORS = ["#3b82f6", "#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b"];

export function ollamaModelColor(index: number): string {
  return OLLAMA_MODEL_COLORS[index % OLLAMA_MODEL_COLORS.length];
}

export function buildModelColorMap(models: string[]): Map<string, string> {
  const sorted = [...new Set(models)].sort();
  const map = new Map<string, string>();
  sorted.forEach((model, index) => {
    map.set(model, ollamaModelColor(index));
  });
  return map;
}

export function usageTone(used: number): string {
  if (used >= 90) return "text-rose-600";
  if (used >= 70) return "text-amber-600";
  return "text-cyan-700";
}

export function progressTone(used: number): string {
  if (used >= 90) return "bg-rose-500";
  if (used >= 70) return "bg-amber-500";
  return "bg-gradient-to-r from-cyan-500 to-sky-500";
}

const LABEL_MONTHLY = "Monthly";
const LABEL_WEEKLY = "Weekly";
const LABEL_ROLLING = "5h Rolling";

export function applyOpenCodeCascade(windows: import("@/lib/api").QuotaWindow[]): import("@/lib/api").QuotaWindow[] {
  const monthly = windows.find((w) => w.label === LABEL_MONTHLY);
  const weekly = windows.find((w) => w.label === LABEL_WEEKLY);
  const monthlyFull = monthly != null && monthly.used >= 100;
  const weeklyFull = weekly != null && weekly.used >= 100;

  return windows.map((window) => {
    let blocked = false;
    let blockedBy = "";
    if (window.label === LABEL_WEEKLY && monthlyFull) {
      blocked = true;
      blockedBy = LABEL_MONTHLY;
    } else if (window.label === LABEL_ROLLING && (monthlyFull || weeklyFull)) {
      blocked = true;
      blockedBy = monthlyFull ? LABEL_MONTHLY : LABEL_WEEKLY;
    }
    return {
      ...window,
      blocked,
      blocked_by: blockedBy,
      effective_remaining: blocked ? 0 : window.remaining,
    };
  });
}

export function opencodeBlockedLabel(blockedBy: string | undefined): string {
  switch (blockedBy) {
    case LABEL_MONTHLY:
      return "月限额已满";
    case LABEL_WEEKLY:
      return "周限额已满";
    default:
      return "限额已满";
  }
}
