export interface Opportunity {
  item_name: string;
  profit_score: number;
  price_change_pct?: number | null;
  momentum_pct: number;
  momentum_score?: number | null;
  liquidity_score?: number | null;
  volatility_score?: number | null;
  spread_stability_score?: number | null;
  liquidity_label: string;
  volatility_label: string;
  current_price?: number | null;
  on_watchlist: boolean;
}

export interface OpportunitiesResponse {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DashboardKPIs {
  total_opportunities: number;
  portfolio_heat_pct: number;
  today_pnl_rub: number;
  win_rate_pct: number | null;
  last_scan: string | null;
  balance: number;
  open_positions: number;
}

export interface Position {
  id: number;
  item_name: string;
  entry_price: number;
  quantity: number;
  cost: number;
  current_price?: number | null;
  unrealized_pnl_rub?: number | null;
  unrealized_pnl_pct?: number | null;
  stop_loss?: number | null;
  opened_at?: string | null;
}

export interface PortfolioSummary {
  balance: number;
  starting_balance: number;
  portfolio_heat_pct: number;
  open_positions_count: number;
  total_exposure_rub: number;
  today_pnl_rub: number;
  win_rate_pct: number | null;
}

export interface Trade {
  id: number;
  item_name: string;
  entry_price: number;
  exit_price?: number | null;
  quantity: number;
  pnl_rub?: number | null;
  pnl_pct?: number | null;
  opened_at?: string | null;
  closed_at?: string | null;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  raw: string;
}

export interface FilterPreset {
  id: string;
  name: string;
  filters: Record<string, unknown>;
}

export interface ItemDetail {
  item_name: string;
  profit_score: number;
  price_change_pct?: number | null;
  momentum_pct: number;
  momentum_score?: number | null;
  liquidity_score?: number | null;
  volatility_score?: number | null;
  spread_stability_score?: number | null;
  liquidity_label: string;
  volatility_label: string;
  price_movement_component?: number | null;
}

export interface PricePoint {
  timestamp: string;
  price: number;
  volume: number;
}

export interface BacktestResult {
  id: string;
  item_name: string;
  starting_balance: number;
  ending_balance: number;
  total_pnl: number;
  trade_count: number;
  blocked_buys: number;
  signals_seen: number;
  trades: Array<{
    item_name: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    cost: number;
    pnl_rub: number;
    pnl_pct: number;
    stop_loss: number;
  }>;
  created_at: string;
}

export interface SystemHealth {
  overall: string;
  components: Array<{ name: string; status: string; detail: string }>;
  last_scan: string | null;
  opportunities_count: number;
  monitor_running: boolean;
}

export type TabId =
  | "dashboard"
  | "opportunities"
  | "watchlist"
  | "positions"
  | "trades"
  | "backtests"
  | "system";
