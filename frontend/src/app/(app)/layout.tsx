"use client";

import Sidebar from "@/components/layout/Sidebar";
import ImpersonationBanner from "@/components/layout/ImpersonationBanner";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Layout for all authenticated app pages (dashboard, transactions, etc.).
 * Renders the Sidebar and the impersonation warning banner.
 * Redirects to /login if not authenticated.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [user, isLoading, router]);

  // Show nothing while auth resolves to prevent flash
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex min-h-screen">
      <ImpersonationBanner />
      <Sidebar />
      <main className="ml-60 flex-1 min-h-screen bg-gray-50">
        {children}
      </main>
    </div>
  );
}
