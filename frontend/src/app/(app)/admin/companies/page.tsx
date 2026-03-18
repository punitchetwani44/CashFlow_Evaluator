"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Building2,
  Plus,
  Search,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Users,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  listCompanies,
  createCompany,
  inactivateCompany,
  reactivateCompany,
  getCompanyBusinessAccounts,
  createBusinessAccount,
} from "@/lib/api";

interface Company {
  id: number;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  created_at: string;
}

interface BA {
  id: number;
  name: string;
  is_active: boolean;
}

export default function AdminCompaniesPage() {
  const { user: currentUser } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [baMap, setBaMap] = useState<Record<number, BA[]>>({});
  const [showAddBA, setShowAddBA] = useState<number | null>(null);
  const [newBAName, setNewBAName] = useState("");

  // Create company form
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const fetchCompanies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listCompanies();
      setCompanies(res.data);
    } catch {
      setError("Failed to load companies");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      await createCompany({ name: newName });
      setNewName("");
      setShowCreate(false);
      fetchCompanies();
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } } };
      setCreateError(axErr.response?.data?.detail || "Failed to create company");
    } finally {
      setCreating(false);
    }
  };

  const toggleExpand = async (companyId: number) => {
    if (expanded === companyId) {
      setExpanded(null);
      return;
    }
    setExpanded(companyId);
    if (!baMap[companyId]) {
      try {
        const res = await getCompanyBusinessAccounts(companyId);
        setBaMap((prev) => ({ ...prev, [companyId]: res.data }));
      } catch {
        setBaMap((prev) => ({ ...prev, [companyId]: [] }));
      }
    }
  };

  const handleAddBA = async (companyId: number) => {
    if (!newBAName.trim()) return;
    try {
      await createBusinessAccount(companyId, { name: newBAName });
      setNewBAName("");
      setShowAddBA(null);
      const res = await getCompanyBusinessAccounts(companyId);
      setBaMap((prev) => ({ ...prev, [companyId]: res.data }));
    } catch {
      alert("Failed to add business account");
    }
  };

  const filtered = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.slug.toLowerCase().includes(search.toLowerCase())
  );

  if (currentUser?.role !== "super_admin") {
    return (
      <div className="p-8 text-center text-gray-500">
        Super admin access required.
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Building2 className="text-indigo-600" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
            <p className="text-sm text-gray-500">{companies.length} total companies</p>
          </div>
        </div>
        <button
          onClick={() => setShowCreate((s) => !s)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {showCreate ? <ChevronUp size={16} /> : <Plus size={16} />}
          {showCreate ? "Cancel" : "New Company"}
        </button>
      </div>

      {/* Create company form */}
      {showCreate && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Create New Company</h2>
          <form onSubmit={handleCreate} className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Company Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                placeholder="Acme Corp"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button
              type="submit"
              disabled={creating}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {creating ? "Creating…" : "Create"}
            </button>
          </form>
          {createError && (
            <p className="mt-2 text-sm text-red-600">{createError}</p>
          )}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies…"
          className="w-full border border-gray-300 rounded-lg pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Companies list */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading…</div>
      ) : error ? (
        <div className="text-center py-16 text-red-500">{error}</div>
      ) : (
        <div className="space-y-3">
          {filtered.length === 0 && (
            <div className="text-center py-12 text-gray-400">No companies found</div>
          )}
          {filtered.map((co) => (
            <div
              key={co.id}
              className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden"
            >
              {/* Company row */}
              <div className="flex items-center gap-4 px-5 py-4">
                <div className="w-9 h-9 bg-indigo-100 rounded-lg flex items-center justify-center text-indigo-700 font-bold text-sm">
                  {co.name[0]?.toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-800 truncate">{co.name}</p>
                  <p className="text-xs text-gray-400">
                    /{co.slug} · {co.plan} plan
                  </p>
                </div>
                <span
                  className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                    co.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-600"
                  }`}
                >
                  {co.is_active ? (
                    <CheckCircle size={11} />
                  ) : (
                    <XCircle size={11} />
                  )}
                  {co.is_active ? "Active" : "Inactive"}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      co.is_active
                        ? (confirm("Inactivate this company? All user sessions will be revoked.") &&
                            inactivateCompany(co.id).then(fetchCompanies))
                        : reactivateCompany(co.id).then(fetchCompanies)
                    }
                    className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                      co.is_active
                        ? "border-red-200 text-red-600 hover:bg-red-50"
                        : "border-green-200 text-green-700 hover:bg-green-50"
                    }`}
                  >
                    {co.is_active ? "Inactivate" : "Reactivate"}
                  </button>
                  <button
                    onClick={() => toggleExpand(co.id)}
                    className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 px-3 py-1.5 rounded-lg hover:bg-indigo-50 border border-indigo-200 transition-colors"
                  >
                    <Users size={12} />
                    BAs
                    {expanded === co.id ? (
                      <ChevronUp size={12} />
                    ) : (
                      <ChevronDown size={12} />
                    )}
                  </button>
                </div>
              </div>

              {/* Business accounts panel */}
              {expanded === co.id && (
                <div className="border-t border-gray-100 bg-gray-50 px-5 py-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Business Accounts
                    </h3>
                    <button
                      onClick={() =>
                        setShowAddBA(showAddBA === co.id ? null : co.id)
                      }
                      className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                    >
                      <Plus size={12} /> Add
                    </button>
                  </div>

                  {showAddBA === co.id && (
                    <div className="flex gap-2 mb-3">
                      <input
                        type="text"
                        value={newBAName}
                        onChange={(e) => setNewBAName(e.target.value)}
                        placeholder="Account name"
                        className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <button
                        onClick={() => handleAddBA(co.id)}
                        className="bg-indigo-600 text-white text-sm px-4 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors"
                      >
                        Add
                      </button>
                    </div>
                  )}

                  {!baMap[co.id] ? (
                    <p className="text-xs text-gray-400">Loading…</p>
                  ) : baMap[co.id].length === 0 ? (
                    <p className="text-xs text-gray-400">No business accounts yet</p>
                  ) : (
                    <div className="space-y-1.5">
                      {baMap[co.id].map((ba) => (
                        <div
                          key={ba.id}
                          className="flex items-center justify-between bg-white rounded-lg px-4 py-2.5 border border-gray-200 text-sm"
                        >
                          <span className="font-medium text-gray-700">{ba.name}</span>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              ba.is_active
                                ? "bg-green-100 text-green-700"
                                : "bg-red-100 text-red-600"
                            }`}
                          >
                            {ba.is_active ? "Active" : "Inactive"}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
