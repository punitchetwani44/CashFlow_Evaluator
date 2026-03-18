"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, Building2, Check, Users } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { getMyBusinessAccounts, listCompanies } from "@/lib/api";
import type { BusinessAccount, Company } from "@/lib/api";

/**
 * Business Account switcher dropdown.
 *
 * - super_admin: two-tier selector (Tenant → Business).
 *   Tenant list comes from listCompanies(); BA list is filtered client-side
 *   from the single getMyBusinessAccounts() call (which returns ALL BAs for
 *   super_admin, each with company_id). No per-tenant API call needed.
 *
 * - company_admin / manager: single BA dropdown (same as before), but
 *   window.location.reload() is replaced with router.refresh() to avoid
 *   the double-refresh logout bug caused by Strict Mode.
 */
export default function BusinessSwitcher() {
  const router = useRouter();
  const { user, activeBusinessId, switchBusiness } = useAuth();

  const [accounts, setAccounts] = useState<BusinessAccount[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);

  // Separate open states for the two super_admin dropdowns
  const [tenantOpen, setTenantOpen] = useState(false);
  const [baOpen, setBaOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  const tenantRef = useRef<HTMLDivElement>(null);
  const baRef = useRef<HTMLDivElement>(null);

  const isSuperAdmin = user?.role === "super_admin";

  // ── Fetch data on mount (or when user / active business changes) ────────────
  useEffect(() => {
    if (!user) return;

    getMyBusinessAccounts()
      .then((res) => {
        const bas = res.data;
        setAccounts(bas);

        // For super_admin: auto-detect the current tenant from activeBusinessId
        if (isSuperAdmin && activeBusinessId) {
          const currentBA = bas.find((b) => b.id === activeBusinessId);
          if (currentBA) setSelectedTenantId(currentBA.company_id);
        }
      })
      .catch(() => setAccounts([]));

    if (isSuperAdmin) {
      listCompanies()
        .then((res) => setCompanies(res.data))
        .catch(() => setCompanies([]));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, activeBusinessId]);

  // ── Close dropdowns on outside click ───────────────────────────────────────
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (tenantRef.current && !tenantRef.current.contains(e.target as Node)) {
        setTenantOpen(false);
      }
      if (baRef.current && !baRef.current.contains(e.target as Node)) {
        setBaOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // ── Switch handler ──────────────────────────────────────────────────────────
  const handleSwitch = async (id: number) => {
    if (id === activeBusinessId || switching) return;
    setSwitching(true);
    setBaOpen(false);
    setTenantOpen(false);
    try {
      await switchBusiness(id);
      // router.refresh() re-validates Next.js router cache for server components.
      // Client components refetch via the activeBusinessId change in AuthContext.
      router.refresh();
    } catch {
      // AuthContext surfaces errors; ignore here
    } finally {
      setSwitching(false);
    }
  };

  // ── Derived display values ──────────────────────────────────────────────────
  const activeName =
    accounts.find((a) => a.id === activeBusinessId)?.name ?? "Select account";

  const selectedTenantName =
    companies.find((c) => c.id === selectedTenantId)?.name ?? "Select tenant";

  // BAs shown in the BA dropdown: filtered by selected tenant for super_admin
  const visibleBAs = isSuperAdmin && selectedTenantId !== null
    ? accounts.filter((b) => b.company_id === selectedTenantId)
    : accounts;

  // Hide if there is nothing to switch to
  if (!isSuperAdmin && accounts.length <= 1) return null;

  // ── Super-admin: two-tier UI ────────────────────────────────────────────────
  if (isSuperAdmin) {
    return (
      <div className="px-3 mb-2 space-y-1.5">
        {/* Tenant selector */}
        <div ref={tenantRef} className="relative">
          <button
            onClick={() => { setTenantOpen((o) => !o); setBaOpen(false); }}
            disabled={switching}
            className="w-full flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-60 rounded-lg px-3 py-2 text-xs text-slate-300 transition-colors"
          >
            <Users size={12} className="text-slate-400 shrink-0" />
            <span className="flex-1 text-left truncate">{selectedTenantName}</span>
            <ChevronDown
              size={12}
              className={`text-slate-400 transition-transform ${tenantOpen ? "rotate-180" : ""}`}
            />
          </button>

          {tenantOpen && (
            <div className="absolute left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 overflow-hidden max-h-52 overflow-y-auto">
              {companies.length === 0 && (
                <p className="px-3 py-2 text-xs text-slate-500">No tenants found</p>
              )}
              {companies.map((co) => (
                <button
                  key={co.id}
                  onClick={() => {
                    setSelectedTenantId(co.id);
                    setTenantOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors
                    ${co.id === selectedTenantId
                      ? "bg-indigo-600/40 text-indigo-200"
                      : "text-slate-300 hover:bg-slate-700"
                    }`}
                >
                  {co.id === selectedTenantId && (
                    <Check size={10} className="text-indigo-400 shrink-0" />
                  )}
                  {co.id !== selectedTenantId && <span className="w-2.5" />}
                  <span className="truncate">{co.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Business Account selector */}
        <div ref={baRef} className="relative">
          <button
            onClick={() => { setBaOpen((o) => !o); setTenantOpen(false); }}
            disabled={switching || selectedTenantId === null}
            className="w-full flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-60 rounded-lg px-3 py-2 text-sm text-slate-200 transition-colors"
          >
            <Building2 size={14} className="text-slate-400 shrink-0" />
            <span className="flex-1 text-left truncate">
              {switching ? "Switching…" : activeName}
            </span>
            <ChevronDown
              size={14}
              className={`text-slate-400 transition-transform ${baOpen ? "rotate-180" : ""}`}
            />
          </button>

          {baOpen && (
            <div className="absolute left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 overflow-hidden max-h-52 overflow-y-auto">
              {visibleBAs.length === 0 && (
                <p className="px-3 py-2 text-sm text-slate-500">
                  {selectedTenantId === null ? "Select a tenant first" : "No accounts for this tenant"}
                </p>
              )}
              {visibleBAs.map((acct) => (
                <button
                  key={acct.id}
                  onClick={() => handleSwitch(acct.id)}
                  disabled={!acct.is_active}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors
                    ${acct.id === activeBusinessId
                      ? "bg-indigo-600/40 text-indigo-200"
                      : "text-slate-300 hover:bg-slate-700"
                    }
                    ${!acct.is_active ? "opacity-40 cursor-not-allowed" : ""}
                  `}
                >
                  {acct.id === activeBusinessId && (
                    <Check size={12} className="text-indigo-400 shrink-0" />
                  )}
                  {acct.id !== activeBusinessId && <span className="w-3" />}
                  <span className="truncate">{acct.name}</span>
                  {!acct.is_active && (
                    <span className="ml-auto text-xs text-slate-500">Inactive</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── company_admin / manager: single dropdown (no reload) ───────────────────
  return (
    <div ref={baRef} className="relative px-3 mb-2">
      <button
        onClick={() => setBaOpen((o) => !o)}
        disabled={switching}
        className="w-full flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-60 rounded-lg px-3 py-2 text-sm text-slate-200 transition-colors"
      >
        <Building2 size={14} className="text-slate-400 shrink-0" />
        <span className="flex-1 text-left truncate">
          {switching ? "Switching…" : activeName}
        </span>
        <ChevronDown
          size={14}
          className={`text-slate-400 transition-transform ${baOpen ? "rotate-180" : ""}`}
        />
      </button>

      {baOpen && (
        <div className="absolute left-3 right-3 top-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 overflow-hidden">
          {accounts.map((acct) => (
            <button
              key={acct.id}
              onClick={() => handleSwitch(acct.id)}
              disabled={!acct.is_active}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors
                ${acct.id === activeBusinessId
                  ? "bg-indigo-600/40 text-indigo-200"
                  : "text-slate-300 hover:bg-slate-700"
                }
                ${!acct.is_active ? "opacity-40 cursor-not-allowed" : ""}
              `}
            >
              {acct.id === activeBusinessId && (
                <Check size={12} className="text-indigo-400 shrink-0" />
              )}
              {acct.id !== activeBusinessId && <span className="w-3" />}
              <span className="truncate">{acct.name}</span>
              {!acct.is_active && (
                <span className="ml-auto text-xs text-slate-500">Inactive</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
