import type { SystemHealth } from "../types";
import { Card } from "./ui/Card";

const STATUS_DOT: Record<string, string> = {
  ok: "bg-panel-success",
  warn: "bg-panel-warn",
  error: "bg-panel-danger",
  degraded: "bg-panel-warn",
};

interface Props {
  health?: SystemHealth;
  loading?: boolean;
}

export function SystemHealthPanel({ health, loading }: Props) {
  if (loading || !health) {
    return <Card className="h-32 animate-pulse" />;
  }

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`h-3 w-3 rounded-full ${STATUS_DOT[health.overall] ?? "bg-slate-500"}`}
        />
        <h3 className="font-medium capitalize">{health.overall}</h3>
        <span className="text-slate-500 text-sm ml-auto">
          Monitor {health.monitor_running ? "active" : "idle"}
        </span>
      </div>
      <ul className="space-y-2 text-sm">
        {health.components.map((c) => (
          <li key={c.name} className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${STATUS_DOT[c.status] ?? "bg-slate-500"}`}
            />
            <span className="text-slate-300 w-32">{c.name}</span>
            <span className="text-slate-500 truncate">{c.detail}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
