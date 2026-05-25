import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Bookmark,
  LayoutDashboard,
  LineChart,
  RefreshCw,
  Settings,
  Wallet,
} from "lucide-react";
import { useCallback, useState, type ComponentType } from "react";
import { BacktestPanel } from "./components/BacktestPanel";
import { DashboardCards } from "./components/DashboardCards";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ItemDetailModal } from "./components/ItemDetailModal";
import {
  OpportunitiesTable,
  type OpportunityFilters,
} from "./components/OpportunitiesTable";
import { LogsViewer } from "./components/LogsViewer";
import { PortfolioHeat } from "./components/PortfolioHeat";
import { PositionsTable } from "./components/PositionsTable";
import { SystemHealthPanel } from "./components/SystemHealth";
import { Button } from "./components/ui/Button";
import { useRefreshInterval, type RefreshOption } from "./hooks/useRefreshInterval";
import { useWebSocket } from "./hooks/useWebSocket";
import type { FilterPreset, Opportunity, TabId } from "./types";
import { api } from "./utils/api";
import { cn } from "./utils/cn";

const defaultFilters: OpportunityFilters = {
  search: "",
  profit_min: "",
  profit_max: "",
  liquidity_min: "",
  volatility_min: "",
  momentum_min: "",
  price_min: "",
  price_max: "",
};

const TABS: { id: TabId; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "opportunities", label: "Opportunities", icon: TargetIcon },
  { id: "watchlist", label: "Watchlist", icon: Bookmark },
  { id: "positions", label: "Positions", icon: Wallet },
  { id: "trades", label: "Trades", icon: LineChart },
  { id: "backtests", label: "Backtests", icon: BarChart3 },
  { id: "system", label: "System & Logs", icon: Settings },
];

function TargetIcon({ className }: { className?: string }) {
  return <Activity className={className} />;
}

function buildOppParams(
  filters: OpportunityFilters,
  page: number,
  sortBy: string,
  sortDir: string,
  watchlistOnly: boolean
) {
  const p = new URLSearchParams();
  if (filters.search) p.set("search", filters.search);
  if (filters.profit_min) p.set("profit_min", filters.profit_min);
  if (filters.profit_max) p.set("profit_max", filters.profit_max);
  if (filters.liquidity_min) p.set("liquidity_min", filters.liquidity_min);
  if (filters.volatility_min) p.set("volatility_min", filters.volatility_min);
  if (filters.momentum_min) p.set("momentum_min", filters.momentum_min);
  if (filters.price_min) p.set("price_min", filters.price_min);
  if (filters.price_max) p.set("price_max", filters.price_max);
  p.set("page", String(page));
  p.set("page_size", "25");
  p.set("sort_by", sortBy);
  p.set("sort_dir", sortDir);
  if (watchlistOnly) p.set("watchlist_only", "true");
  return p;
}

