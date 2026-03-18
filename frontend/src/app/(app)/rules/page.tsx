"use client";
import { useState, useEffect, useMemo } from "react";
import {
  getRules,
  getRulesStats,
  createRule,
  updateRule,
  deleteRule,
  ClassificationRule,
  RulesStats,
} from "@/lib/api";
import { ALL_HEADS, INFLOW_HEADS, OUTFLOW_HEADS } from "@/lib/constants";
import {
  Plus,
  Trash2,
  Lock,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
  Search,
  ChevronDown,
  X,
} from "lucide-react";
import clsx from "clsx";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const RULE_TYPE_LABELS: Record<string, string> = {
  user_learned:  "User Learned",
  vendor_exact:  "Vendor Match",
  regex_keyword: "Regex",
};

const RULE_TYPE_COLORS: Record<string, string> = {
  user_learned:  "bg-purple-100 text-purple-700",
  vendor_exact:  "bg-blue-100 text-blue-700",
  regex_keyword: "bg-orange-100 text-orange-700",
};

const FILTER_TABS = [
  { key: "all",          label: "All" },
  { key: "vendor_exact", label: "Vendor Match" },
  { key: "regex_keyword",label: "Regex" },
  { key: "user_learned", label: "User Learned" },
];

// ─── Add Rule Modal ───────────────────────────────────────────────────────────

function AddRuleModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [ruleType, setRuleType] = useState<"user_learned" | "vendor_exact" | "regex_keyword">("user_learned");
  const [keyPhrase, setKeyPhrase] = useState("");
  const [pattern, setPattern] = useState("");
  const [vendor, setVendor] = useState("");
  const [head, setHead] = useState("");
  const [flow, setFlow] = useState<"inflow" | "outflow">("outflow");
  const [confidence, setConfidence] = useState(0.95);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const headOptions = flow === "inflow" ? INFLOW_HEADS : OUTFLOW_HEADS;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!head) { setError("Please select a head."); return; }
    if (ruleType === "user_learned" && !keyPhrase.trim()) { setError("Key phrase is required."); return; }
    if (ruleType === "vendor_exact" && !vendor.trim()) { setError("Vendor token is required."); return; }
    if (ruleType === "regex_keyword" && !pattern.trim()) { setError("Regex pattern is required."); return; }

    setSaving(true);
    setError("");
    try {
      let kp = keyPhrase.trim();
      if (ruleType === "vendor_exact") kp = `__vendor__${vendor.trim().toLowerCase()}`;
      else if (ruleType === "regex_keyword") kp = `__regex_custom__${Date.now()}`;

      await createRule({
        key_phrase: kp,
        head,
        type: flow,
        rule_type: ruleType,
        pattern: ruleType === "regex_keyword" ? pattern.trim() : undefined,
        normalized_vendor: ruleType === "vendor_exact" ? vendor.trim().toLowerCase() : undefined,
        confidence,
        scope: "user",
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create rule.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold text-gray-900 text-base">Add Classification Rule</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Rule type */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Rule Type</label>
            <div className="flex gap-2">
              {(["user_learned", "vendor_exact", "regex_keyword"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setRuleType(t)}
                  className={clsx(
                    "px-3 py-1.5 text-xs rounded-lg border font-medium transition-colors",
                    ruleType === t
                      ? "bg-indigo-600 text-white border-indigo-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-indigo-400"
                  )}
                >
                  {RULE_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
          </div>

          {/* Dynamic input based on rule type */}
          {ruleType === "user_learned" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Key Phrase <span className="text-gray-400 font-normal">(words extracted from description)</span>
              </label>
              <input
                type="text"
                value={keyPhrase}
                onChange={(e) => setKeyPhrase(e.target.value)}
                placeholder="e.g. aws cloud subscription"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-400"
              />
            </div>
          )}

          {ruleType === "vendor_exact" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Vendor Token <span className="text-gray-400 font-normal">(lowercase, single word)</span>
              </label>
              <input
                type="text"
                value={vendor}
                onChange={(e) => setVendor(e.target.value.toLowerCase().replace(/\s+/g, ""))}
                placeholder="e.g. zomato"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-400 font-mono"
              />
            </div>
          )}

          {ruleType === "regex_keyword" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Regex Pattern <span className="text-gray-400 font-normal">(Python re syntax, case-insensitive)</span>
              </label>
              <input
                type="text"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                placeholder={`e.g. \\bsalary\\b|\\bpayroll\\b`}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-400 font-mono"
              />
            </div>
          )}

          {/* Flow type */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Flow Type</label>
            <div className="flex gap-2">
              {(["inflow", "outflow"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => { setFlow(f); setHead(""); }}
                  className={clsx(
                    "px-3 py-1.5 text-xs rounded-lg border font-medium capitalize",
                    flow === f
                      ? f === "inflow" ? "bg-green-600 text-white border-green-600" : "bg-red-600 text-white border-red-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Head */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Cashflow Head</label>
            <select
              value={head}
              onChange={(e) => setHead(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-400"
            >
              <option value="">— Select Head —</option>
              {headOptions.map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>

          {/* Confidence */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Confidence: <span className="text-indigo-600 font-semibold">{(confidence * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>50% — Needs Review</span>
              <span>80% — Auto-map</span>
              <span>100%</span>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-2 justify-end pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Create Rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function RulesPage() {
  const [rules, setRules] = useState<ClassificationRule[]>([]);
  const [stats, setStats] = useState<RulesStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState("all");
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [rulesRes, statsRes] = await Promise.all([getRules(), getRulesStats()]);
      setRules(rulesRes.data);
      setStats(statsRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const filtered = useMemo(() => {
    return rules.filter((r) => {
      if (filterTab !== "all" && r.rule_type !== filterTab) return false;
      if (search) {
        const s = search.toLowerCase();
        return (
          r.key_phrase.toLowerCase().includes(s) ||
          r.head.toLowerCase().includes(s) ||
          (r.pattern || "").toLowerCase().includes(s) ||
          (r.normalized_vendor || "").toLowerCase().includes(s)
        );
      }
      return true;
    });
  }, [rules, filterTab, search]);

  const handleToggle = async (rule: ClassificationRule) => {
    setTogglingId(rule.id);
    try {
      await updateRule(rule.id, { is_enabled: !rule.is_enabled });
      await fetchAll();
    } catch (e) {
      console.error(e);
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (rule: ClassificationRule) => {
    if (!confirm(`Delete rule "${rule.key_phrase}"? This cannot be undone.`)) return;
    setDeletingId(rule.id);
    try {
      await deleteRule(rule.id);
      await fetchAll();
    } catch (e) {
      console.error(e);
    } finally {
      setDeletingId(null);
    }
  };

  const displayPhrase = (rule: ClassificationRule) => {
    if (rule.rule_type === "vendor_exact") return rule.normalized_vendor || rule.key_phrase;
    if (rule.rule_type === "regex_keyword") return rule.pattern || rule.key_phrase;
    return rule.key_phrase;
  };

  return (
    <div className="p-6 max-w-6xl">
      {showAddModal && (
        <AddRuleModal
          onClose={() => setShowAddModal(false)}
          onSaved={fetchAll}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Classification Rules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Rules run before AI — reducing API costs and improving accuracy.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus size={14} />
            Add Rule
          </button>
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-6">
          {[
            { label: "Total Rules",   value: stats.total,         color: "text-gray-800" },
            { label: "Active",        value: stats.active,        color: "text-green-600" },
            { label: "User Learned",  value: stats.user_learned,  color: "text-purple-600" },
            { label: "Vendor Match",  value: stats.vendor_exact,  color: "text-blue-600" },
            { label: "Regex",         value: stats.regex_keyword, color: "text-orange-600" },
            { label: "System Rules",  value: stats.system_rules,  color: "text-slate-600" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-xl p-4 text-center">
              <p className={clsx("text-2xl font-bold", color)}>{value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs + search */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {FILTER_TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilterTab(key)}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                filterTab === key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-800"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search rules…"
            className="w-full border border-gray-200 rounded-lg pl-8 pr-3 py-1.5 text-sm outline-none focus:border-indigo-400"
          />
        </div>
        <span className="text-xs text-gray-400">{filtered.length} rules</span>
      </div>

      {/* Rules table */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading rules…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 border border-dashed border-gray-200 rounded-xl">
          No rules found
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Pattern / Phrase</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Head</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Flow</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Conf.</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Uses</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Enabled</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((rule) => {
                const isSystem = rule.scope === "system";
                return (
                  <tr
                    key={rule.id}
                    className={clsx(
                      "transition-colors",
                      !rule.is_enabled && "opacity-50",
                      "hover:bg-gray-50"
                    )}
                  >
                    {/* Type badge */}
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded-full text-xs font-medium",
                          RULE_TYPE_COLORS[rule.rule_type] || "bg-gray-100 text-gray-700"
                        )}
                      >
                        {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
                      </span>
                    </td>

                    {/* Pattern / Phrase */}
                    <td className="px-4 py-3 max-w-xs">
                      <p
                        className={clsx(
                          "truncate font-mono text-xs",
                          rule.rule_type === "regex_keyword" ? "text-orange-700" : "text-gray-800"
                        )}
                        title={displayPhrase(rule)}
                      >
                        {displayPhrase(rule)}
                      </p>
                    </td>

                    {/* Head */}
                    <td className="px-4 py-3 text-gray-700 text-xs">{rule.head}</td>

                    {/* Flow */}
                    <td className="px-4 py-3 text-center">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded-full text-xs font-medium",
                          rule.type === "inflow"
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        )}
                      >
                        {rule.type}
                      </span>
                    </td>

                    {/* Confidence */}
                    <td className="px-4 py-3 text-center">
                      <span
                        className={clsx(
                          "text-xs font-semibold",
                          rule.confidence >= 0.9
                            ? "text-green-600"
                            : rule.confidence >= 0.8
                            ? "text-indigo-600"
                            : "text-amber-600"
                        )}
                      >
                        {(rule.confidence * 100).toFixed(0)}%
                      </span>
                    </td>

                    {/* Uses */}
                    <td className="px-4 py-3 text-center text-xs text-gray-500">
                      {rule.use_count}
                    </td>

                    {/* Enabled toggle */}
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleToggle(rule)}
                        disabled={togglingId === rule.id}
                        className="text-gray-400 hover:text-indigo-600 disabled:opacity-50"
                        title={rule.is_enabled ? "Disable rule" : "Enable rule"}
                      >
                        {rule.is_enabled ? (
                          <ToggleRight size={20} className="text-indigo-500" />
                        ) : (
                          <ToggleLeft size={20} />
                        )}
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3 text-center">
                      {isSystem ? (
                        <Lock
                          size={14}
                          className="mx-auto text-gray-300"
                        />
                      ) : (
                        <button
                          onClick={() => handleDelete(rule)}
                          disabled={deletingId === rule.id}
                          className="mx-auto text-gray-300 hover:text-red-500 disabled:opacity-50 transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
