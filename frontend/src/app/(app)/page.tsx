"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  getAggregateMetrics,
  getMyBusinessAccounts,
  AggregatedMetrics,
  BusinessAccount,
  DateRange,
  formatCurrency,
  formatMonth,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import MetricCard from "@/components/dashboard/MetricCard";
import InflowOutflowChart from "@/components/dashboard/InflowOutflowChart";
import NetCashflowChart from "@/components/dashboard/NetCashflowChart";
import CategoryPieChart from "@/components/dashboard/CategoryPieChart";
import LeadingIndicators from "@/components/dashboard/LeadingIndicators";
import BusinessSelector from "@/components/dashboard/BusinessSelector";
import DateRangeSelector from "@/components/dashboard/DateRangeSelector";
import ExpenseTrendChart from "@/components/dashboard/ExpenseTrendChart";
import {
  TrendingUp,
  TrendingDown,
  ArrowUpDown,
  Activity,
  RefreshCw,
  BarChart3,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";

// Returns YYYY-MM for the current month
function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const SESSION_KEY_BAS   = "dashboard_business_ids";
const SESSION_KEY_RANGE = "dashboard_date_range";

function getDefaultRange(): DateRange {
  const m = currentMonth();
  return { dateFrom: m, dateTo: m, label: "This Month" };
}

export default function DashboardPage() {
  const { activeBusinessId } = useAuth();

  const [userBAs, setUserBAs] = useState<BusinessAccount[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [dateRange, setDateRange] = useState<DateRange>(getDefaultRange());
  const [metrics, setMetrics] = useState<AggregatedMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  // Keep a stable ref to selectedIds + userBAs for use inside async closures
  const selectedIdsRef = useRef<number[]>([]);
  const userBAsRef     = useRef<BusinessAccount[]>([]);
  useEffect(() => { selectedIdsRef.current = selectedIds; }, [selectedIds]);
  useEffect(() => { userBAsRef.current = userBAs; }, [userBAs]);

  // ── On mount / business switch: load BAs and restore selections ────────────
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await getMyBusinessAccounts();
        if (!mounted) return;
        const bas: BusinessAccount[] = res.data;
        setUserBAs(bas);

        // When the active business changes, clear the stale cross-business
        // selection so the dashboard resets to just the new active business.
        sessionStorage.removeItem(SESSION_KEY_BAS);

        // Restore selectedIds from sessionStorage, filtering out stale IDs
        const validIds = new Set(bas.map((b) => b.id));
        let ids: number[] = [];
        try {
          const stored = sessionStorage.getItem(SESSION_KEY_BAS);
          if (stored) {
            ids = (JSON.parse(stored) as number[]).filter((id) => validIds.has(id));
          }
        } catch {}
        if (ids.length === 0 && activeBusinessId) ids = [activeBusinessId];
        if (ids.length === 0 && bas.length > 0) ids = [bas[0].id];
        setSelectedIds(ids);

        // Restore date range (preserved across business switches)
        try {
          const stored = sessionStorage.getItem(SESSION_KEY_RANGE);
          if (stored) setDateRange(JSON.parse(stored) as DateRange);
        } catch {}
      } catch (e) {
        console.error("Failed to load business accounts", e);
        setLoading(false);
      }
    })();
    return () => { mounted = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBusinessId]);

  // ── Fetch aggregated metrics whenever selection/range changes ───────────────
  const fetchData = useCallback(async (ids: number[], range: DateRange) => {
    if (ids.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getAggregateMetrics(ids, range.dateFrom, range.dateTo);
      setMetrics(res.data);
    } catch (err: any) {
      if (err.response?.status === 403) {
        // Access lost mid-session — trim inaccessible IDs and retry
        const current = selectedIdsRef.current;
        const known   = new Set(userBAsRef.current.map((b) => b.id));
        const trimmed = current.filter((id) => known.has(id));
        if (trimmed.length > 0 && trimmed.length < current.length) {
          setSelectedIds(trimmed);
          sessionStorage.setItem(SESSION_KEY_BAS, JSON.stringify(trimmed));
          return; // re-fetch via useEffect
        }
      }
      const msg = err.response?.data?.detail ?? err.message ?? "Failed to load metrics";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedIds.length > 0) {
      fetchData(selectedIds, dateRange);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIds, dateRange]);

  // ── Trend helpers ──────────────────────────────────────────────────────────
  const pctChange = (curr: number, prev: number | undefined) => {
    if (prev == null || prev === 0) return null;
    return ((curr - prev) / prev) * 100;
  };

  const inflowTrend  = pctChange(metrics?.total_inflow  ?? 0, metrics?.prev_total_inflow);
  const outflowTrend = pctChange(metrics?.total_outflow ?? 0, metrics?.prev_total_outflow);
  const prevLabel = metrics?.prev_period_label ? `vs ${metrics.prev_period_label}` : "vs prev period";

  // Whether we have any renderable content
  const hasData = !loading && metrics && metrics.transaction_count > 0;
  const isEmpty = !loading && !error && (!metrics || metrics.transaction_count === 0);

  return (
    <div className="p-6 space-y-6">
      {/* Header — always visible so user can change date range / business */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cashflow Dashboard</h1>
          <p className="text-sm text-gray-500">AI-powered financial overview for your business</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <BusinessSelector
            userBAs={userBAs}
            selectedIds={selectedIds}
            onChange={(ids) => {
              setSelectedIds(ids);
              sessionStorage.setItem(SESSION_KEY_BAS, JSON.stringify(ids));
            }}
          />
          <DateRangeSelector
            value={dateRange}
            onChange={(range) => {
              setDateRange(range);
              sessionStorage.setItem(SESSION_KEY_RANGE, JSON.stringify(range));
            }}
          />
          <button
            onClick={() => fetchData(selectedIds, dateRange)}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg disabled:opacity-40"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Loading skeleton (first load only) */}
      {loading && !metrics && (
        <div className="flex items-center justify-center h-64 text-gray-400">
          <RefreshCw className="animate-spin mr-2" size={20} />
          Loading dashboard…
        </div>
      )}

      {/* Empty state — shown inline so header controls remain accessible */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center gap-5 text-center px-8 py-24">
          <BarChart3 size={60} className="text-gray-300" />
          <h2 className="text-2xl font-bold text-gray-700">No Data Found</h2>
          <p className="text-gray-500 max-w-md">
            No transactions found for the selected businesses and date range.
            Try a different range or upload a bank statement.
          </p>
          <Link
            href="/upload"
            className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition"
          >
            Upload Bank Statement →
          </Link>
        </div>
      )}

      {/* >10 businesses performance warning */}
      {selectedIds.length > 10 && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
          <AlertTriangle size={16} className="flex-shrink-0" />
          Aggregating {selectedIds.length} businesses — loading may be slower than usual.
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {error}
        </div>
      )}

      {hasData && metrics && (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard
              label="Total Inflow"
              value={formatCurrency(metrics.total_inflow)}
              icon={<TrendingUp size={20} />}
              color="green"
              trend={inflowTrend !== null ? { value: inflowTrend, label: prevLabel } : undefined}
            />
            <MetricCard
              label="Total Outflow"
              value={formatCurrency(metrics.total_outflow)}
              icon={<TrendingDown size={20} />}
              color="red"
              trend={outflowTrend !== null ? { value: outflowTrend, label: prevLabel } : undefined}
            />
            <MetricCard
              label="Net Cashflow"
              value={formatCurrency(metrics.net_cashflow)}
              subValue={metrics.net_cashflow >= 0 ? "Cash Surplus" : "Cash Deficit"}
              icon={<ArrowUpDown size={20} />}
              color={metrics.net_cashflow >= 0 ? "indigo" : "amber"}
            />
            <MetricCard
              label="Indicator Cashflow"
              value={formatCurrency(metrics.indicator_cashflow)}
              subValue="Excl. Capital Movements"
              icon={<Activity size={20} />}
              color={metrics.indicator_cashflow >= 0 ? "green" : "amber"}
            />
          </div>

          {/* Period info strip */}
          <div className="flex items-center gap-2 text-xs text-gray-400 flex-wrap">
            <span className="font-medium text-gray-500">Period:</span>
            <span>{metrics.period_label}</span>
            {metrics.business_names.length > 0 && (
              <>
                <span className="text-gray-300">·</span>
                <span className="font-medium text-gray-500">Businesses:</span>
                <span className="truncate max-w-xs">{metrics.business_names.join(", ")}</span>
              </>
            )}
          </div>

          {/* Charts Row 1 */}
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Monthly Inflow vs Outflow</h3>
              <p className="text-xs text-gray-400 mb-4">
                {metrics.is_multi_month
                  ? `${metrics.period_label} breakdown`
                  : `${formatMonth(metrics.date_from)} overview`}
              </p>
              <InflowOutflowChart data={metrics.monthly_breakdown} />
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Net Cashflow Trend</h3>
              <p className="text-xs text-gray-400 mb-4">Monthly net position</p>
              <NetCashflowChart data={metrics.monthly_breakdown} />
            </div>
          </div>

          {/* Charts Row 2 */}
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Outflow by Category</h3>
              <p className="text-xs text-gray-400 mb-4">
                {metrics.is_multi_month
                  ? `${metrics.period_label} spending breakdown`
                  : `${formatMonth(metrics.date_from)} spending breakdown`}
              </p>
              <CategoryPieChart
                categoryBreakdown={metrics.category_breakdown}
                type="outflow"
              />
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Leading Indicators</h3>
              <LeadingIndicators metric={metrics} />
            </div>
          </div>

          {/* Expense Trend Chart */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Expense Trend</h3>
            <p className="text-xs text-gray-400 mb-4">
              Monthly spending vs 3-month moving average
              {metrics.monthly_breakdown.length >= 3 && (
                <span className="ml-2 inline-flex gap-3">
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm inline-block bg-[#94a3b8]" />
                    Normal
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm inline-block bg-[#ef4444]" />
                    Above trend
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm inline-block bg-[#991b1b]" />
                    {">"} 15% spike
                  </span>
                </span>
              )}
            </p>
            <ExpenseTrendChart data={metrics.monthly_breakdown} />
          </div>

          {/* Stats Footer */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center justify-between text-sm flex-wrap gap-3">
            <div className="flex gap-6">
              <div>
                <span className="text-gray-400">Transactions: </span>
                <span className="font-semibold">{metrics.transaction_count}</span>
              </div>
              <div>
                <span className="text-gray-400">Mapped: </span>
                <span className="font-semibold text-green-600">{metrics.mapped_count}</span>
              </div>
              <div>
                <span className="text-gray-400">Unmapped: </span>
                <span className="font-semibold text-amber-600">
                  {metrics.transaction_count - metrics.mapped_count}
                </span>
              </div>
            </div>
            <div className="flex gap-3">
              <Link
                href={`/transactions?month=${metrics.date_from}`}
                className="text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Review Transactions →
              </Link>
              <Link
                href={
                  metrics.is_multi_month
                    ? `/insights?date_from=${metrics.date_from}&date_to=${metrics.date_to}`
                    : `/insights?month=${metrics.date_from}`
                }
                className="text-indigo-600 hover:text-indigo-800 font-medium"
              >
                AI Insights →
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
