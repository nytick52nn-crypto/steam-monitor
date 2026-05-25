const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.headers.get("content-type")?.includes("text/csv")) {
    return (await res.text()) as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<import("../types").DashboardKPIs>("/api/system/dashboard"),
  health: () => request<import("../types").SystemHealth>("/api/system/health"),
  opportunities: (params: URLSearchParams) =>
    request<import("../types").OpportunitiesResponse>(
      `/api/analytics/opportunities?${params}`
    ),
  itemDetail: (name: string) =>
    request<import("../types").ItemDetail>(
      `/api/analytics/items/${encodeURIComponent(name)}/detail`
    ),
  itemHistory: (name: string, days: number) =>
    request<{ points: import("../types").PricePoint[] }>(
      `/api/analytics/items/${encodeURIComponent(name)}/history?days=${days}`
    ),
  itemRisk: (name: string) =>
    request<Record<string, unknown>>(
      `/api/analytics/items/${encodeURIComponent(name)}/risk`
    ),
  runAnalytics: () =>
    request<{ message: string }>("/api/analytics/run", { method: "POST" }),
  watchlist: () => request<string[]>("/api/analytics/watchlist"),
  addWatchlist: (name: string) =>
    request<string[]>(`/api/analytics/watchlist/${encodeURIComponent(name)}`, {
      method: "POST",
    }),
  removeWatchlist: (name: string) =>
    request<string[]>(
      `/api/analytics/watchlist/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    ),
  filterPresets: () =>
    request<import("../types").FilterPreset[]>("/api/analytics/filter-presets"),
  savePreset: (name: string, filters: Record<string, unknown>) =>
    request<import("../types").FilterPreset>("/api/analytics/filter-presets", {
      method: "POST",
      body: JSON.stringify({ name, filters }),
    }),
  positions: () => request<import("../types").Position[]>("/api/positions"),
  portfolio: () =>
    request<import("../types").PortfolioSummary>("/api/positions/summary"),
  trades: (params: URLSearchParams) =>
    request<{
      items: import("../types").Trade[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
      summary: Record<string, number | null>;
    }>(`/api/trades?${params}`),
  exportTrades: (params: URLSearchParams) =>
    request<string>(`/api/trades/export?${params}`),
  backtests: () =>
    request<{ items: import("../types").BacktestResult[] }>("/api/backtests"),
  runBacktest: (item_name: string, starting_balance: number) =>
    request<import("../types").BacktestResult>("/api/backtests/run", {
      method: "POST",
      body: JSON.stringify({ item_name, starting_balance }),
    }),
  logs: (params: URLSearchParams) =>
    request<{ entries: import("../types").LogEntry[]; total: number }>(
      `/api/logs?${params}`
    ),
};
