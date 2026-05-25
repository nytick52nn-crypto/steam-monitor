import type { Position } from "../types";
import { Card } from "./ui/Card";

interface Props {
  positions: Position[];
  loading?: boolean;
}

export function PositionsTable({ positions, loading }: Props) {
  return (
    <Card>
      <h3 className="text-sm font-medium text-slate-400 mb-3">Active Positions</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-500 border-b border-panel-border">
            <tr>
              <th className="text-left py-2">Item</th>
              <th className="text-right py-2">Entry</th>
              <th className="text-right py-2">Current</th>
              <th className="text-right py-2">PnL</th>
              <th className="text-right py-2">Stop</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : positions.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-slate-500">
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((p) => (
                <tr key={p.id} className="border-t border-panel-border/40">
                  <td className="py-2">{p.item_name}</td>
                  <td className="text-right">{p.entry_price.toFixed(2)}</td>
                  <td className="text-right">
                    {p.current_price?.toFixed(2) ?? "—"}
                  </td>
                  <td
                    className={`text-right font-medium ${
                      (p.unrealized_pnl_rub ?? 0) >= 0
                        ? "text-panel-success"
                        : "text-panel-danger"
                    }`}
                  >
                    {p.unrealized_pnl_rub != null
                      ? `${p.unrealized_pnl_rub >= 0 ? "+" : ""}${p.unrealized_pnl_rub.toFixed(0)} ₽`
                      : "—"}
                  </td>
                  <td className="text-right text-amber-400/90">
                    {p.stop_loss?.toFixed(2) ?? "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
