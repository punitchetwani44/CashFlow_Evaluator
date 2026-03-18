"use client";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CHART_COLORS } from "@/lib/constants";

interface Props {
  categoryBreakdown: string | null;
  type?: "outflow" | "inflow";
}

const formatY = (value: number) => {
  if (value >= 100000) return `₹${(value / 100000).toFixed(1)}L`;
  if (value >= 1000) return `₹${(value / 1000).toFixed(0)}K`;
  return `₹${value.toFixed(0)}`;
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const { name, value, percent } = payload[0];
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg text-sm">
        <p className="font-semibold text-gray-700">{name}</p>
        <p className="text-gray-600">{formatY(value)}</p>
        <p className="text-gray-400">{(percent * 100).toFixed(1)}%</p>
      </div>
    );
  }
  return null;
};

export default function CategoryPieChart({ categoryBreakdown, type = "outflow" }: Props) {
  if (!categoryBreakdown) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        No data available
      </div>
    );
  }

  const parsed: Record<string, number> = JSON.parse(categoryBreakdown);
  const filtered = Object.entries(parsed)
    .filter(([key]) => key.startsWith(`${type}:`))
    .map(([key, value]) => ({
      name: key.split(":")[1],
      value,
    }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  if (!filtered.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        No {type} data for this month
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={filtered}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="45%"
          outerRadius={85}
          innerRadius={45}
          paddingAngle={2}
        >
          {filtered.map((_, index) => (
            <Cell
              key={index}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
            />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(value) =>
            value.length > 20 ? value.substring(0, 18) + "…" : value
          }
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
