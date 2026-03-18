"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { setSessionHint, clearSessionHint, isTokenExpired } from "@/lib/auth";
import { setApiToken } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: "super_admin" | "company_admin" | "manager" | "end_user";
  is_active: boolean;
  company_id: number;
  created_at: string;
}

export interface BusinessAccountBrief {
  id: number;
  name: string;
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  activeBusinessId: number | null;
  isLoading: boolean;
  isShadow: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<string>;   // returns otp_session_token
  verifyOTP: (otpSessionToken: string, otpCode: string) => Promise<void>;
  logout: () => Promise<void>;
  switchBusiness: (businessAccountId: number) => Promise<void>;
  refreshToken: () => Promise<string | null>;
  setAccessToken: (token: string) => void;
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | null>(null);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    activeBusinessId: null,
    isLoading: true,
    isShadow: false,
  });

  // Ref so interceptors can always read the latest token
  const tokenRef = useRef<string | null>(null);

  const updateState = useCallback((patch: Partial<AuthState>) => {
    setState((prev) => ({ ...prev, ...patch }));
    if (patch.accessToken !== undefined) {
      tokenRef.current = patch.accessToken;
      // Keep api.ts interceptor in sync
      setApiToken(patch.accessToken);
    }
  }, []);

  // ── Refresh token ──────────────────────────────────────────────────────────

  const refreshToken = useCallback(async (): Promise<string | null> => {
    try {
      const res = await axios.post(
        `${API_BASE}/api/auth/refresh`,
        {},
        { withCredentials: true }
      );
      const { access_token, active_business_id } = res.data;
      tokenRef.current = access_token;
      setApiToken(access_token);
      setSessionHint(access_token);
      setState((prev) => ({
        ...prev,
        accessToken: access_token,
        activeBusinessId: active_business_id ?? prev.activeBusinessId,
      }));
      return access_token;
    } catch {
      return null;
    }
  }, []);

  // ── Auto-restore session on mount ─────────────────────────────────────────

  useEffect(() => {
    const restore = async () => {
      const token = await refreshToken();
      if (token) {
        try {
          const res = await axios.get(`${API_BASE}/api/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          updateState({
            user: res.data,
            accessToken: token,
            isLoading: false,
          });
        } catch {
          updateState({ isLoading: false });
        }
      } else {
        updateState({ isLoading: false });
      }
    };
    restore();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Login (Step 1) ────────────────────────────────────────────────────────

  const login = useCallback(
    async (email: string, password: string): Promise<string> => {
      const res = await axios.post(`${API_BASE}/api/auth/login`, {
        email,
        password,
      });
      return res.data.otp_session_token;
    },
    []
  );

  // ── Verify OTP (Step 2) ───────────────────────────────────────────────────

  const verifyOTP = useCallback(
    async (otpSessionToken: string, otpCode: string): Promise<void> => {
      const res = await axios.post(
        `${API_BASE}/api/auth/verify-otp`,
        { otp_session_token: otpSessionToken, otp_code: otpCode },
        { withCredentials: true }
      );
      const { access_token, user, active_business_id } = res.data;
      tokenRef.current = access_token;
      setSessionHint(access_token);
      updateState({
        user,
        accessToken: access_token,
        activeBusinessId: active_business_id,
        isLoading: false,
        isShadow: false,
      });
    },
    [updateState]
  );

  // ── Logout ─────────────────────────────────────────────────────────────────

  const logout = useCallback(async (): Promise<void> => {
    try {
      await axios.post(
        `${API_BASE}/api/auth/logout`,
        {},
        {
          headers: { Authorization: `Bearer ${tokenRef.current}` },
          withCredentials: true,
        }
      );
    } catch {
      // proceed even if the request fails
    }
    tokenRef.current = null;
    setApiToken(null);
    clearSessionHint();
    updateState({
      user: null,
      accessToken: null,
      activeBusinessId: null,
      isShadow: false,
    });
    router.push("/login");
  }, [updateState, router]);

  // ── Switch Business ────────────────────────────────────────────────────────

  const switchBusiness = useCallback(
    async (businessAccountId: number): Promise<void> => {
      const res = await axios.post(
        `${API_BASE}/api/auth/switch-business/${businessAccountId}`,
        {},
        {
          headers: { Authorization: `Bearer ${tokenRef.current}` },
          withCredentials: true,
        }
      );
      const { access_token, active_business_id } = res.data;
      tokenRef.current = access_token;
      setSessionHint(access_token);
      updateState({ accessToken: access_token, activeBusinessId: active_business_id });
    },
    [updateState]
  );

  const setAccessToken = useCallback(
    (token: string) => {
      tokenRef.current = token;
      updateState({ accessToken: token });
    },
    [updateState]
  );

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        verifyOTP,
        logout,
        switchBusiness,
        refreshToken,
        setAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
