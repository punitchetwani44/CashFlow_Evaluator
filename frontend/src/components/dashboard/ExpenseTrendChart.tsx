"use client";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { MonthlyBreakdown, formatMonth } from "@/lib/api";

interface Props {
  data: MonthlyBreakdown[];
}

// ── Y-axis + tooltip currency formatter (matches existing charts) ─────────────
const formatY = (value: number) => {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(1)}Cr`;
  if (value >= 100_000)    return `₹${(value / 100_000).toFixed(1)}L`;
  if (value >= 1_000)      return `₹${(value / 1_000).toFixed(0)}K`;
  return `₹${value}`;
};

// ── Internal chart data shape ────────────────────────────────────────────────
interface ChartPoint {
  month: string;
  Expense: number;
  SMA: number | null;
  // kept for Cell colour logic (same values, typed numbers)
  _outflow: number;
  _sma: number | null;
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || !payload.length) return null;

  const expEntry = payload.find((p: any) => p.dataKey === "Expense");
  const smaEntry = payload.find((p: any) => p.dataKey === "SMA");

  const expense = expEntry?.value as number | undefined;
  const sma     = (smaEntry?.value as number | null) ?? null;

  let spikeMsg: { text: string; color: string } | null = null;
  if (expense != null && sma != null) {
    if (expense > sma * 1.15) {
      spikeMsg = { text: "Spending significantly above normal trend", color: "#991b1b" };
    } else if (expense > sma) {
      spikeMsg = { text: "Spending above normal trend", color: "#ef4444" };
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg text-sm min-w-[200px]">
      <p className="font-semibold text-gray-700 mb-2">{label}</p>
      {expense != null && (
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Monthly Expense:</span>
          <span className="font-medium">{formatY(expense)}</span>
        </div>
      )}
      {sma != null && (
        <div className="flex justify-between gap-4 mt-1">
          <span style={{ color: "#f59e0b" }}>3-Month SMA:</span>
          <span className="font-medium">{formatY(sma)}</span>
        </div>
      )}
      {spikeMsg && (
        <p className="mt-2 text-xs font-semibold" style={{ color: spikeMsg.color }}>
          ⚠ {spikeMsg.text}
        </p>
      )}
    </div>
  );
};

// ── Bar colour helper ─────────────────────────────────────────────────────────
function barFill(outflow: number, sma: number | null): string {
  if (sma == null)           return "#94a3b8"; // slate  — no SMA yet (first 2 months)
  if (outflow > sma * 1.15)  return "#991b1b"; // dark red — significant spike (>15%)
  if (outflow > sma)         return "#ef4444"; // red       — above trend
  return "#94a3b8";                            // slate     — within trend
}

// ── Chart component ───────────────────────────────────────────────────────────
export default function ExpenseTrendChart({ data: rawData }: Props) {
  // Need ≥ 3 months for a meaningful SMA line
  if (rawData.length < 3) {
    return (
      <div className="flex items-center justify-center h-48 text-center px-6">
        <p className="text-sm text-gray-400">
          Minimum 3 months of data required for trend analysis
        </p>
      </div>
    );
  }

  const data: ChartPoint[] = rawData.map((m) => ({
    month:    formatMonth(m.month),
    Expense:  m.total_outflow,
    SMA:      m.sma_3 ?? null,
    _outflow: m.total_outflow,
    _sma:     m.sma_3 ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart
        data={data}
        barSize={20}
        margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={formatY} tick={{ fontSize: 11 }} width={65} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />

        {/* Monthly expense bars — colour per bar via Cell */}
        <Bar dataKey="Expense" name="Monthly Expense" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={barFill(entry._outflow, entry._sma)} />
          ))}
        </Bar>

        {/* 3-month SMA line — starts at month 3 (null for months 1 & 2) */}
        <Line
          type="monotone"
          dataKey="SMA"
          name="3-Month SMA"
          stroke="#f59e0b"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          activeDot={{ r: 4, fill: "#f59e0b" }}
          connectNulls={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
