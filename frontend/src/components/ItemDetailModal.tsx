import { useQuery } from "@tanstack/react-query";
import { Bookmark, X } from "lucide-react";
import { useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Opportunity } from "../types";
import { api } from "../utils/api";
import { Button } from "./ui/Button";

interface Props {
  item: Opportunity | null;
  onClose: () => void;
  onWatchlistToggle?: () => void;
}

export function ItemDetailModal({ item, onClose, onWatchlistToggle }: Props) {
  const [days, setDays] = useState(7);
  const name = item?.item_name ?? "";

  const detail = useQuery({
    queryKey: ["item-detail", name],
    queryFn: () => api.itemDetail(name),
    enabled: !!name,
  });

  const history = useQuery({
    queryKey: ["item-history", name, days],
    queryFn: () => api.itemHistory(name, days),
    enabled: !!name,
  });

  const risk = useQuery({
    queryKey: ["item-risk", name],
    queryFn: () => api.itemRisk(name),
    enabled: !!name,
  });

  if (!item) return null;

  const chartData =
    history.data?.points.map((p) => ({
      ts: p.timestamp.slice(5, 16),
      price: p.price,
      volume: p.volume,
    })) ?? [];

  const d = detail.data;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-panel-card border border-panel-border rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-start justify-between p-4 border-b border-panel-border">
          <div>
            <h2 className="text-xl font-bold">{item.item_name}</h2>
            <p className="text-slate-400 text-sm">
              Profit score{" "}
              <span className="text-panel-accent font-semibold">
                {item.profit_score.toFixed(0)}
              </span>
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={onWatchlistToggle}>
              <Bookmark className="h-4 w-4 mr-1" />
              {item.on_watchlist ? "Remove watchlist" : "Add to watchlist"}
            </Button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-700"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <Button
                key={d}
                size="sm"
                variant={days === d ? "primary" : "ghost"}
                onClick={() => setDays(d)}
              >
                {d}d
              </Button>
            ))}
          </div>

          <div className="h-56">
            {history.isLoading ? (
              <div className="h-full flex items-center justify-center text-slate-500">
                Loading chart...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}>
                  <CartesianGrid stroke="#2d3a4f" strokeDasharray="3 3" />
                  <XAxis dataKey="ts" tick={{ fontSize: 10 }} stroke="#64748b" />
                  <YAxis yAxisId="price" tick={{ fontSize: 10 }} stroke="#64748b" />
                  <YAxis yAxisId="vol" orientation="right" hide />
                  <Tooltip
                    contentStyle={{
                      background: "#1a2332",
                      border: "1px solid #2d3a4f",
                    }}
                  />
                  <Area
                    yAxisId="price"
                    type="monotone"
                    dataKey="price"
                    stroke="#3b82f6"
                    fill="#3b82f640"
                  />
                  <Bar yAxisId="vol" dataKey="volume" fill="#64748b55" barSize={4} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>

          {d && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              <ScoreChip label="Price movement" value={d.price_movement_component} />
              <ScoreChip label="Liquidity" value={d.liquidity_score} />
              <ScoreChip label="Volatility" value={d.volatility_score} />
              <ScoreChip label="Spread stability" value={d.spread_stability_score} />
              <ScoreChip label="Momentum" value={d.momentum_score} />
              <ScoreChip label="Change %" value={d.price_change_pct} suffix="%" />
            </div>
          )}

          {risk.data && (
            <div className="rounded-lg bg-slate-900/50 p-3 text-sm space-y-1">
              <div className="font-medium text-slate-300">Risk</div>
              <div>
                Trade allowed:{" "}
                <span
                  className={
                    risk.data.trade_allowed ? "text-panel-success" : "text-panel-danger"
                  }
                >
                  {String(risk.data.trade_allowed)}
                </span>
              </div>
              <div className="text-slate-400">{String(risk.data.trade_reason)}</div>
              {risk.data.stop_loss_preview != null && (
                <div>Stop loss preview: {Number(risk.data.stop_loss_preview).toFixed(2)} ₽</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ScoreChip({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value?: number | null;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg border border-panel-border p-2">
      <div className="text-slate-500 text-xs">{label}</div>
      <div className="font-semibold">
        {value != null ? `${value.toFixed(1)}${suffix}` : "—"}
      </div>
    </div>
  );
}
