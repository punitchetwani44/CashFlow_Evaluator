export const INFLOW_HEADS = [
  "Receipts",
  "Interest on Investment",
  "Interest from Customers",
  "Commission Received",
  "Rent Received",
  "Loan Received",
  "Loan Recovered",
  "Sale of Shares",
  "Bank Interest",
  "Sale of Assets",
  "Capital Infused",
  "Other Inflow",
];

export const OUTFLOW_HEADS = [
  "Suppliers' Payment",
  "Salaries",
  "Rentals",
  "Loan Repayment",
  "EMI",
  "Labor Charges",
  "Utilities",
  "Staff Welfare",
  "Repairs & Maintenance",
  "IT Expenses",
  "Transportation",
  "Asset Purchase",
  "Furniture & Fixtures",
  "Consulting Fees",
  "Training Fees",
  "R&D Expenses",
  "Other Operating Expenses",
  "Interest Paid",
  "Insurance Premiums",
  "Taxes",
  "Fees & Charges",
  "Penalties",
  "Donations",
  "Drawings",
  "Bonus Paid",
  "Commissions Paid",
  "Capital Withdrawn",
  "Bank Charges",
  "Unknown / Unmapped",
];

export const ALL_HEADS = [...INFLOW_HEADS, ...OUTFLOW_HEADS];

export const CHART_COLORS = [
  "#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4",
  "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
];

export const INSIGHT_COLORS: Record<string, string> = {
  positive: "border-green-400 bg-green-50",
  warning: "border-amber-400 bg-amber-50",
  alert: "border-red-400 bg-red-50",
  info: "border-blue-400 bg-blue-50",
};

export const INSIGHT_ICONS: Record<string, string> = {
  positive: "✅",
  warning: "⚠️",
  alert: "🚨",
  info: "ℹ️",
};
