import axios, { AxiosError } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,   // send HttpOnly refresh_token cookie
});

// ─── Token store (module-level, set by AuthContext) ─────────────────────────

let _accessToken: string | null = null;
let _isRefreshing = false;
let _refreshQueue: Array<(token: string | null) => void> = [];

export function setApiToken(token: string | null): void {
  _accessToken = token;
}

// ─── Request interceptor: attach Bearer ─────────────────────────────────────

api.interceptors.request.use((config) => {
  if (_accessToken && config.headers) {
    config.headers["Authorization"] = `Bearer ${_accessToken}`;
  }
  return config;
});

// ─── Response interceptor: silent token refresh on 401 ───────────────────────

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as typeof error.config & { _retry?: boolean };
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      originalRequest.url !== "/api/auth/refresh"
    ) {
      if (_isRefreshing) {
        return new Promise((resolve, reject) => {
          _refreshQueue.push((token) => {
            if (!token) {
              reject(error);
              return;
            }
            if (originalRequest.headers) {
              originalRequest.headers["Authorization"] = `Bearer ${token}`;
            }
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        const res = await axios.post(
          `${API_URL}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );
        const newToken = res.data.access_token;
        _accessToken = newToken;
        if (originalRequest.headers) {
          originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
        }
        _refreshQueue.forEach((cb) => cb(newToken));
        _refreshQueue = [];
        return api(originalRequest);
      } catch (refreshError) {
        _accessToken = null;
        _refreshQueue.forEach((cb) => cb(null));
        _refreshQueue = [];
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      } finally {
        _isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// ─── Types ──────────────────────────────────────────────────────────────────

export interface Upload {
  id: number;
  filename: string;
  original_filename: string;
  file_type: string;
  status: string;
  error_message?: string;
  row_count: number;
  mapped_count: number;
  unmapped_count: number;
  created_at: string;
}

export interface Transaction {
  id: number;
  upload_id: number;
  date: string;
  description: string;
  amount: number;
  type: string;
  head: string | null;
  month: string | null;
  comments: string | null;
  status: string;
  is_user_modified: boolean;
  classification_confidence: number | null;
  raw_debit: number | null;
  raw_credit: number | null;
  raw_balance: number | null;
  created_at: string;
}

export interface MonthlyMetric {
  id: number;
  month: string;
  total_inflow: number;
  total_outflow: number;
  net_cashflow: number;
  indicator_cashflow: number;
  capital_infused: number;
  capital_withdrawn: number;
  fixed_cost_ratio: number;
  payroll_ratio: number;
  cash_runway: number | null;
  vendor_dependency: number | null;
  transaction_count: number;
  mapped_count: number;
  category_breakdown: string | null;
  updated_at: string;
}

export interface AIInsight {
  id: number;
  month: string;
  insights: string;
  generated_at: string;
}

export interface InsightItem {
  insight: string;
  category: "positive" | "warning" | "alert" | "info";
  metric: string;
}

export interface ClassificationRule {
  id: number;
  key_phrase: string;
  head: string;
  type: string;
  rule_type: "user_learned" | "vendor_exact" | "regex_keyword";
  pattern: string | null;
  normalized_vendor: string | null;
  is_enabled: boolean;
  confidence: number;
  use_count: number;
  confirmation_count: number;
  scope: "user" | "system";
  created_at: string;
  updated_at: string;
}

export interface RulesStats {
  total: number;
  active: number;
  user_learned: number;
  vendor_exact: number;
  regex_keyword: number;
  system_rules: number;
}

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  company_id: number;
  created_at: string;
}

export interface BusinessAccount {
  id: number;
  name: string;
  is_active: boolean;
  company_id: number;
  description?: string;
  created_at: string;
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  plan: string;
  max_business_accounts: number;
  is_active: boolean;
  created_at: string;
}

// ─── Auth APIs ───────────────────────────────────────────────────────────────

export const loginUser = (email: string, password: string) =>
  api.post<{ otp_session_token: string; message: string }>(
    "/api/auth/login",
    { email, password }
  );

export const verifyOTP = (otpSessionToken: string, otpCode: string) =>
  api.post<{
    access_token: string;
    token_type: string;
    user: AuthUser;
    active_business_id: number | null;
  }>("/api/auth/verify-otp", {
    otp_session_token: otpSessionToken,
    otp_code: otpCode,
  });

export const resendOTP = (otpSessionToken: string) =>
  api.post<{ otp_session_token: string; message: string }>(
    "/api/auth/resend-otp",
    { otp_session_token: otpSessionToken }
  );

export const refreshAuthToken = () =>
  api.post<{ access_token: string; active_business_id: number | null }>(
    "/api/auth/refresh"
  );

export const logoutUser = () => api.post("/api/auth/logout");

export const switchBusinessAccount = (businessAccountId: number) =>
  api.post<{ access_token: string; active_business_id: number; business_name: string }>(
    `/api/auth/switch-business/${businessAccountId}`
  );

export const forgotPassword = (email: string) =>
  api.post<{ otp_session_token: string; message: string }>(
    "/api/auth/forgot-password",
    { email }
  );

export const resetPassword = (
  otpSessionToken: string,
  otpCode: string,
  newPassword: string
) =>
  api.post("/api/auth/reset-password", {
    otp_session_token: otpSessionToken,
    otp_code: otpCode,
    new_password: newPassword,
  });

// ─── User APIs ────────────────────────────────────────────────────────────────

export const getMyProfile = () => api.get<AuthUser>("/api/users/me");
export const getMyBusinessAccounts = () =>
  api.get<BusinessAccount[]>("/api/users/me/business-accounts");
export const listUsers = () => api.get<AuthUser[]>("/api/users/");
export const createUser = (data: {
  email: string; password: string; full_name: string;
  role: string; company_id?: number; business_account_ids?: number[];
}) => api.post<AuthUser>("/api/users/", data);
export const inactivateUser = (id: number, reason?: string) =>
  api.post(`/api/users/${id}/inactivate`, { reason });
export const reactivateUser = (id: number) =>
  api.post(`/api/users/${id}/reactivate`);

// ─── Company APIs ─────────────────────────────────────────────────────────────

export const listCompanies = () => api.get<Company[]>("/api/companies/");
export const createCompany = (data: {
  name: string; plan?: string; max_business_accounts?: number;
}) => api.post<Company>("/api/companies/", data);
export const inactivateCompany = (id: number, reason?: string) =>
  api.post(`/api/companies/${id}/inactivate`, { reason });
export const reactivateCompany = (id: number) =>
  api.post(`/api/companies/${id}/reactivate`);
export const getCompanyBusinessAccounts = (companyId: number) =>
  api.get<BusinessAccount[]>(`/api/companies/${companyId}/business-accounts`);
export const createBusinessAccount = (
  companyId: number,
  data: { name: string; description?: string }
) => api.post<BusinessAccount>(`/api/companies/${companyId}/business-accounts`, data);

// ─── Upload APIs ─────────────────────────────────────────────────────────────

export const uploadFile = (
  file: File,
  onProgress?: (progress: number) => void
) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post<Upload>("/api/uploads", formData, {
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded * 100) / evt.total));
      }
    },
  });
};

export const getUploads = () => api.get<Upload[]>("/api/uploads");
export const getUpload = (id: number) => api.get<Upload>(`/api/uploads/${id}`);
export const deleteUpload = (id: number) => api.delete(`/api/uploads/${id}`);

// ─── Transaction APIs ────────────────────────────────────────────────────────

export const getTransactions = (params?: {
  month?: string; status?: string; head?: string;
  upload_id?: number; skip?: number; limit?: number;
}) => api.get<Transaction[]>("/api/transactions", { params });
export const getMonths = () => api.get<string[]>("/api/transactions/months");
export const updateTransaction = (
  id: number,
  data: { head?: string; type?: string; comments?: string; create_rule?: boolean }
) => api.put<Transaction>(`/api/transactions/${id}`, data);
export const bulkUpdateTransactions = (
  ids: number[],
  data: { head: string; type?: string; comments?: string; create_rule?: boolean }
) => api.post("/api/transactions/bulk-update", { ids, ...data });
export const reprocessMonth = (month: string) =>
  api.post(`/api/transactions/reprocess/${month}`);

// ─── Metrics APIs ────────────────────────────────────────────────────────────

export const getAllMetrics = () => api.get<MonthlyMetric[]>("/api/metrics");
export const getMonthMetrics = (month: string) =>
  api.get<MonthlyMetric>(`/api/metrics/${month}`);
export const recalculateMetrics = (month: string) =>
  api.post<MonthlyMetric>(`/api/metrics/recalculate/${month}`);

// ─── Insights APIs ───────────────────────────────────────────────────────────

export const getInsights = (month: string) =>
  api.get<AIInsight>(`/api/insights/${month}`);
export const generateInsights = (month: string) =>
  api.post<AIInsight>(`/api/insights/generate/${month}`);

// ─── Rules APIs ──────────────────────────────────────────────────────────────

export const getRulesStats = () => api.get<RulesStats>("/api/rules/stats");
export const getRules = (params?: {
  rule_type?: string; is_enabled?: boolean; scope?: string;
}) => api.get<ClassificationRule[]>("/api/rules", { params });
export const createRule = (data: {
  key_phrase: string; head: string; type: string;
  rule_type?: string; pattern?: string; normalized_vendor?: string;
  is_enabled?: boolean; confidence?: number; scope?: string;
}) => api.post<ClassificationRule>("/api/rules", data);
export const updateRule = (
  id: number,
  data: Partial<{
    key_phrase: string; head: string; type: string; rule_type: string;
    pattern: string | null; normalized_vendor: string | null;
    is_enabled: boolean; confidence: number; scope: string;
  }>
) => api.put<ClassificationRule>(`/api/rules/${id}`, data);
export const deleteRule = (id: number) => api.delete(`/api/rules/${id}`);
export const promoteRule = (id: number) =>
  api.post<ClassificationRule>(`/api/rules/${id}/promote`);
export const seedRules = () => api.post("/api/rules/seed");

// ─── Aggregate metrics types ─────────────────────────────────────────────────

export interface MonthlyBreakdown {
  month: string;
  total_inflow: number;
  total_outflow: number;
  net_cashflow: number;
  indicator_cashflow: number;
  transaction_count: number;
  sma_3?: number | null;  // 3-month SMA of outflow; null for first 2 months
}

export interface AggregatedMetrics {
  period_label: string;
  date_from: string;
  date_to: string;
  business_names: string[];
  is_multi_month: boolean;
  total_inflow: number;
  total_outflow: number;
  net_cashflow: number;
  indicator_cashflow: number;
  fixed_cost_ratio: number;
  payroll_ratio: number;
  cash_runway: number | null;
  vendor_dependency: number | null;
  transaction_count: number;
  mapped_count: number;
  category_breakdown: string | null;
  monthly_breakdown: MonthlyBreakdown[];
  prev_period_label?: string;
  prev_total_inflow?: number;
  prev_total_outflow?: number;
  prev_net_cashflow?: number;
}

export interface DateRange {
  dateFrom: string;   // YYYY-MM
  dateTo: string;     // YYYY-MM
  label: string;
}

// ─── Aggregate metrics APIs ───────────────────────────────────────────────────

export const getAggregateMetrics = (
  businessIds: number[],
  dateFrom: string,
  dateTo: string,
) =>
  api.get<AggregatedMetrics>("/api/metrics/aggregate", {
    params: { business_ids: businessIds, date_from: dateFrom, date_to: dateTo },
    paramsSerializer: { indexes: null },  // serialize as business_ids=1&business_ids=2 (no brackets)
  });

export const generateAggregateInsights = (
  businessIds: number[],
  dateFrom: string,
  dateTo: string,
) =>
  api.post<{
    period_label: string;
    business_names: string[];
    insights: string;
    generated_at: string;
  }>("/api/insights/generate-aggregate", {
    business_ids: businessIds,
    date_from: dateFrom,
    date_to: dateTo,
  });

// ─── Helpers ─────────────────────────────────────────────────────────────────

export const formatCurrency = (value: number): string => {
  if (Math.abs(value) >= 10000000) {
    return `₹${(value / 10000000).toFixed(2)}Cr`;
  }
  if (Math.abs(value) >= 100000) {
    return `₹${(value / 100000).toFixed(2)}L`;
  }
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
};

export const formatMonth = (month: string): string => {
  if (!month) return "";
  const [year, m] = month.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(m) - 1]} ${year}`;
};
