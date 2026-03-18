"use client";
import { useState, useMemo } from "react";
import { Transaction, updateTransaction, bulkUpdateTransactions, formatCurrency } from "@/lib/api";
import { ALL_HEADS, INFLOW_HEADS, OUTFLOW_HEADS } from "@/lib/constants";
import { Save, RefreshCw, CheckSquare, Square, X, BookMarked } from "lucide-react";
import clsx from "clsx";

interface Props {
  transactions: Transaction[];
  onRefresh: () => void;
  onReprocess?: () => void;
  loading?: boolean;
}

const PAGE_SIZE = 50;

export default function TransactionTable({
  transactions,
  onRefresh,
  onReprocess,
  loading,
}: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [edits, setEdits] = useState<Record<number, Partial<Transaction>>>({});
  const [bulkHead, setBulkHead] = useState("");
  const [bulkLearnRule, setBulkLearnRule] = useState(true);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // "Apply to future?" modal state
  const [showRuleModal, setShowRuleModal] = useState(false);
  const [pendingSaveEdits, setPendingSaveEdits] = useState<Record<number, Partial<Transaction>>>({});

  const filtered = useMemo(() => {
    return transactions.filter((t) => {
      if (statusFilter !== "all" && t.status !== statusFilter) return false;
      if (typeFilter !== "all" && t.type !== typeFilter) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return (
          t.description.toLowerCase().includes(term) ||
          (t.head || "").toLowerCase().includes(term)
        );
      }
      return true;
    });
  }, [transactions, statusFilter, typeFilter, searchTerm]);

  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  // Determine the dominant type among selected transactions for the bulk dropdown
  const bulkSelectedType = useMemo(() => {
    const selectedTxns = transactions.filter((t) => selected.has(t.id));
    if (!selectedTxns.length) return "all";
    const inCount = selectedTxns.filter((t) => t.type === "inflow").length;
    const outCount = selectedTxns.length - inCount;
    if (inCount > 0 && outCount === 0) return "inflow";
    if (outCount > 0 && inCount === 0) return "outflow";
    return "mixed";
  }, [selected, transactions]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === paginated.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(paginated.map((t) => t.id)));
    }
  };

  const setEdit = (id: number, field: string, value: string) => {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }));
  };

  /** Execute the actual save with or without creating a rule. */
  const executeSave = async (
    editsToSave: Record<number, Partial<Transaction>>,
    createRule: boolean
  ) => {
    const pending = Object.entries(editsToSave).filter(([_, v]) => Object.keys(v).length > 0);
    if (!pending.length) return;
    setSaving(true);
    try {
      await Promise.all(
        pending.map(([id, data]) =>
          updateTransaction(parseInt(id), {
            head: data.head as string | undefined,
            comments: data.comments as string | undefined,
            create_rule: createRule,
          })
        )
      );
      setEdits({});
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  /**
   * Gate: if any head changed, open the "Apply to future?" modal.
   * If only comments changed, save without creating a rule.
   */
  const saveAll = () => {
    const pending = Object.entries(edits).filter(([_, v]) => Object.keys(v).length > 0);
    if (!pending.length) return;

    const hasHeadChange = pending.some(([_, v]) => v.head !== undefined);
    if (hasHeadChange) {
      setPendingSaveEdits({ ...edits });
      setShowRuleModal(true);
    } else {
      // Only comments changed — save without learning
      executeSave(edits, false);
    }
  };

  const bulkUpdate = async () => {
    if (!bulkHead || selected.size === 0) return;
    setSaving(true);
    try {
      await bulkUpdateTransactions(Array.from(selected), {
        head: bulkHead,
        create_rule: bulkLearnRule,
      });
      setSelected(new Set());
      setBulkHead("");
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const getRowClass = (t: Transaction) => {
    if (edits[t.id]?.head !== undefined) return "bg-indigo-50 border-l-4 border-indigo-400";
    if (t.is_user_modified) return "bg-indigo-50 border-l-4 border-indigo-300";
    if (t.status === "unmapped") return "bg-amber-50 border-l-4 border-amber-400";
    return "bg-white hover:bg-gray-50";
  };

  const unmappedCount = transactions.filter((t) => t.status === "unmapped").length;
  const headChangeCount = Object.values(edits).filter((v) => v.head !== undefined).length;

  return (
    <div className="space-y-3">

      {/* ── "Apply to future?" modal ─────────────────────────────────────── */}
      {showRuleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md mx-4">
            <div className="flex items-start gap-3 mb-4">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <BookMarked size={20} className="text-indigo-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-base">
                  Save category changes?
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  You updated {headChangeCount} transaction{headChangeCount !== 1 ? "s'" : "'"} category.
                  Should the system learn these mappings for future auto-classification?
                </p>
              </div>
            </div>
            <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-3 mb-5 text-sm text-indigo-800">
              <strong>Yes, Learn Mappings</strong> — new rules will fire automatically on future uploads and re-processes, reducing AI calls.
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowRuleModal(false);
                  setPendingSaveEdits({});
                }}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowRuleModal(false);
                  executeSave(pendingSaveEdits, false);
                  setPendingSaveEdits({});
                }}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Save Only
              </button>
              <button
                onClick={() => {
                  setShowRuleModal(false);
                  executeSave(pendingSaveEdits, true);
                  setPendingSaveEdits({});
                }}
                className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium"
              >
                Yes, Learn Mappings ✓
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stats bar */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-gray-600">
          <strong>{transactions.length}</strong> transactions
        </span>
        {unmappedCount > 0 && (
          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
            {unmappedCount} unmapped
          </span>
        )}
        {Object.keys(edits).length > 0 && (
          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">
            {Object.keys(edits).length} pending changes
          </span>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 bg-white border border-gray-200 rounded-lg p-2">
        <input
          type="text"
          placeholder="Search description or head…"
          value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded px-3 py-1.5 text-sm flex-1 min-w-40 outline-none focus:border-indigo-400"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded px-2 py-1.5 text-sm outline-none focus:border-indigo-400"
        >
          <option value="all">All Status</option>
          <option value="mapped">Mapped</option>
          <option value="unmapped">Unmapped</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded px-2 py-1.5 text-sm outline-none focus:border-indigo-400"
        >
          <option value="all">All Types</option>
          <option value="inflow">Inflow</option>
          <option value="outflow">Outflow</option>
        </select>
        <div className="flex-1" />
        {Object.keys(edits).length > 0 && (
          <button
            onClick={saveAll}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save size={14} />
            {saving ? "Saving…" : `Save Changes (${Object.keys(edits).length})`}
          </button>
        )}
        {onReprocess && (
          <button
            onClick={onReprocess}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200"
          >
            <RefreshCw size={14} />
            Re-process Month
          </button>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 bg-indigo-50 border border-indigo-200 rounded-lg p-2.5">
          <span className="text-sm font-medium text-indigo-700">
            {selected.size} selected
          </span>
          <select
            value={bulkHead}
            onChange={(e) => setBulkHead(e.target.value)}
            className="border border-indigo-300 rounded px-2 py-1 text-sm outline-none flex-1 max-w-xs bg-white"
          >
            <option value="">— Select Head —</option>
            {bulkSelectedType === "inflow" ? (
              INFLOW_HEADS.map((h) => <option key={h} value={h}>{h}</option>)
            ) : bulkSelectedType === "outflow" ? (
              OUTFLOW_HEADS.map((h) => <option key={h} value={h}>{h}</option>)
            ) : (
              <>
                <optgroup label="── Inflow ──">
                  {INFLOW_HEADS.map((h) => <option key={h} value={h}>{h}</option>)}
                </optgroup>
                <optgroup label="── Outflow ──">
                  {OUTFLOW_HEADS.map((h) => <option key={h} value={h}>{h}</option>)}
                </optgroup>
              </>
            )}
          </select>
          {/* Learn mapping checkbox */}
          <label className="flex items-center gap-1.5 text-sm text-indigo-700 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={bulkLearnRule}
              onChange={(e) => setBulkLearnRule(e.target.checked)}
              className="accent-indigo-600 w-3.5 h-3.5"
            />
            Learn mapping
          </label>
          <button
            onClick={bulkUpdate}
            disabled={!bulkHead || saving}
            className="px-3 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            Apply to Selected
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="p-1 text-gray-400 hover:text-gray-600"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-3 py-3 text-left w-8">
                  <button onClick={toggleSelectAll} className="text-gray-500 hover:text-gray-800">
                    {selected.size === paginated.length && paginated.length > 0
                      ? <CheckSquare size={16} />
                      : <Square size={16} />}
                  </button>
                </th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Description</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide min-w-40">Head</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Comment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-gray-400">
                    Loading transactions…
                  </td>
                </tr>
              ) : paginated.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-gray-400">
                    No transactions found
                  </td>
                </tr>
              ) : (
                paginated.map((t) => {
                  const editedHead = edits[t.id]?.head;
                  const editedComment = edits[t.id]?.comments;
                  const displayHead = editedHead !== undefined ? editedHead : t.head;
                  return (
                    <tr key={t.id} className={clsx("transition-colors", getRowClass(t))}>
                      <td className="px-3 py-2.5">
                        <button
                          onClick={() => toggleSelect(t.id)}
                          className="text-gray-400 hover:text-indigo-600"
                        >
                          {selected.has(t.id) ? <CheckSquare size={15} className="text-indigo-600" /> : <Square size={15} />}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap">{t.date}</td>
                      <td className="px-3 py-2.5 max-w-xs">
                        <p className="text-gray-800 truncate" title={t.description}>
                          {t.description}
                        </p>
                        {t.is_user_modified && (
                          <span className="text-xs text-indigo-500">✏ edited</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right font-medium whitespace-nowrap">
                        <span className={t.type === "inflow" ? "text-green-600" : "text-red-600"}>
                          {formatCurrency(t.amount)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-xs font-medium",
                            t.type === "inflow"
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-700"
                          )}
                        >
                          {t.type}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <select
                          value={displayHead || ""}
                          onChange={(e) => setEdit(t.id, "head", e.target.value)}
                          className="w-full border border-gray-200 rounded px-2 py-1 text-xs outline-none focus:border-indigo-400 bg-transparent"
                        >
                          <option value="">— Select Head —</option>
                          {(t.type === "inflow" ? INFLOW_HEADS : OUTFLOW_HEADS).map((h) => (
                            <option key={h} value={h}>{h}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-xs font-medium",
                            t.status === "mapped"
                              ? "bg-green-100 text-green-700"
                              : "bg-amber-100 text-amber-700"
                          )}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <input
                          type="text"
                          value={editedComment !== undefined ? (editedComment ?? "") : (t.comments ?? "")}
                          onChange={(e) => setEdit(t.id, "comments", e.target.value)}
                          placeholder="Add note…"
                          className="border border-gray-200 rounded px-2 py-1 text-xs w-full outline-none focus:border-indigo-400 bg-transparent"
                        />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of{" "}
            {filtered.length}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              ← Prev
            </button>
            <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded font-medium">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
