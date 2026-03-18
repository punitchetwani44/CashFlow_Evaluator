"use client";

import { useAuth } from "@/contexts/AuthContext";
import { AlertTriangle } from "lucide-react";

/**
 * Shows an orange banner when a super_admin is shadow-logged into another user's account.
 * Rendered inside the (app) layout, above the main content.
 */
export default function ImpersonationBanner() {
  const { isShadow, user } = useAuth();

  if (!isShadow) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-orange-500 text-white px-4 py-2 flex items-center justify-center gap-2 text-sm font-medium shadow-lg">
      <AlertTriangle size={16} className="shrink-0" />
      <span>
        You are viewing as{" "}
        <strong>{user?.full_name || user?.email || "another user"}</strong> —
        shadow session active
      </span>
    </div>
  );
}
