import { Bookmark, ChevronLeft, ChevronRight, Columns3, Save } from "lucide-react";
import { useMemo, useState } from "react";
import type { FilterPreset, Opportunity } from "../types";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

export interface OpportunityFilters {
  search: string;
  profit_min: string;
  profit_max: string;
  liquidity_min: string;
  volatility_min: string;
  momentum_min: string;
  price_min: string;
  price_max: string;
}

const ALL_COLUMNS = [
  { key: "item_name", label: "Item" },
  { key: "profit_score", label: "Profit Score" },
  { key: "liquidity_score", label: "Liquidity" },
  { key: "volatility_score", label: "Volatility" },
  { key: "momentum_score", label: "Momentum" },
  { key: "current_price", label: "Price" },
  { key: "liquidity_label", label: "Liq. Label" },
] as const;

interface Props {
  items: Opportunity[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  filters: OpportunityFilters;
  onFiltersChange: (f: OpportunityFilters) => void;
  onPageChange: (p: number) => void;
  onSort: (col: string) => void;
  sortBy: string;
  sortDir: string;
  loading?: boolean;
  onRowClick: (item: Opportunity) => void;
  presets?: FilterPreset[];
  onSavePreset?: (name: string) => void;
  onLoadPreset?: (preset: FilterPreset) => void;
  watchlistMode?: boolean;
}

export function OpportunitiesTable({
  items,
  total,
  page,
  pageSize,
  totalPages,
  filters,
  onFiltersChange,
  onPageChange,
  onSort,
  sortBy,
  sortDir,
  loading,
  onRowClick,
  presets = [],
  onSavePreset,
  onLoadPreset,
}: Props) {
  const [visibleCols, setVisibleCols] = useState<string[]>(
    ALL_COLUMNS.map((c) => c.key)
  );
  const [showCols, setShowCols] = useState(false);
  const [presetName, setPresetName] = useState("");

  const cols = useMemo(
    () => ALL_COLUMNS.filter((c) => visibleCols.includes(c.key)),
    [visibleCols]
  );

  const set = (key: keyof OpportunityFilters, val: string) =>
    onFiltersChange({ ...filters, [key]: val });

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <input
          className="flex-1 min-w-[200px] rounded-lg bg-slate-900 border border-panel-border px-3 py-2 text-sm"
          placeholder="Search by item name..."
          value={filters.search}
          onChange={(e) => set("search", e.target.value)}
        />
        <FilterInput label="Score min" value={filters.profit_min} onChange={(v) => set("profit_min", v)} />
        <FilterInput label="Score max" value={filters.profit_max} onChange={(v) => set("profit_max", v)} />
        <FilterInput label="Liq min" value={filters.liquidity_min} onChange={(v) => set("liquidity_min", v)} />
        <FilterInput label="Vol min" value={filters.volatility_min} onChange={(v) => set("volatility_min", v)} />
        <FilterInput label="Mom min" value={filters.momentum_min} onChange={(v) => set("momentum_min", v)} />
        <FilterInput label="Price min" value={filters.price_min} onChange={(v) => set("price_min", v)} />
        <FilterInput label="Price max" value={filters.price_max} onChange={(v) => set("price_max", v)} />
        <Button variant="ghost" size="sm" onClick={() => setShowCols(!showCols)}>
          <Columns3 className="h-4 w-4" />
        </Button>
      </div>

      {showCols && (
        <div className="flex flex-wrap gap-2 text-xs">
          {ALL_COLUMNS.map((c) => (
            <label key={c.key} className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={visibleCols.includes(c.key)}
                onChange={() =>
                  setVisibleCols((prev) =>
                    prev.includes(c.key)
                      ? prev.filter((k) => k !== c.key)
                      : [...prev, c.key]
                  )
                }
              />
              {c.label}
            </label>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center text-sm">
        <input
          className="rounded bg-slate-900 border border-panel-border px-2 py-1 w-32"
          placeholder="Preset name"
          value={presetName}
          onChange={(e) => setPresetName(e.target.value)}
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={!presetName || !onSavePreset}
          onClick={() => {
            onSavePreset?.(presetName);
            setPresetName("");
          }}
        >
          <Save className="h-3 w-3 mr-1" /> Save preset
        </Button>
        {presets.map((p) => (
          <Button
            key={p.id}
            size="sm"
            variant="ghost"
            onClick={() => onLoadPreset?.(p)}
          >
            {p.name}
          </Button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-panel-border">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/80 text-slate-400">
            <tr>
              {cols.map((c) => (
                <th
                  key={c.key}
                  className="px-3 py-2 text-left cursor-pointer hover:text-white"
                  onClick={() => onSort(c.key)}
                >
                  {c.label}
                  {sortBy === c.key && (sortDir === "desc" ? " ↓" : " ↑")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={cols.length} className="p-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={cols.length} className="p-8 text-center text-slate-500">
                  No opportunities match filters
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr
                  key={row.item_name}
                  className="border-t border-panel-border/50 hover:bg-slate-800/60 cursor-pointer"
                  onClick={() => onRowClick(row)}
                >
                  {cols.map((c) => (
                    <td key={c.key} className="px-3 py-2">
                      {c.key === "item_name" ? (
                        <span className="flex items-center gap-2">
                          {row.on_watchlist && (
                            <Bookmark className="h-3 w-3 text-amber-400 fill-amber-400" />
                          )}
                          {row.item_name}
                        </span>
                      ) : c.key === "current_price" ? (
                        row.current_price != null
                          ? `${row.current_price.toFixed(0)} ₽`
                          : "—"
                      ) : (
                        String(
                          (row as unknown as Record<string, unknown>)[c.key] ?? "—"
                        )
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-400">
        <span>
          {total} items · page {page}/{totalPages}
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function FilterInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="text-xs text-slate-500">
      {label}
      <input
        type="number"
        className="block w-20 mt-0.5 rounded bg-slate-900 border border-panel-border px-2 py-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