export default function App() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabId>("dashboard");
  const [filters, setFilters] = useState(defaultFilters);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("profit_score");
  const [sortDir, setSortDir] = useState("desc");
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [refreshSec, setRefreshSec] = useState<RefreshOption>(30);
  const [logsPaused, setLogsPaused] = useState(false);
  const [logLevel, setLogLevel] = useState("");
  const [logSearch, setLogSearch] = useState("");
  const [tradeSearch, setTradeSearch] = useState("");

  const refreshAll = useCallback(() => {
    qc.invalidateQueries();
  }, [qc]);

  useWebSocket(() => {
    if (!logsPaused) qc.invalidateQueries({ queryKey: ["logs"] });
    qc.invalidateQueries({ queryKey: ["positions"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  });

  useRefreshInterval(refreshSec, refreshAll);

  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
  });

  const opportunities = useQuery({
    queryKey: ["opportunities", filters, page, sortBy, sortDir, tab === "watchlist"],
    queryFn: () =>
      api.opportunities(
        buildOppParams(filters, page, sortBy, sortDir, tab === "watchlist")
      ),
    enabled: tab === "opportunities" || tab === "watchlist" || tab === "dashboard",
  });

  const presets = useQuery({
    queryKey: ["presets"],
    queryFn: api.filterPresets,
  });

  const positions = useQuery({
    queryKey: ["positions"],
    queryFn: api.positions,
  });

  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: api.portfolio,
  });

  const trades = useQuery({
    queryKey: ["trades", tradeSearch],
    queryFn: () => {
      const p = new URLSearchParams();
      if (tradeSearch) p.set("search", tradeSearch);
      p.set("page_size", "50");
      return api.trades(p);
    },
    enabled: tab === "trades",
  });

  const backtests = useQuery({
    queryKey: ["backtests"],
    queryFn: async () => (await api.backtests()).items,
    enabled: tab === "backtests",
  });

  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    enabled: tab === "system",
  });

  const logs = useQuery({
    queryKey: ["logs", logLevel, logSearch],
    queryFn: () => {
      const p = new URLSearchParams();
      if (logLevel) p.set("level", logLevel);
      if (logSearch) p.set("search", logSearch);
      p.set("limit", "300");
      return api.logs(p);
    },
    enabled: tab === "system" && !logsPaused,
    refetchInterval: logsPaused ? false : refreshSec ? refreshSec * 1000 : false,
  });

  const runAnalytics = useMutation({
    mutationFn: api.runAnalytics,
    onSuccess: refreshAll,
  });

  const runBacktest = useMutation({
    mutationFn: ({ item, balance }: { item: string; balance: number }) =>
      api.runBacktest(item, balance),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backtests"] }),
  });

  const savePreset = useMutation({
    mutationFn: (name: string) =>
      api.savePreset(name, { ...filters, sortBy, sortDir }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["presets"] }),
  });

  const toggleWatchlist = useMutation({
    mutationFn: async (item: Opportunity) => {
      if (item.on_watchlist) return api.removeWatchlist(item.item_name);
      return api.addWatchlist(item.item_name);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const handleSort = (col: string) => {
    if (sortBy === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const loadPreset = (preset: FilterPreset) => {
    const f = preset.filters as Record<string, string>;
    setFilters({
      ...defaultFilters,
      search: f.search ?? "",
      profit_min: f.profit_min ?? "",
      profit_max: f.profit_max ?? "",
      liquidity_min: f.liquidity_min ?? "",
      volatility_min: f.volatility_min ?? "",
      momentum_min: f.momentum_min ?? "",
      price_min: f.price_min ?? "",
      price_max: f.price_max ?? "",
    });
    if (f.sortBy) setSortBy(f.sortBy);
    if (f.sortDir) setSortDir(f.sortDir);
    setPage(1);
  };

  const exportCsv = async () => {
    const p = new URLSearchParams();
    if (tradeSearch) p.set("search", tradeSearch);
    const csv = await api.exportTrades(p);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trades.csv";
    a.click();
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen flex">
        <aside className="w-56 border-r border-panel-border bg-panel-card/50 p-4 flex flex-col gap-1">
          <h1 className="text-lg font-bold mb-4 px-2">Steam Monitor</h1>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition",
                tab === t.id
                  ? "bg-panel-accent/20 text-blue-300"
                  : "text-slate-400 hover:bg-slate-800"
              )}
            >
              <t.icon className="h-4 w-4" />
              {t.label}
            </button>
          ))}
        </aside>

        <main className="flex-1 p-6 overflow-auto">
          <header className="flex flex-wrap items-center justify-between gap-4 mb-6">
            <h2 className="text-2xl font-semibold capitalize">{tab}</h2>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded-lg bg-panel-card border border-panel-border px-3 py-1.5 text-sm"
                value={refreshSec}
                onChange={(e) =>
                  setRefreshSec(Number(e.target.value) as RefreshOption)
                }
              >
                <option value={15}>15s</option>
                <option value={30}>30s</option>
                <option value={60}>60s</option>
                <option value={0}>Manual</option>
              </select>
              <Button
                variant="secondary"
                onClick={() => runAnalytics.mutate()}
                disabled={runAnalytics.isPending}
              >
                Run Analytics
              </Button>
              <Button
                variant="secondary"
                onClick={() => setTab("backtests")}
              >
                Run Backtest
              </Button>
              <Button variant="primary" onClick={refreshAll}>
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh All
              </Button>
            </div>
          </header>

          {(tab === "dashboard" || tab === "opportunities" || tab === "watchlist") && (
            <>
              {tab === "dashboard" && (
                <div className="space-y-6 mb-6">
                  <DashboardCards data={dashboard.data} loading={dashboard.isLoading} />
                  <div className="grid lg:grid-cols-3 gap-4">
                    <div className="lg:col-span-2">
                      <h3 className="text-sm text-slate-400 mb-2">Top opportunities</h3>
                      <OpportunitiesTable
                        items={opportunities.data?.items.slice(0, 10) ?? []}
                        total={opportunities.data?.total ?? 0}
                        page={1}
                        pageSize={10}
                        totalPages={1}
                        filters={filters}
                        onFiltersChange={setFilters}
                        onPageChange={setPage}
                        onSort={handleSort}
                        sortBy={sortBy}
                        sortDir={sortDir}
                        loading={opportunities.isLoading}
                        onRowClick={setSelected}
                        presets={presets.data}
                        onSavePreset={(n) => savePreset.mutate(n)}
                        onLoadPreset={loadPreset}
                      />
                    </div>
                    <PortfolioHeat
                      heatPct={portfolio.data?.portfolio_heat_pct ?? 0}
                    />
                  </div>
                </div>
              )}

              {(tab === "opportunities" || tab === "watchlist") && (
                <OpportunitiesTable
                  items={opportunities.data?.items ?? []}
                  total={opportunities.data?.total ?? 0}
                  page={opportunities.data?.page ?? 1}
                  pageSize={opportunities.data?.page_size ?? 25}
                  totalPages={opportunities.data?.total_pages ?? 1}
                  filters={filters}
                  onFiltersChange={(f) => {
                    setFilters(f);
                    setPage(1);
                  }}
                  onPageChange={setPage}
                  onSort={handleSort}
                  sortBy={sortBy}
                  sortDir={sortDir}
                  loading={opportunities.isLoading}
                  onRowClick={setSelected}
                  presets={presets.data}
                  onSavePreset={(n) => savePreset.mutate(n)}
                  onLoadPreset={loadPreset}
                  watchlistMode={tab === "watchlist"}
                />
              )}
            </>
          )}

          {tab === "positions" && (
            <div className="grid lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <PositionsTable
                  positions={positions.data ?? []}
                  loading={positions.isLoading}
                />
              </div>
              <PortfolioHeat heatPct={portfolio.data?.portfolio_heat_pct ?? 0} />
            </div>
          )}

          {tab === "trades" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-lg bg-panel-card border border-panel-border px-3 py-2"
                  placeholder="Filter trades..."
                  value={tradeSearch}
                  onChange={(e) => setTradeSearch(e.target.value)}
                />
                <Button variant="secondary" onClick={exportCsv}>
                  Export CSV
                </Button>
              </div>
              {trades.data?.summary && (
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <Stat label="Total trades" value={String(trades.data.summary.total_trades)} />
                  <Stat
                    label="Total PnL"
                    value={`${trades.data.summary.total_pnl_rub} ₽`}
                  />
                  <Stat
                    label="Win rate"
                    value={
                      trades.data.summary.win_rate_pct != null
                        ? `${trades.data.summary.win_rate_pct}%`
                        : "—"
                    }
                  />
                </div>
              )}
              <div className="rounded-xl border border-panel-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-900 text-slate-400">
                    <tr>
                      <th className="text-left p-2">Item</th>
                      <th className="text-right p-2">PnL</th>
                      <th className="text-right p-2">%</th>
                      <th className="text-right p-2">Closed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(trades.data?.items ?? []).map((t) => (
                      <tr key={t.id} className="border-t border-panel-border/40">
                        <td className="p-2">{t.item_name}</td>
                        <td
                          className={`text-right p-2 ${
                            (t.pnl_rub ?? 0) >= 0
                              ? "text-panel-success"
                              : "text-panel-danger"
                          }`}
                        >
                          {t.pnl_rub?.toFixed(0)} ₽
                        </td>
                        <td className="text-right p-2">{t.pnl_pct?.toFixed(1)}%</td>
                        <td className="text-right p-2 text-slate-500">
                          {t.closed_at
                            ? new Date(t.closed_at).toLocaleDateString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "backtests" && (
            <BacktestPanel
              history={backtests.data ?? []}
              running={runBacktest.isPending}
              onRun={(item, balance) => runBacktest.mutate({ item, balance })}
            />
          )}

          {tab === "system" && (
            <div className="grid lg:grid-cols-2 gap-4">
              <SystemHealthPanel health={health.data} loading={health.isLoading} />
              <LogsViewer
                entries={logs.data?.entries ?? []}
                loading={logs.isLoading}
                level={logLevel}
                search={logSearch}
                onLevelChange={setLogLevel}
                onSearchChange={setLogSearch}
                paused={logsPaused}
                onPausedChange={setLogsPaused}
              />
            </div>
          )}
        </main>
      </div>

      <ItemDetailModal
        item={selected}
        onClose={() => setSelected(null)}
        onWatchlistToggle={() => selected && toggleWatchlist.mutate(selected)}
      />
    </ErrorBoundary>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-panel-border bg-panel-card p-3">
      <div className="text-slate-500 text-xs">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
