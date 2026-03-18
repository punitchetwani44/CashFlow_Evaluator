import re
import json
import time
import logging
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from ..config import settings
from .rule_engine import rule_engine  # multi-phase rule engine

logger = logging.getLogger(__name__)

# ─── Cashflow heads ─────────────────────────────────────────────────────────────

INFLOW_HEADS = [
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
]

OUTFLOW_HEADS = [
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
]

ALL_HEADS = INFLOW_HEADS + OUTFLOW_HEADS

# ─── Key phrase extraction ───────────────────────────────────────────────────────

# Words that carry no vendor/customer identification value in Indian bank descriptions
_BANKING_NOISE = {
    # Banking channels
    "neft", "rtgs", "imps", "upi", "nach", "ecs", "chq", "cheque",
    # Directional / conjunctions
    "to", "from", "by", "at", "and", "or", "the", "for", "in", "on", "of",
    # Company legal suffixes (keep "corp" / "llp" — they identify the entity)
    "pvt", "ltd", "private", "limited", "inc", "co", "india",
    # Month abbreviations and full names
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
    # Generic transaction labels that don't identify the counterparty
    "ref", "no", "num", "id", "cr", "dr", "inv", "acct", "account",
    "transfer", "received", "paid", "payment", "credit", "debit",
    "transaction", "reversal", "bill", "charges", "advance", "monthly",
    "bank", "subscription", "services", "service", "order",
}


def extract_key_phrase(description: str) -> str:
    """
    Extract the identifying vendor/customer/service words from a bank description.

    Removes: banking prefixes (NEFT/RTGS/UPI), numeric tokens (dates, ref numbers,
    amounts), company legal suffixes (PVT LTD), and generic noise words.
    Keeps: vendor name, service name, or any distinguishing label.

    Examples
    --------
    "NEFT FROM ACME CORP INV001 2024"   → "acme corp"
    "SALARY CREDIT EMPLOYEES JAN 2024"  → "salary employees"
    "AWS CLOUD SERVICES SUBSCRIPTION"   → "aws cloud services"
    "ELECTRICITY BILL BESCOM"           → "electricity bescom"
    "HDFC BANK EMI LOAN ACCT 123"       → "hdfc emi loan"
    """
    text = description.lower()
    # Strip digit-containing tokens (ref numbers, dates, invoice numbers)
    text = re.sub(r'\b[\d][\d/\-\.]*\b', '', text)
    # Keep only letters and spaces
    text = re.sub(r'[^a-z\s]', ' ', text)
    # Normalise whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Keep meaningful words (length > 2, not in noise set)
    words = [w for w in text.split() if len(w) > 2 and w not in _BANKING_NOISE]
    # Up to 4 words — enough to uniquely identify a vendor/service
    return ' '.join(words[:4])


# ─── Rule matching ───────────────────────────────────────────────────────────────

def _match_rule(description: str, rules: List[Dict]) -> Optional[Dict]:
    """
    Return the best matching learned rule for a description, or None.

    Strategy: compare word overlap between the rule's stored key_phrase and the
    new description's extracted key phrase.  Requires ≥ 60% of the rule's words
    to appear (precision-biased to prevent false positives).
    """
    key = extract_key_phrase(description)
    if not key:
        return None

    key_words = set(key.split())
    best_match: Optional[Dict] = None
    best_score = 0.0

    for rule in rules:
        rule_key = rule.get("key_phrase", "").strip()
        if not rule_key:
            continue
        rule_words = set(rule_key.split())
        if not rule_words:
            continue

        overlap = len(rule_words & key_words)
        # Fraction of the rule's words covered by this description
        score = overlap / len(rule_words)

        # Require ≥ 60% coverage and at least 1 shared word
        if score >= 0.6 and overlap >= 1 and score > best_score:
            best_score = score
            best_match = rule

    return best_match


# ─── OpenAI prompt ───────────────────────────────────────────────────────────────

def _build_classification_prompt(transactions: List[Dict]) -> str:
    txn_lines = "\n".join(
        f'{i + 1}. [{t["type"].upper()}] ₹{t["amount"]:,.2f} - {t["description"]}'
        for i, t in enumerate(transactions)
    )
    inflow_str = ", ".join(INFLOW_HEADS)
    outflow_str = ", ".join(OUTFLOW_HEADS)

    return f"""You are a financial transaction classifier for Indian SMEs. Classify each bank transaction.

INFLOW HEADS (use for credit/deposit transactions):
{inflow_str}

OUTFLOW HEADS (use for debit/withdrawal transactions):
{outflow_str}

Transactions to classify:
{txn_lines}

Return ONLY a JSON object with key "classifications" containing an array:
{{
  "classifications": [
    {{"index": 1, "head": "exact head name", "type": "inflow", "confidence": 0.9}},
    ...
  ]
}}

Rules:
- Use EXACT head names from the lists above
- type must be "inflow" or "outflow"
- confidence is 0.0–1.0 (use < 0.7 when uncertain)
- If completely unsure, use "Unknown / Unmapped"
- Receipts = customer payments / sales proceeds
- Salaries = payroll, NEFT to employees
- Taxes = GST, TDS, advance tax, income tax payments
- Bank Charges = bank fees, service charges, SMS charges
- EMI = loan EMI payments
- Drawings = owner withdrawals"""


