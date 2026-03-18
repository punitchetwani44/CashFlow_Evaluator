"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Users,
  Plus,
  Search,
  UserX,
  UserCheck,
  ChevronDown,
  ChevronUp,
  Mail,
  Shield,
  Building2,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  listUsers,
  createUser,
  inactivateUser,
  reactivateUser,
  listCompanies,
  getCompanyBusinessAccounts,
} from "@/lib/api";

interface UserRow {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  company_id: number;
  created_at: string;
}

interface CompanyOption {
  id: number;
  name: string;
  is_active: boolean;
}

interface BAOption {
  id: number;
  name: string;
  is_active: boolean;
}

const ROLE_OPTIONS = ["company_admin", "manager", "end_user"] as const;

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  company_admin: "Admin",
  manager: "Manager",
  end_user: "User",
};

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-red-100 text-red-700",
  company_admin: "bg-indigo-100 text-indigo-700",
  manager: "bg-emerald-100 text-emerald-700",
  end_user: "bg-gray-100 text-gray-600",
};

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  // Create form state
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<string>("end_user");
  const [newCompanyId, setNewCompanyId] = useState<number | "">("");
  const [newBAIds, setNewBAIds] = useState<number[]>([]);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  // Company + BA options for the form
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [availableBAs, setAvailableBAs] = useState<BAOption[]>([]);
  const [loadingBAs, setLoadingBAs] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listUsers();
      setUsers(res.data);
    } catch {
      setError("Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load companies for the dropdown (super_admin only)
  useEffect(() => {
    if (currentUser?.role === "super_admin") {
      listCompanies()
        .then((res) => setCompanies(res.data.filter((c: CompanyOption) => c.is_active)))
        .catch(() => setCompanies([]));
    }
  }, [currentUser?.role]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // When company selection changes, load its BAs (for super_admin who picks a company)
  useEffect(() => {
    if (!newCompanyId) {
      // For company_admin: don't clear BAs (loaded separately below)
      if (currentUser?.role !== "company_admin") {
        setAvailableBAs([]);
        setNewBAIds([]);
      }
      return;
    }
    setLoadingBAs(true);
    setNewBAIds([]);
    getCompanyBusinessAccounts(Number(newCompanyId))
      .then((res) => setAvailableBAs(res.data.filter((b: BAOption) => b.is_active)))
      .catch(() => setAvailableBAs([]))
      .finally(() => setLoadingBAs(false));
  }, [newCompanyId, currentUser?.role]);

  // For company_admin: load their own company's BAs when the create form opens
  useEffect(() => {
    if (currentUser?.role === "company_admin" && showCreate && currentUser.company_id) {
      setLoadingBAs(true);
      setNewBAIds([]);
      getCompanyBusinessAccounts(currentUser.company_id)
        .then((res) => setAvailableBAs(res.data.filter((b: BAOption) => b.is_active)))
        .catch(() => setAvailableBAs([]))
        .finally(() => setLoadingBAs(false));
    } else if (!showCreate) {
      setAvailableBAs([]);
      setNewBAIds([]);
    }
  }, [showCreate, currentUser?.role, currentUser?.company_id]);

  const toggleBA = (id: number) => {
    setNewBAIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const resetForm = () => {
    setNewEmail("");
    setNewName("");
    setNewPassword("");
    setNewRole("end_user");
    setNewCompanyId("");
    setNewBAIds([]);
    setAvailableBAs([]);
    setCreateError("");
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      await createUser({
        email: newEmail,
        full_name: newName,
        password: newPassword,
        role: newRole,
        company_id: newCompanyId ? Number(newCompanyId) : undefined,
        business_account_ids: newBAIds,
      });
      resetForm();
      setShowCreate(false);
      fetchUsers();
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } } };
      setCreateError(axErr.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handleInactivate = async (id: number) => {
    if (!confirm("Inactivate this user? Their sessions will be revoked.")) return;
    try {
      await inactivateUser(id);
      fetchUsers();
    } catch {
      alert("Failed to inactivate user");
    }
  };

  const handleReactivate = async (id: number) => {
    try {
      await reactivateUser(id);
      fetchUsers();
    } catch {
      alert("Failed to reactivate user");
    }
  };

  const filtered = users.filter(
    (u) =>
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.full_name.toLowerCase().includes(search.toLowerCase())
  );

  if (currentUser?.role !== "super_admin" && currentUser?.role !== "company_admin") {
    return (
      <div className="p-8 text-center text-gray-500">
        You don&apos;t have permission to view this page.
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users className="text-indigo-600" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Users</h1>
            <p className="text-sm text-gray-500">{users.length} total users</p>
          </div>
        </div>
        <button
          onClick={() => {
            setShowCreate((s) => !s);
            if (showCreate) resetForm();
          }}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {showCreate ? <ChevronUp size={16} /> : <Plus size={16} />}
          {showCreate ? "Cancel" : "New User"}
        </button>
      </div>

      {/* ── Create user form ── */}
      {showCreate && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Create New User</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">

            {/* Full Name */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Full Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                placeholder="Jane Smith"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
                placeholder="jane@company.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                placeholder="Min 8 characters"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Role */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
                {currentUser?.role === "super_admin" && (
                  <option value="super_admin">Super Admin</option>
                )}
              </select>
            </div>

            {/* Company (super_admin only) */}
            {currentUser?.role === "super_admin" && (
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1 flex items-center gap-1">
                  <Building2 size={12} />
                  Company
                </label>
                <select
                  value={newCompanyId}
                  onChange={(e) =>
                    setNewCompanyId(e.target.value ? Number(e.target.value) : "")
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                >
                  <option value="">— Use my company (Default Company) —</option>
                  {companies.map((co) => (
                    <option key={co.id} value={co.id}>{co.name}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Business Accounts (shown after company is selected) */}
            {(newCompanyId || currentUser?.role === "company_admin") && (
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-2">
                  Business Account Access{" "}
                  <span className="text-gray-400 font-normal">(select at least one so the user can log in)</span>
                </label>
                {loadingBAs ? (
                  <p className="text-xs text-gray-400">Loading accounts…</p>
                ) : availableBAs.length === 0 ? (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    No active business accounts found for this company. Create one first via Manage Companies.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {availableBAs.map((ba) => (
                      <label
                        key={ba.id}
                        className={`flex items-center gap-2 border rounded-lg px-3 py-2 cursor-pointer text-sm transition-colors ${
                          newBAIds.includes(ba.id)
                            ? "border-indigo-400 bg-indigo-50 text-indigo-800"
                            : "border-gray-200 hover:border-indigo-300 text-gray-700"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={newBAIds.includes(ba.id)}
                          onChange={() => toggleBA(ba.id)}
                          className="accent-indigo-600"
                        />
                        <span className="truncate">{ba.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Error */}
            {createError && (
              <div className="col-span-2 bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-red-600 text-sm">
                {createError}
              </div>
            )}

            {/* Submit */}
            <div className="col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={creating}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {creating ? "Creating…" : "Create User"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or email…"
          className="w-full border border-gray-300 rounded-lg pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading…</div>
      ) : error ? (
        <div className="text-center py-16 text-red-500">{error}</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Joined</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-gray-400">No users found</td>
                </tr>
              )}
              {filtered.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 font-semibold text-xs">
                        {u.full_name?.[0]?.toUpperCase() ?? "?"}
                      </div>
                      <div>
                        <p className="font-medium text-gray-800">{u.full_name}</p>
                        <p className="text-xs text-gray-400 flex items-center gap-1">
                          <Mail size={10} />
                          {u.email}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLORS[u.role] ?? "bg-gray-100 text-gray-600"}`}>
                      {u.role === "super_admin" && <Shield size={10} />}
                      {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== currentUser?.id && u.role !== "super_admin" && (
                      <button
                        onClick={() => u.is_active ? handleInactivate(u.id) : handleReactivate(u.id)}
                        className={`inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                          u.is_active
                            ? "border-red-200 text-red-600 hover:bg-red-50"
                            : "border-green-200 text-green-700 hover:bg-green-50"
                        }`}
                      >
                        {u.is_active ? <><UserX size={12} /> Inactivate</> : <><UserCheck size={12} /> Reactivate</>}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
