"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Mail, ArrowLeft } from "lucide-react";
import { forgotPassword, resetPassword } from "@/lib/api";
import axios from "axios";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [otpSessionToken, setOtpSessionToken] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await forgotPassword(email);
      if (res.data.otp_session_token) {
        setOtpSessionToken(res.data.otp_session_token);
        setStep("reset");
      } else {
        // Email not found — show generic message anyway
        setStep("reset");
        setOtpSessionToken("dummy");
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status !== 429) {
        setStep("reset");   // Always show reset form (don't reveal email existence)
      } else if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Please wait before requesting again");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(otpSessionToken, otpCode, newPassword);
      setSuccess(true);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Failed to reset password");
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
        <div className="w-full max-w-md bg-slate-800 rounded-2xl p-8 border border-slate-700 text-center">
          <div className="w-14 h-14 bg-green-900/50 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-green-400 text-2xl">✓</span>
          </div>
          <h2 className="text-white text-xl font-semibold mb-2">Password reset!</h2>
          <p className="text-slate-400 text-sm mb-6">
            Your password has been updated. Please sign in with your new password.
          </p>
          <button
            onClick={() => router.push("/login")}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 px-6 rounded-lg text-sm transition-colors"
          >
            Go to sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <TrendingUp className="text-indigo-400" size={32} />
          <div>
            <div className="text-white font-bold text-2xl">CashFlow</div>
            <div className="text-slate-400 text-sm">Evaluator</div>
          </div>
        </div>

        <div className="bg-slate-800 rounded-2xl p-8 shadow-2xl border border-slate-700">
          {step === "email" ? (
            <>
              <h1 className="text-white text-xl font-semibold mb-1">Reset password</h1>
              <p className="text-slate-400 text-sm mb-6">
                Enter your email and we&apos;ll send a reset code.
              </p>
              <form onSubmit={handleEmailSubmit} className="space-y-4">
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
                      className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 pl-9 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>
                {error && (
                  <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-2.5 text-red-300 text-sm">
                    {error}
                  </div>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
                >
                  {loading ? "Sending…" : "Send reset code"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-white text-xl font-semibold mb-1">Enter new password</h1>
              <p className="text-slate-400 text-sm mb-6">
                Check your email for a 6-digit reset code.
              </p>
              <form onSubmit={handleResetSubmit} className="space-y-4">
                <div>
                  <label className="block text-slate-300 text-sm font-medium mb-1.5">Reset code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                    required
                    placeholder="123456"
                    className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 tracking-widest"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 text-sm font-medium mb-1.5">New password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    placeholder="••••••••"
                    className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 text-sm font-medium mb-1.5">Confirm password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                {error && (
                  <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-2.5 text-red-300 text-sm">
                    {error}
                  </div>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
                >
                  {loading ? "Resetting…" : "Reset password"}
                </button>
              </form>
            </>
          )}

          <div className="mt-4 text-center">
            <a
              href="/login"
              className="flex items-center gap-1 text-slate-500 hover:text-slate-400 text-xs mx-auto justify-center transition-colors"
            >
              <ArrowLeft size={12} /> Back to sign in
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
