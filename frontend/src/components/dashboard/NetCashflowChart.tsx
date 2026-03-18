"use client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";
import { formatMonth } from "@/lib/api";

interface ChartDataPoint {
  month: string;
  net_cashflow: number;
}

interface Props {
  data: ChartDataPoint[];
}

const formatY = (value: number) => {
  if (Math.abs(value) >= 10000000) return `₹${(value / 10000000).toFixed(1)}Cr`;
  if (Math.abs(value) >= 100000) return `₹${(value / 100000).toFixed(1)}L`;
  if (Math.abs(value) >= 1000) return `₹${(value / 1000).toFixed(0)}K`;
  return `₹${value}`;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const val = payload[0].value;
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg text-sm">
        <p className="font-semibold text-gray-700 mb-1">{label}</p>
        <p className={val >= 0 ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
          Net Cashflow: {formatY(val)}
        </p>
      </div>
    );
  }
  return null;
};

export default function NetCashflowChart({ data: rawData }: Props) {
  const data = rawData.map((m) => ({
    month: formatMonth(m.month),
    "Net Cashflow": m.net_cashflow,
  }));

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <defs>
          <linearGradient id="netGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={formatY} tick={{ fontSize: 11 }} width={65} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="4 4" />
        <Area
          type="monotone"
          dataKey="Net Cashflow"
          stroke="#6366f1"
          strokeWidth={2}
          fill="url(#netGradient)"
          dot={{ fill: "#6366f1", r: 3 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
