"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Mail, Lock, Eye, EyeOff } from "lucide-react";
import { loginUser } from "@/lib/api";
import axios from "axios";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await loginUser(email, password);
      const { otp_session_token } = res.data;
      // Store OTP session token temporarily in sessionStorage
      sessionStorage.setItem("otp_session_token", otp_session_token);
      sessionStorage.setItem("otp_email", email);
      router.push("/verify-otp");
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        if (!err.response) {
          setError("Cannot reach the server. Make sure the backend is running.");
        } else {
          const detail = err.response.data?.detail;
          setError(typeof detail === "string" ? detail : "Invalid email or password");
        }
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <TrendingUp className="text-indigo-400" size={32} />
          <div>
            <div className="text-white font-bold text-2xl leading-tight">CashFlow</div>
            <div className="text-slate-400 text-sm leading-tight">Evaluator</div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-slate-800 rounded-2xl p-8 shadow-2xl border border-slate-700">
          <h1 className="text-white text-xl font-semibold mb-1">Sign in</h1>
          <p className="text-slate-400 text-sm mb-6">
            Enter your credentials to continue
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-slate-300 text-sm font-medium mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@company.com"
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 pl-9 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-slate-300 text-sm font-medium mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 pl-9 pr-10 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-2.5 text-red-300 text-sm">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors mt-2"
            >
              {loading ? "Sending OTP…" : "Continue →"}
            </button>
          </form>

          <div className="mt-4 text-center">
            <a
              href="/forgot-password"
              className="text-slate-400 hover:text-slate-300 text-xs transition-colors"
            >
              Forgot your password?
            </a>
          </div>
        </div>

        <p className="text-slate-600 text-xs text-center mt-6">
          Indian SME Cashflow Analysis · Powered by GPT-4o-mini
        </p>
      </div>
    </div>
  );
}
