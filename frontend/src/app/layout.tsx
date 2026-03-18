import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";

export const metadata: Metadata = {
  title: "CashFlow Evaluator",
  description: "AI-powered cashflow analysis for Indian SMEs",
};

/**
 * Root layout — wraps ALL pages (auth + app) with AuthProvider.
 * No Sidebar here; the (app) route group layout adds it for authenticated pages.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
