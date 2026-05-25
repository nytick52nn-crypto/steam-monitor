import { useState } from "react";
import type { BacktestResult } from "../types";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface Props {
  history: BacktestResult[];
  onRun: (item: string, balance: number) => void;
  running?: boolean;
}

export function BacktestPanel({ history, onRun, running }: Props) {
  const [item, setItem] = useState("");
  const [balance, setBalance] = useState("10000");

  return (
    <div className="space-y-4">
      <Card>
        <h3 className="text-sm font-medium text-slate-400 mb-3">Run Backtest</h3>
        <div className="flex flex-wrap gap-3">
          <input
            className="flex-1 min-w-[200px] rounded-lg bg-slate-900 border border-panel-border px-3 py-2"
            placeholder="Item name (exact)"
            value={item}
            onChange={(e) => setItem(e.target.value)}
          />
          <input
            type="number"
            className="w-32 rounded-lg bg-slate-900 border border-panel-border px-3 py-2"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
          <Button
            disabled={!item || running}
            onClick={() => onRun(item, parseFloat(balance) || 10000)}
          >
            {running ? "Running..." : "Run"}
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-slate-400 mb-3">History</h3>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {history.length === 0 ? (
            <p className="text-slate-500 text-sm">No backtests yet</p>
          ) : (
            history.map((b) => (
              <div
                key={b.id}
                className="flex justify-between items-center rounded-lg bg-slate-900/50 px-3 py-2 text-sm"
              >
                <div>
                  <span className="font-medium">{b.item_name}</span>
                  <span className="text-slate-500 ml-2">{b.created_at.slice(0, 10)}</span>
                </div>
                <div className="text-right">
                  <div
                    className={
                      b.total_pnl >= 0 ? "text-panel-success" : "text-panel-danger"
                    }
                  >
                    {b.total_pnl >= 0 ? "+" : ""}
                    {b.total_pnl.toFixed(0)} ₽
                  </div>
                  <div className="text-xs text-slate-500">
                    {b.trade_count} trades · {b.signals_seen} signals
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
