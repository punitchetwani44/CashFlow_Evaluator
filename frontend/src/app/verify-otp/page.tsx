"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, RefreshCw } from "lucide-react";
import { resendOTP } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import axios from "axios";

export default function VerifyOTPPage() {
  const router = useRouter();
  const auth = useAuth();
  const [otpSessionToken, setOtpSessionToken] = useState("");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState("");
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    const token = sessionStorage.getItem("otp_session_token") || "";
    const storedEmail = sessionStorage.getItem("otp_email") || "";
    if (!token) {
      router.push("/login");
      return;
    }
    setOtpSessionToken(token);
    setEmail(storedEmail);
    setCooldown(60);
  }, [router]);

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const handleOTPChange = (idx: number, val: string) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[idx] = val;
    setOtp(next);
    if (val && idx < 5) inputRefs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[idx] && idx > 0) {
      inputRefs.current[idx - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    const next = [...otp];
    pasted.split("").forEach((ch, i) => { next[i] = ch; });
    setOtp(next);
    inputRefs.current[Math.min(pasted.length, 5)]?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length !== 6) {
      setError("Please enter the 6-digit OTP");
      return;
    }
    setError("");
    setLoading(true);
    try {
      // Use AuthContext.verifyOTP — this updates user state, token, and cookie
      await auth.verifyOTP(otpSessionToken, code);
      sessionStorage.removeItem("otp_session_token");
      sessionStorage.removeItem("otp_email");
      router.push("/");
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Invalid or expired OTP");
      } else {
        setError("Something went wrong");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      const res = await resendOTP(otpSessionToken);
      setOtpSessionToken(res.data.otp_session_token);
      sessionStorage.setItem("otp_session_token", res.data.otp_session_token);
      setCooldown(60);
      setOtp(["", "", "", "", "", ""]);
      setError("");
      inputRefs.current[0]?.focus();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Could not resend OTP");
      }
    } finally {
      setResending(false);
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

        <div className="bg-slate-800 rounded-2xl p-8 shadow-2xl border border-slate-700">
          <h1 className="text-white text-xl font-semibold mb-1">
            Verify your email
          </h1>
          <p className="text-slate-400 text-sm mb-6">
            We sent a 6-digit code to{" "}
            <span className="text-slate-200 font-medium">{email}</span>
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* OTP Boxes */}
            <div className="flex gap-2 justify-center" onPaste={handlePaste}>
              {otp.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => { inputRefs.current[idx] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOTPChange(idx, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(idx, e)}
                  className="w-12 h-12 text-center text-white text-xl font-bold bg-slate-700 border border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent caret-indigo-400"
                />
              ))}
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-2.5 text-red-300 text-sm text-center">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || otp.join("").length !== 6}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? "Verifying…" : "Verify & Sign in"}
            </button>
          </form>

          <div className="mt-5 text-center">
            {cooldown > 0 ? (
              <span className="text-slate-500 text-sm">
                Resend code in {cooldown}s
              </span>
            ) : (
              <button
                onClick={handleResend}
                disabled={resending}
                className="flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 text-sm mx-auto transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={resending ? "animate-spin" : ""} />
                {resending ? "Sending…" : "Resend code"}
              </button>
            )}
          </div>

          <div className="mt-4 text-center">
            <a
              href="/login"
              className="text-slate-500 hover:text-slate-400 text-xs transition-colors"
            >
              ← Back to sign in
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
