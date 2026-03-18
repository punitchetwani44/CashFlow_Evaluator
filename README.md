# CashFlow Evaluator

AI-powered cashflow analysis for Indian SMEs. Upload bank statements (PDF/Excel/CSV), get automatic transaction classification, leading indicator dashboards, and GPT-4o-mini powered financial insights.

## Quick Start

### Option 1 — Docker (recommended)

```bash
cp .env.example .env
# Add your OpenAI API key to .env
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

### Option 2 — Local Development

**Backend:**
```bash
cd backend
cp ../.env.example .env        # Add OPENAI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes* | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model for classification & insights |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | No | `0.7` | Min confidence to mark as "mapped" |
| `DATABASE_URL` | No | `sqlite:///./cashflow.db` | Database connection string |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Backend URL for frontend |

*Without an OpenAI key, all transactions are marked "Unknown / Unmapped". You can still manually classify them via the Transactions page.

## Features

- **Multi-format upload** — PDF, XLS, XLSX, CSV with smart column detection
- **Auto-classification** — GPT-4o-mini classifies every transaction into cashflow heads from your Leading Indicator sheet
- **Manual review** — Inline editing, bulk updates, comment fields
- **Monthly reprocessing** — Re-classify any month while preserving your manual corrections
- **Dashboard** — 4 metric cards, inflow/outflow bar chart, net cashflow trend, category pie chart
- **Leading Indicators** — Fixed Cost Ratio, Payroll Ratio, Cash Runway, Vendor Dependency
- **AI Insights** — 3–5 actionable insights per month benchmarked against Indian SME standards

## Cashflow Classification Heads

Based on the Leading Indicator Cashflow sheet:

**Inflow:** Receipts, Interest on Investment, Commission Received, Rent Received, Loan Received/Recovered, Sale of Shares/Assets, Bank Interest, Capital Infused, Other Inflow

**Outflow:** Suppliers' Payment, Salaries, Rentals, Loan Repayment, EMI, Labor Charges, Utilities, Staff Welfare, Repairs & Maintenance, IT Expenses, Transportation, Asset Purchase, Consulting/Training Fees, Taxes, Drawings, Bank Charges, and more

## API Reference

Interactive docs at `http://localhost:8000/docs`

| Endpoint | Method | Description |
|---|---|---|
| `/api/uploads` | POST | Upload bank statement |
| `/api/uploads` | GET | List all uploads |
| `/api/transactions` | GET | Get transactions (filter by month/status/head) |
| `/api/transactions/{id}` | PUT | Update transaction head/comments |
| `/api/transactions/bulk-update` | POST | Bulk update transactions |
| `/api/transactions/reprocess/{month}` | POST | Re-classify a month |
| `/api/metrics` | GET | All monthly metrics |
| `/api/metrics/{month}` | GET | Metrics for a specific month |
| `/api/insights/generate/{month}` | POST | Generate AI insights |
| `/api/insights/{month}` | GET | Get cached insights |
