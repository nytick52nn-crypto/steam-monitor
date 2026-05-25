import { Pause, Play, Search } from "lucide-react";
import type { LogEntry } from "../types";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface Props {
  entries: LogEntry[];
  loading?: boolean;
  level: string;
  search: string;
  onLevelChange: (v: string) => void;
  onSearchChange: (v: string) => void;
  paused: boolean;
  onPausedChange: (v: boolean) => void;
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "text-slate-500",
  INFO: "text-blue-400",
  WARNING: "text-amber-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-500",
};

export function LogsViewer({
  entries,
  loading,
  level,
  search,
  onLevelChange,
  onSearchChange,
  paused,
  onPausedChange,
}: Props) {
  return (
    <Card className="flex flex-col h-[480px]">
      <div className="flex flex-wrap gap-2 mb-3">
        <select
          className="rounded-lg bg-slate-900 border border-panel-border px-3 py-1.5 text-sm"
          value={level}
          onChange={(e) => onLevelChange(e.target.value)}
        >
          <option value="">All levels</option>
          {["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        <div className="flex-1 flex items-center gap-2 rounded-lg bg-slate-900 border border-panel-border px-3">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            className="flex-1 bg-transparent text-sm outline-none"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPausedChange(!paused)}
        >
          {paused ? (
            <>
              <Play className="h-4 w-4 mr-1" /> Resume
            </>
          ) : (
            <>
              <Pause className="h-4 w-4 mr-1" /> Pause
            </>
          )}
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto font-mono text-xs space-y-0.5">
        {loading && (
          <div className="text-slate-500 p-4 text-center">Loading logs...</div>
        )}
        {!loading &&
          entries.map((e, i) => (
            <div
              key={`${e.timestamp}-${i}`}
              className="hover:bg-slate-800/50 px-2 py-0.5 rounded"
            >
              <span className="text-slate-600">{e.timestamp}</span>{" "}
              <span className={LEVEL_COLORS[e.level] ?? "text-slate-400"}>
                {e.level}
              </span>{" "}
              <span className="text-slate-500">{e.logger}</span>{" "}
              <span className="text-slate-200">{e.message}</span>
            </div>
          ))}
      </div>
    </Card>
  );
}
