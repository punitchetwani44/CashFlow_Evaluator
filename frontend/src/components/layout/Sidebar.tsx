"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  Table2,
  Sparkles,
  TrendingUp,
  ListFilter,
  LogOut,
  ShieldCheck,
  Users,
  Building2,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import BusinessSwitcher from "./BusinessSwitcher";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload Statement", icon: Upload },
  { href: "/transactions", label: "Transactions", icon: Table2 },
  { href: "/rules", label: "Rules", icon: ListFilter },
  { href: "/insights", label: "AI Insights", icon: Sparkles },
];

const ADMIN_ITEMS = [
  { href: "/admin/users", label: "Manage Users", icon: Users },
  { href: "/admin/companies", label: "Manage Companies", icon: Building2 },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  company_admin: "Admin",
  manager: "Manager",
  end_user: "User",
};

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-red-900/60 text-red-300",
  company_admin: "bg-indigo-900/60 text-indigo-300",
  manager: "bg-emerald-900/60 text-emerald-300",
  end_user: "bg-slate-700 text-slate-400",
};

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const role = user?.role ?? "end_user";
  const showAdmin = role === "super_admin";
  const showSwitcher =
    role === "company_admin" || role === "manager" || role === "super_admin";

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-slate-900 text-white flex flex-col z-10">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <TrendingUp className="text-indigo-400" size={22} />
          <div>
            <div className="font-bold text-base leading-tight">CashFlow</div>
            <div className="text-xs text-slate-400 leading-tight">Evaluator</div>
          </div>
        </div>
      </div>

      {/* Business Switcher (company_admin + manager + super_admin) */}
      {showSwitcher && (
        <div className="pt-3">
          <BusinessSwitcher />
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? "bg-indigo-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}

        {/* Admin section — super_admin only */}
        {showAdmin && (
          <>
            <div className="pt-4 pb-1 px-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <ShieldCheck size={12} />
                Admin
              </span>
            </div>
            {ADMIN_ITEMS.map(({ href, label, icon: Icon }) => {
              const active =
                pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    active
                      ? "bg-indigo-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  <Icon size={18} />
                  {label}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* User info + logout */}
      <div className="px-4 py-4 border-t border-slate-700 space-y-3">
        {user ? (
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-200 truncate">
              {user.full_name}
            </p>
            <p className="text-xs text-slate-500 truncate">{user.email}</p>
            <span
              className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                ROLE_COLORS[role] ?? "bg-slate-700 text-slate-400"
              }`}
            >
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
        ) : (
          <p className="text-xs text-slate-500">Loading…</p>
        )}

        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg px-3 py-2 text-sm transition-colors"
        >
          <LogOut size={15} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
