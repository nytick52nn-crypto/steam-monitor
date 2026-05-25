import { Activity, Flame, Percent, Target, Wallet } from "lucide-react";
import type { DashboardKPIs } from "../types";
import { Card } from "./ui/Card";

interface Props {
  data?: DashboardKPIs;
  loading?: boolean;
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  return (
    <Card className="flex flex-col gap-2 min-w-[160px] flex-1">
      <div className="flex items-center justify-between text-slate-400 text-sm">
        <span>{label}</span>
        <Icon className={cnIcon(accent)} />
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

function cnIcon(accent: string) {
  return `h-5 w-5 ${accent}`;
}

export function DashboardCards({ data, loading }: Props) {
  if (loading || !data) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i} className="h-24 animate-pulse bg-slate-800/50" />
        ))}
      </div>
    );
  }

  const pnlColor =
    data.today_pnl_rub >= 0 ? "text-panel-success" : "text-panel-danger";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      <KpiCard
        label="Opportunities"
        value={String(data.total_opportunities)}
        sub="Scored items"
        icon={Target}
        accent="text-blue-400"
      />
      <KpiCard
        label="Portfolio Heat"
        value={`${data.portfolio_heat_pct.toFixed(1)}%`}
        sub="Open exposure"
        icon={Flame}
        accent="text-orange-400"
      />
      <KpiCard
        label="Today PnL"
        value={`${data.today_pnl_rub >= 0 ? "+" : ""}${data.today_pnl_rub.toFixed(0)} ₽`}
        sub="Closed today"
        icon={Wallet}
        accent={pnlColor}
      />
      <KpiCard
        label="Win Rate"
        value={
          data.win_rate_pct != null ? `${data.win_rate_pct.toFixed(1)}%` : "—"
        }
        sub="All closed trades"
        icon={Percent}
        accent="text-emerald-400"
      />
      <KpiCard
        label="Last Scan"
        value={data.last_scan?.split(" ")[1] ?? "—"}
        sub={data.last_scan?.split(" ")[0] ?? "No data"}
        icon={Activity}
        accent="text-violet-400"
      />
    </div>
  );
}
