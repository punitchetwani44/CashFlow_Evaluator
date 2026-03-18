/**
 * Auth token storage utilities.
 *
 * Access token lives in React state (via AuthContext) — never in localStorage.
 * Refresh token lives in an HttpOnly cookie set by the backend.
 *
 * We write the access_token to a readable cookie so the Next.js Edge Middleware
 * can check it for route protection without needing a backend round-trip.
 * We also keep a sessionStorage hint so AuthContext knows to attempt /refresh
 * on a page reload.
 */

const SESSION_STORAGE_KEY = "cf_session_hint";
const COOKIE_NAME = "access_token";
const COOKIE_MAX_AGE = 1800; // 30 min — matches JWT TTL

/** Write the access token to sessionStorage AND the Edge-readable cookie. */
export function setSessionHint(token: string): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, token);
  } catch {
    // sessionStorage unavailable (private mode etc.)
  }
  try {
    document.cookie = `${COOKIE_NAME}=${token}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
  } catch {
    // ignore DOM exceptions
  }
}

/** Clear session hint from sessionStorage and remove the cookie. */
export function clearSessionHint(): void {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // ignore
  }
  try {
    document.cookie = `${COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
  } catch {
    // ignore
  }
}

/** Check if there might be an active session (hint present). */
export function hasSessionHint(): boolean {
  try {
    return !!sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return false;
  }
}

/** Decode a JWT payload without verification (browser only). */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

/** Return true if the token is expired (or within 60s of expiry). */
export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") return true;
  return payload.exp * 1000 < Date.now() + 60_000;
}
