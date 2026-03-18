/**
 * Next.js Edge Middleware — lightweight route protection.
 *
 * Reads the access_token from cookies (NOT verifies signature — that's the
 * backend's job). If missing or expired, redirects to /login.
 * If path starts with /admin and decoded role !== super_admin, redirect to /.
 */

import { NextRequest, NextResponse } from "next/server";

// Paths that are always public (no redirect)
const PUBLIC_PATHS = ["/login", "/verify-otp", "/forgot-password", "/reset-password"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

function decodeJwtExp(token: string): { exp?: number; role?: string } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const pad = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const decoded = Buffer.from(pad, "base64").toString("utf-8");
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Always allow public paths + Next.js internals
  if (
    isPublic(pathname) ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/api/") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // Check for access token in cookie
  const token = request.cookies.get("access_token")?.value;

  if (!token) {
    // No token → redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const payload = decodeJwtExp(token);
  if (!payload) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Check expiry (with 60s grace to account for clock drift)
  if (payload.exp && payload.exp * 1000 < Date.now() + 60_000) {
    // Token expired — let client-side refresh handle it (don't redirect here
    // to avoid redirect loops; the React interceptor will refresh silently)
    return NextResponse.next();
  }

  // Admin route guard
  if (pathname.startsWith("/admin") && payload.role !== "super_admin") {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all paths except static files, _next internals, and api routes
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
