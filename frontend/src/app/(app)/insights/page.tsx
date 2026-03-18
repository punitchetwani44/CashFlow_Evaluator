"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  getMonths,
  getInsights,
  generateInsights,
  getMonthMetrics,
  InsightItem,
  MonthlyMetric,
  formatMonth,
  formatCurrency,
} from "@/lib/api";
import { INSIGHT_COLORS, INSIGHT_ICONS } from "@/lib/constants";
import {
  ChevronDown,
  Sparkles,
  Loader,
  TrendingUp,
  TrendingDown,
  ArrowUpDown,
} from "lucide-react";
import clsx from "clsx";

function InsightsContent() {
  const searchParams = useSearchParams();
  const initialMonth = searchParams.get("month") || "";

  const [months, setMonths] = useState<string[]>([]);
  const [selectedMonth, setSelectedMonth] = useState(initialMonth);
  const [insights, setInsights] = useState<InsightItem[] | null>(null);
  const [metric, setMetric] = useState<MonthlyMetric | null>(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<string>("");
  const [error, setError] = useState("");

  const fetchMonths = async () => {
    try {
      const { data } = await getMonths();
      const sorted = data.sort().reverse();
      setMonths(sorted);
      if (!selectedMonth && sorted.length > 0) {
        setSelectedMonth(sorted[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchInsights = async (month: string) => {
    setLoading(true);
    setError("");
    try {
      const { data } = await getInsights(month);
      setInsights(JSON.parse(data.insights));
      setGeneratedAt(data.generated_at);
    } catch (e: any) {
      if (e.response?.status === 404) {
        setInsights(null);
      } else {
        setError("Failed to load insights");
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchMetric = async (month: string) => {
    try {
      const { data } = await getMonthMetrics(month);
      setMetric(data);
    } catch {
      setMetric(null);
    }
  };

  useEffect(() => {
    fetchMonths();
  }, []);

  useEffect(() => {
    if (selectedMonth) {
      fetchInsights(selectedMonth);
      fetchMetric(selectedMonth);
    }
  }, [selectedMonth]);

  const handleGenerate = async () => {
    if (!selectedMonth) return;
    setGenerating(true);
    setError("");
    try {
      const { data } = await generateInsights(selectedMonth);
      setInsights(JSON.parse(data.insights));
      setGeneratedAt(data.generated_at);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to generate insights");
    } finally {
      setGenerating(false);
    }
  };

  const categoryOrder = ["alert", "warning", "positive", "info"];
  const sortedInsights = insights
    ? [...insights].sort(
        (a, b) => categoryOrder.indexOf(a.category) - categoryOrder.indexOf(b.category)
      )
    : [];

  return (
    <div className="p-6 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles size={24} className="text-indigo-500" />
            AI Financial Insights
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            GPT-4o-mini powered analysis with Indian SME benchmarks
          </p>
        </div>
        <div className="relative">
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 border border-gray-200 rounded-lg text-sm font-medium bg-white focus:outline-none focus:border-indigo-400"
          >
            <option value="">Select Month</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {formatMonth(m)}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="absolute right-2.5 top-3 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {/* Monthly summary */}
      {metric && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="flex items-center justify-center gap-2 text-green-600 mb-1">
              <TrendingUp size={16} />
              <span className="text-xs font-medium">Total Inflow</span>
            </div>
            <p className="text-xl font-bold text-gray-800">{formatCurrency(metric.total_inflow)}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="flex items-center justify-center gap-2 text-red-600 mb-1">
              <TrendingDown size={16} />
              <span className="text-xs font-medium">Total Outflow</span>
            </div>
            <p className="text-xl font-bold text-gray-800">{formatCurrency(metric.total_outflow)}</p>
          </div>
          <div
            className={clsx(
              "border rounded-xl p-4 text-center",
              metric.net_cashflow >= 0
                ? "bg-green-50 border-green-200"
                : "bg-red-50 border-red-200"
            )}
          >
            <div className="flex items-center justify-center gap-2 mb-1">
              <ArrowUpDown
                size={16}
                className={metric.net_cashflow >= 0 ? "text-green-600" : "text-red-600"}
              />
              <span className="text-xs font-medium text-gray-600">Net Cashflow</span>
            </div>
            <p
              className={clsx(
                "text-xl font-bold",
                metric.net_cashflow >= 0 ? "text-green-700" : "text-red-700"
              )}
            >
              {metric.net_cashflow >= 0 ? "+" : ""}
              {formatCurrency(metric.net_cashflow)}
            </p>
          </div>
        </div>
      )}

      {/* Generate button */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          {generatedAt && (
            <>
              Last generated: {new Date(generatedAt).toLocaleString("en-IN")}
            </>
          )}
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating || !selectedMonth}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          {generating ? (
            <Loader size={16} className="animate-spin" />
          ) : (
            <Sparkles size={16} />
          )}
          {generating ? "Generating…" : insights ? "Regenerate Insights" : "Generate Insights"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Insights */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">
          <Loader className="animate-spin mx-auto mb-3" size={24} />
          Loading insights…
        </div>
      ) : sortedInsights.length > 0 ? (
        <div className="space-y-3">
          {sortedInsights.map((item, i) => (
            <div
              key={i}
              className={clsx(
                "border-l-4 rounded-r-xl p-4 flex items-start gap-3",
                INSIGHT_COLORS[item.category] || "border-gray-400 bg-gray-50"
              )}
            >
              <span className="text-xl flex-shrink-0 mt-0.5">
                {INSIGHT_ICONS[item.category] || "ℹ️"}
              </span>
              <div className="flex-1">
                <p className="text-gray-800 leading-relaxed">{item.insight}</p>
                {item.metric && (
                  <span className="inline-block mt-2 text-xs px-2 py-0.5 bg-white bg-opacity-70 rounded-full text-gray-500 border border-gray-200">
                    {item.metric}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : !generating && selectedMonth ? (
        <div className="text-center py-12 border border-dashed border-gray-200 rounded-xl">
          <Sparkles size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">No insights generated yet for {formatMonth(selectedMonth)}</p>
          <p className="text-sm text-gray-400 mt-1">
            Click "Generate Insights" to get AI-powered financial analysis
          </p>
        </div>
      ) : null}

      {/* Leading indicators */}
      {metric && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            Leading Indicator Benchmarks
          </h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Fixed Cost Ratio</span>
              <span
                className={clsx(
                  "font-semibold",
                  metric.fixed_cost_ratio <= 50 ? "text-green-600" : "text-red-600"
                )}
              >
                {metric.fixed_cost_ratio.toFixed(1)}%
                <span className="text-xs text-gray-400 font-normal ml-1">(bench &lt;50%)</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Payroll Ratio</span>
              <span
                className={clsx(
                  "font-semibold",
                  metric.payroll_ratio <= 35 ? "text-green-600" : "text-red-600"
                )}
              >
                {metric.payroll_ratio.toFixed(1)}%
                <span className="text-xs text-gray-400 font-normal ml-1">(bench &lt;35%)</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Cash Runway</span>
              <span
                className={clsx(
                  "font-semibold",
                  !metric.cash_runway
                    ? "text-gray-400"
                    : metric.cash_runway >= 3
                    ? "text-green-600"
                    : "text-red-600"
                )}
              >
                {metric.cash_runway ? `${metric.cash_runway.toFixed(1)} mo` : "N/A"}
                <span className="text-xs text-gray-400 font-normal ml-1">(bench &gt;3 mo)</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-gray-600">Indicator CF</span>
              <span
                className={clsx(
                  "font-semibold",
                  metric.indicator_cashflow >= 0 ? "text-green-600" : "text-red-600"
                )}
              >
                {formatCurrency(metric.indicator_cashflow)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen text-gray-400">
        <Loader className="animate-spin mr-2" size={20} />
        Loading…
      </div>
    }>
      <InsightsContent />
    </Suspense>
  );
}