# ─── Classifier ──────────────────────────────────────────────────────────────────

class Classifier:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if not settings.openai_api_key:
            return None
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def _classify_batch(self, transactions: List[Dict]) -> List[Dict]:
        if not self.client:
            return [
                {**t, "head": "Unknown / Unmapped", "status": "unmapped", "classification_confidence": 0.0}
                for t in transactions
            ]

        prompt = _build_classification_prompt(transactions)
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=60,
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)
            classifications = result.get("classifications", [])
        except Exception as e:
            logger.error(f"OpenAI classification error: {e}")
            return [
                {**t, "head": "Unknown / Unmapped", "status": "unmapped", "classification_confidence": 0.0}
                for t in transactions
            ]

        classified = []
        for i, txn in enumerate(transactions):
            match = next((c for c in classifications if c.get("index") == i + 1), None)
            if match:
                head = match.get("head", "Unknown / Unmapped")
                if head not in ALL_HEADS:
                    head = "Unknown / Unmapped"
                confidence = float(match.get("confidence", 0.5))
                txn_type = match.get("type", txn["type"])
                if txn_type not in ("inflow", "outflow"):
                    txn_type = txn["type"]
                status = "mapped" if confidence >= settings.classification_confidence_threshold else "unmapped"
                classified.append({
                    **txn,
                    "head": head,
                    "type": txn_type,
                    "classification_confidence": confidence,
                    "status": status,
                })
            else:
                classified.append({
                    **txn,
                    "head": "Unknown / Unmapped",
                    "status": "unmapped",
                    "classification_confidence": 0.0,
                })
        return classified

    def classify_all(
        self,
        transactions: List[Dict],
        rules: Optional[List[Dict]] = None,
        batch_size: int = 30,
    ) -> List[Dict]:
        """Classify transactions using the multi-phase RuleEngine, then OpenAI fallback.

        Args:
            transactions: List of transaction dicts with at minimum
                          'description', 'type', and 'amount' keys.
            rules:        Optional list of rule dicts loaded from DB (all fields).
            batch_size:   Number of transactions per OpenAI API call.
        """
        if not transactions:
            return []

        db_rules: List[Dict] = rules or []

        # Phase 1-4 — RuleEngine (vendor / regex / user-learned / fuzzy)
        results: List[Optional[Dict]] = [None] * len(transactions)
        need_openai: List[Tuple[int, Dict]] = []

        for i, txn in enumerate(transactions):
            match = rule_engine.match(txn, db_rules)
            if match:
                conf = match["confidence"]
                txn_status = "mapped" if conf >= 0.80 else "unmapped"
                results[i] = {
                    **txn,
                    "head": match["head"],
                    "type": match["type"],
                    "classification_confidence": conf,
                    "status": txn_status,
                    "matched_rule_id": match.get("matched_rule_id"),
                    "matched_rule_source": match.get("matched_rule_source"),
                }
            else:
                need_openai.append((i, txn))

        rule_hits = len(transactions) - len(need_openai)
        if rule_hits:
            logger.info(
                f"RuleEngine auto-classified {rule_hits}/{len(transactions)} transactions"
            )

        # Phase 5 — OpenAI for whatever the rule engine didn't cover
        if need_openai:
            openai_txns = [t for _, t in need_openai]
            openai_results: List[Dict] = []

            for start in range(0, len(openai_txns), batch_size):
                batch = openai_txns[start: start + batch_size]
                classified = self._classify_batch(batch)
                # Mark LLM-classified rows with source
                for row in classified:
                    row.setdefault("matched_rule_id", None)
                    conf = row.get("classification_confidence", 0.0)
                    row["matched_rule_source"] = "llm" if conf > 0 else "none"
                openai_results.extend(classified)
                if start + batch_size < len(openai_txns):
                    time.sleep(0.1)

            for (orig_idx, _), result in zip(need_openai, openai_results):
                results[orig_idx] = result

        return [r for r in results if r is not None]
