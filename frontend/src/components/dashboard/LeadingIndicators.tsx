"use client";
import clsx from "clsx";

// Accept any object that has the fields we need — works with both
// MonthlyMetric (single-month) and AggregatedMetrics (multi-range).
interface MetricSummary {
  fixed_cost_ratio: number;
  payroll_ratio: number;
  cash_runway: number | null;
  vendor_dependency: number | null;
  net_cashflow: number;
  indicator_cashflow: number;
}

interface Props {
  metric: MetricSummary;
}

interface IndicatorRowProps {
  label: string;
  value: string;
  benchmark: string;
  status: "good" | "warning" | "alert";
  description: string;
}

function IndicatorRow({ label, value, benchmark, status, description }: IndicatorRowProps) {
  const statusColors = {
    good: "text-green-600 bg-green-50 border-green-200",
    warning: "text-amber-600 bg-amber-50 border-amber-200",
    alert: "text-red-600 bg-red-50 border-red-200",
  };
  const dotColors = {
    good: "bg-green-500",
    warning: "bg-amber-500",
    alert: "bg-red-500",
  };
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-start gap-3">
        <div className={clsx("w-2 h-2 rounded-full mt-1.5 flex-shrink-0", dotColors[status])} />
        <div>
          <p className="text-sm font-medium text-gray-800">{label}</p>
          <p className="text-xs text-gray-400">{description}</p>
        </div>
      </div>
      <div className="text-right">
        <span
          className={clsx(
            "text-sm font-bold px-2.5 py-1 rounded-full border",
            statusColors[status]
          )}
        >
          {value}
        </span>
        <p className="text-xs text-gray-400 mt-1">Benchmark: {benchmark}</p>
      </div>
    </div>
  );
}

export default function LeadingIndicators({ metric }: Props) {
  const fixedCostRatio = metric.fixed_cost_ratio || 0;
  const payrollRatio = metric.payroll_ratio || 0;
  const cashRunway = metric.cash_runway;
  const vendorDep = metric.vendor_dependency;

  const fixedStatus =
    fixedCostRatio <= 40 ? "good" : fixedCostRatio <= 55 ? "warning" : "alert";
  const payrollStatus =
    payrollRatio <= 30 ? "good" : payrollRatio <= 40 ? "warning" : "alert";
  const runwayStatus =
    !cashRunway ? "warning"
    : cashRunway >= 4 ? "good"
    : cashRunway >= 2 ? "warning"
    : "alert";
  const vendorStatus =
    !vendorDep ? "good"
    : vendorDep <= 40 ? "good"
    : vendorDep <= 65 ? "warning"
    : "alert";

  const indicators: IndicatorRowProps[] = [
    {
      label: "Fixed Cost Ratio",
      value: `${fixedCostRatio.toFixed(1)}%`,
      benchmark: "< 50%",
      status: fixedStatus,
      description: "Salaries + Rent + EMI + Utilities as % of inflow",
    },
    {
      label: "Payroll Ratio",
      value: `${payrollRatio.toFixed(1)}%`,
      benchmark: "< 35%",
      status: payrollStatus,
      description: "Total payroll as % of inflow",
    },
    {
      label: "Cash Runway",
      value: cashRunway ? `${cashRunway.toFixed(1)} mo` : "N/A",
      benchmark: "> 3 months",
      status: runwayStatus,
      description: "Months of operations covered by current balance",
    },
    {
      label: "Vendor Dependency",
      value: vendorDep ? `${vendorDep.toFixed(1)}%` : "N/A",
      benchmark: "< 50%",
      status: vendorStatus,
      description: "Top vendor as % of total supplier payments",
    },
  ];

  // Net cashflow health
  const netPositive = metric.net_cashflow >= 0;

  return (
    <div>
      <div
        className={clsx(
          "mb-4 p-3 rounded-lg border text-sm font-medium",
          netPositive
            ? "bg-green-50 border-green-200 text-green-700"
            : "bg-red-50 border-red-200 text-red-700"
        )}
      >
        {netPositive ? "✅ " : "⚠️ "}
        Indicator Cashflow:{" "}
        <span className="font-bold">
          {metric.indicator_cashflow >= 0 ? "+" : ""}
          ₹{Math.abs(metric.indicator_cashflow).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
        </span>
        {" "}&nbsp;|&nbsp;{" "}
        Net Cashflow:{" "}
        <span className="font-bold">
          {metric.net_cashflow >= 0 ? "+" : ""}
          ₹{Math.abs(metric.net_cashflow).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
        </span>
      </div>
      {indicators.map((ind) => (
        <IndicatorRow key={ind.label} {...ind} />
      ))}
    </div>
  );
}
