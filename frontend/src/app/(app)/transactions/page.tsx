"use client";
import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  getTransactions,
  getMonths,
  getMyBusinessAccounts,
  reprocessMonth,
  Transaction,
  formatMonth,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import TransactionTable from "@/components/transactions/TransactionTable";
import { ChevronDown, RefreshCw, Loader, Building2 } from "lucide-react";

function TransactionsContent() {
  const searchParams = useSearchParams();
  const initialMonth = searchParams.get("month") || "";
  const { activeBusinessId } = useAuth();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [months, setMonths] = useState<string[]>([]);
  const [selectedMonth, setSelectedMonth] = useState(initialMonth);
  const [businessName, setBusinessName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessResult, setReprocessResult] = useState<string>("");

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: 1000 };
      if (selectedMonth) params.month = selectedMonth;
      const { data } = await getTransactions(params);
      setTransactions(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [selectedMonth]);

  // ── Re-fetch months and reset month selection when active business changes ──
  useEffect(() => {
    // Reset so we don't show the previous business's month while loading
    setSelectedMonth("");
    setTransactions([]);
    setReprocessResult("");

    const fetchMonths = async () => {
      try {
        const { data } = await getMonths();
        const sorted = data.sort().reverse();
        setMonths(sorted);
        if (sorted.length > 0) {
          setSelectedMonth(sorted[0]);
        }
      } catch (e) {
        console.error(e);
      }
    };

    // Resolve business name for the header badge
    const fetchBusinessName = async () => {
      try {
        const { data } = await getMyBusinessAccounts();
        const ba = data.find((b) => b.id === activeBusinessId);
        setBusinessName(ba?.name ?? "");
      } catch {
        setBusinessName("");
      }
    };

    fetchMonths();
    fetchBusinessName();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBusinessId]);

  useEffect(() => {
    if (selectedMonth || months.length > 0) {
      fetchTransactions();
    }
  }, [selectedMonth, fetchTransactions]);

  const handleReprocess = async () => {
    if (!selectedMonth) return;
    setReprocessing(true);
    setReprocessResult("");
    try {
      const { data } = await reprocessMonth(selectedMonth);
      setReprocessResult(
        `Reprocessed ${data.reprocessed} transactions → ${data.mapped} mapped, ${data.unmapped} unmapped`
      );
      await fetchTransactions();
    } catch (e: any) {
      setReprocessResult("Reprocessing failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setReprocessing(false);
    }
  };

  const unmapped = transactions.filter((t) => t.status === "unmapped").length;

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Transaction Review</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review and correct AI-classified transactions
          </p>
          {businessName && (
            <span className="inline-flex items-center gap-1.5 mt-1.5 px-2.5 py-0.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full border border-indigo-100">
              <Building2 size={11} />
              {businessName}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Month selector */}
          <div className="relative">
            <select
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 border border-gray-200 rounded-lg text-sm font-medium bg-white focus:outline-none focus:border-indigo-400"
            >
              <option value="">All Months</option>
              {months.map((m) => (
                <option key={m} value={m}>
                  {formatMonth(m)}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-3 text-gray-400 pointer-events-none" />
          </div>
          <button
            onClick={fetchTransactions}
            className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Summary bar */}
      {selectedMonth && !loading && (
        <div className="flex items-center gap-4 bg-white border border-gray-200 rounded-lg p-3 text-sm">
          <span className="font-semibold text-gray-700">{formatMonth(selectedMonth)}</span>
          <span className="text-gray-400">·</span>
          <span className="text-gray-600">{transactions.length} transactions</span>
          {unmapped > 0 && (
            <>
              <span className="text-gray-400">·</span>
              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">
                {unmapped} unmapped — review below
              </span>
            </>
          )}
          <div className="flex-1" />
          {selectedMonth && (
            <button
              onClick={handleReprocess}
              disabled={reprocessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 text-sm rounded-lg hover:bg-indigo-100 disabled:opacity-50"
            >
              {reprocessing ? <Loader size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              {reprocessing ? "Re-processing…" : "Re-classify Month"}
            </button>
          )}
        </div>
      )}

      {reprocessResult && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-sm text-indigo-700">
          {reprocessResult}
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-5 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded border-l-4 border-amber-400 bg-amber-50" />
          Unmapped (needs review)
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded border-l-4 border-indigo-400 bg-indigo-50" />
          User-modified
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-white border border-gray-200" />
          Auto-classified
        </div>
      </div>

      {/* Table */}
      <TransactionTable
        transactions={transactions}
        loading={loading}
        onRefresh={fetchTransactions}
        onReprocess={selectedMonth ? handleReprocess : undefined}
      />
    </div>
  );
}

export default function TransactionsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen text-gray-400">
        <Loader className="animate-spin mr-2" size={20} />
        Loading…
      </div>
    }>
      <TransactionsContent />
    </Suspense>
  );
}
