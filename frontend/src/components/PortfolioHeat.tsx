import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Card } from "./ui/Card";

interface Props {
  heatPct: number;
  maxPct?: number;
}

export function PortfolioHeat({ heatPct, maxPct = 30 }: Props) {
  const used = Math.min(heatPct, 100);
  const free = Math.max(0, maxPct - used);
  const data = [
    { name: "Used", value: used, fill: heatColor(used, maxPct) },
    { name: "Free", value: free || 0.1, fill: "#1e293b" },
  ];

  return (
    <Card className="flex flex-col items-center">
      <h3 className="text-sm font-medium text-slate-400 mb-2 w-full">
        Portfolio Heat
      </h3>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={50}
              outerRadius={70}
              dataKey="value"
              startAngle={180}
              endAngle={0}
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="text-3xl font-bold">{heatPct.toFixed(1)}%</div>
      <div className="text-xs text-slate-500">Limit {maxPct}%</div>
    </Card>
  );
}

function heatColor(used: number, max: number): string {
  const ratio = used / max;
  if (ratio >= 1) return "#ef4444";
  if (ratio >= 0.75) return "#eab308";
  return "#22c55e";
}
