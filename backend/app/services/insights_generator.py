import json
import logging
from typing import List, Dict, Optional
from openai import OpenAI
from ..config import settings

logger = logging.getLogger(__name__)


class InsightsGenerator:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if not settings.openai_api_key:
            return None
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def generate(
        self,
        month: str,
        current: Dict,
        previous: Optional[Dict] = None,
        period_label: Optional[str] = None,
        business_names: Optional[List[str]] = None,
    ) -> List[Dict]:
        if not self.client:
            return [
                {
                    "insight": "Add your OPENAI_API_KEY to the .env file to enable AI-powered insights.",
                    "category": "info",
                    "metric": "config",
                }
            ]

        # MoM change calculations
        def pct_change(curr, prev):
            if prev and prev > 0:
                return (curr - prev) / prev * 100
            return 0.0

        inflow_change = pct_change(current["total_inflow"], previous["total_inflow"] if previous else 0)
        outflow_change = pct_change(current["total_outflow"], previous["total_outflow"] if previous else 0)

        # Format category breakdown
        cat_data = json.loads(current.get("category_breakdown") or "{}")
        outflow_cats = {k.split(":", 1)[1]: v for k, v in cat_data.items() if k.startswith("outflow:")}
        inflow_cats = {k.split(":", 1)[1]: v for k, v in cat_data.items() if k.startswith("inflow:")}

        top_outflows = sorted(outflow_cats.items(), key=lambda x: -x[1])[:8]
        top_inflows = sorted(inflow_cats.items(), key=lambda x: -x[1])[:5]

        outflow_str = "\n".join(f"  - {k}: ₹{v:,.0f}" for k, v in top_outflows) or "  No data"
        inflow_str = "\n".join(f"  - {k}: ₹{v:,.0f}" for k, v in top_inflows) or "  No data"

        fixed_cost_ratio = current.get("fixed_cost_ratio", 0) or 0
        payroll_ratio = current.get("payroll_ratio", 0) or 0
        cash_runway = current.get("cash_runway")
        runway_str = f"{cash_runway:.1f} months" if cash_runway else "N/A (no balance data)"

        scope_str = ", ".join(business_names) if business_names else "Single business"
        period_str = period_label or month

        prompt = f"""You are a financial analyst specializing in Indian SME cashflow analysis.
Analyze this data for {period_str} and provide 4-5 concise, actionable financial insights.

SCOPE: {scope_str}
PERIOD: {period_str}

FINANCIAL SUMMARY:
- Total Inflow: ₹{current['total_inflow']:,.0f}
- Total Outflow: ₹{current['total_outflow']:,.0f}
- Net Cashflow: ₹{current['net_cashflow']:,.0f} ({"SURPLUS" if current['net_cashflow'] >= 0 else "DEFICIT"})
- Indicator Cashflow: ₹{current['indicator_cashflow']:,.0f}

MONTH-OVER-MONTH:
- Inflow: {inflow_change:+.1f}%
- Outflow: {outflow_change:+.1f}%

LEADING INDICATORS:
- Fixed Cost Ratio: {fixed_cost_ratio:.1f}% (Indian SME healthy benchmark: <50%)
- Payroll Ratio: {payroll_ratio:.1f}% (Indian SME healthy benchmark: <35%)
- Cash Runway: {runway_str} (Recommended: >3 months)

TOP OUTFLOW CATEGORIES:
{outflow_str}

TOP INFLOW SOURCES:
{inflow_str}

Return ONLY a JSON object:
{{
  "insights": [
    {{
      "insight": "Specific actionable text with numbers. Keep under 80 words.",
      "category": "positive|warning|alert|info",
      "metric": "related metric (e.g. payroll_ratio, cash_runway, outflow)"
    }}
  ]
}}

Categories: "alert"=critical issue, "warning"=needs attention, "positive"=good trend, "info"=observation.
Focus on: cash burn, cost structure vs Indian SME benchmarks, unusual patterns, actionable recommendations."""

        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"},
                timeout=30,
            )
            result = json.loads(response.choices[0].message.content)
            return result.get("insights", [])
        except Exception as e:
            logger.error(f"Insights generation error: {e}")
            return [
                {
                    "insight": f"Failed to generate insights: {str(e)}",
                    "category": "info",
                    "metric": "error",
                }
            ]
