"""
rule_engine.py
~~~~~~~~~~~~~~
Multi-phase transaction-classification engine.

Priority pipeline (highest → lowest):
  1. user_learned  — word-overlap on key_phrase  (confidence from rule)
  2. vendor_exact  — normalised vendor token match (confidence from rule)
  3. regex_keyword — compiled regex on description (confidence from rule)
  4. fuzzy         — difflib SequenceMatcher ratio ≥ 0.85  (confidence 0.75)
  5. LLM fallback  — caller handles; this module returns None

NOTE: extract_key_phrase is imported *inside* the methods that need it to
avoid a circular import with services/classifier.py.
"""

from __future__ import annotations

import re
import difflib
from typing import Optional

# ---------------------------------------------------------------------------
# Built-in vendor dictionary
# key   → normalised vendor token (lowercase, no spaces)
# value → (head, type, confidence)
# ---------------------------------------------------------------------------
_BUILT_IN_VENDORS: dict[str, tuple[str, str, float]] = {
    # Food / welfare
    "zomato":       ("Staff Welfare", "outflow", 0.95),
    "swiggy":       ("Staff Welfare", "outflow", 0.95),
    "dunzo":        ("Staff Welfare", "outflow", 0.90),
    "zepto":        ("Staff Welfare", "outflow", 0.90),
    "blinkit":      ("Staff Welfare", "outflow", 0.90),
    "bigbasket":    ("Staff Welfare", "outflow", 0.85),

    # Payment gateways / receipts
    "razorpay":     ("Receipts", "inflow", 0.95),
    "cashfree":     ("Receipts", "inflow", 0.95),
    "paytm":        ("Receipts", "inflow", 0.90),
    "stripe":       ("Receipts", "inflow", 0.95),
    "ccavenue":     ("Receipts", "inflow", 0.90),
    "instamojo":    ("Receipts", "inflow", 0.90),
    "billdesk":     ("Receipts", "inflow", 0.88),

    # Telecom / utilities
    "airtel":       ("Utilities", "outflow", 0.95),
    "jio":          ("Utilities", "outflow", 0.95),
    "vodafone":     ("Utilities", "outflow", 0.95),
    "vi":           ("Utilities", "outflow", 0.88),
    "bsnl":         ("Utilities", "outflow", 0.95),
    "bescom":       ("Utilities", "outflow", 0.95),
    "msedcl":       ("Utilities", "outflow", 0.95),
    "tatapower":    ("Utilities", "outflow", 0.90),
    "mahanagar":    ("Utilities", "outflow", 0.85),
    "indiamart":    ("Marketing", "outflow", 0.85),

    # Cloud / IT
    "aws":          ("IT Expenses", "outflow", 0.95),
    "amazon":       ("IT Expenses", "outflow", 0.80),
    "azure":        ("IT Expenses", "outflow", 0.95),
    "microsoft":    ("IT Expenses", "outflow", 0.90),
    "google":       ("IT Expenses", "outflow", 0.85),
    "digitalocean": ("IT Expenses", "outflow", 0.95),
    "godaddy":      ("IT Expenses", "outflow", 0.95),
    "namecheap":    ("IT Expenses", "outflow", 0.95),
    "github":       ("IT Expenses", "outflow", 0.95),
    "slack":        ("IT Expenses", "outflow", 0.90),
    "zoom":         ("IT Expenses", "outflow", 0.90),
    "gsuite":       ("IT Expenses", "outflow", 0.95),

    # Insurance
    "lic":          ("Insurance Premiums", "outflow", 0.90),
    "hdfclife":     ("Insurance Premiums", "outflow", 0.90),
    "icicilombard": ("Insurance Premiums", "outflow", 0.90),
    "niacl":        ("Insurance Premiums", "outflow", 0.90),
    "starhealth":   ("Insurance Premiums", "outflow", 0.90),

    # Payroll / HR
    "greythr":      ("Salaries", "outflow", 0.90),
    "keka":         ("Salaries", "outflow", 0.90),
    "darwinbox":    ("Salaries", "outflow", 0.90),
    "zoho":         ("IT Expenses", "outflow", 0.85),

    # E-commerce / marketplaces
    "flipkart":     ("Office Supplies", "outflow", 0.80),
    "myntra":       ("Staff Welfare", "outflow", 0.75),
}

# ---------------------------------------------------------------------------
# Built-in regex rules
# Each entry: (pattern_str, head, type, confidence)
# ---------------------------------------------------------------------------
_BUILT_IN_REGEX: list[tuple[str, str, str, float]] = [
    # Salaries / payroll
    (r"\bsalary\b|\bpayroll\b|\bwages\b|\bpay\s*slip\b|\bstaff\s*pay\b",
     "Salaries", "outflow", 0.92),

    # EMI / loans
    (r"\bemi\b|\bhome\s*loan\b|\bcar\s*loan\b|\bpersonal\s*loan\b|\bloan\s*emi\b",
     "EMI", "outflow", 0.88),

    # Taxes / compliance
    (r"\bgst\b|\btds\b|\bincome\s*tax\b|\badvance\s*tax\b|\bprofessional\s*tax\b|\bpt\b",
     "Taxes", "outflow", 0.92),

    # Rent / lease
    (r"\brent\b|\brentals?\b|\blease\b|\boffice\s*rent\b|\bpremises\b",
     "Rentals", "outflow", 0.85),

    # Bank charges
    (r"\bbank\s*charges?\b|\bservice\s*charges?\b|\bprocessing\s*fee\b|\bannual\s*fee\b"
     r"|\bsms\s*charges?\b|\bdemat\s*charges?\b",
     "Bank Charges", "outflow", 0.88),

    # Bank interest earned
    (r"\binterest\s*credit\b|\binterest\s*received\b|\binterest\s*on\s*fd\b"
     r"|\bfd\s*interest\b|\bsavings\s*interest\b",
     "Bank Interest", "inflow", 0.88),

    # Capital infusion
    (r"\bcapital\s*infus\b|\bshare\s*capital\b|\bequity\s*infus\b|\binvestment\s*received\b"
     r"|\bfunding\b|\bseed\s*fund\b",
     "Capital Infused", "inflow", 0.85),

    # Capital withdrawal / drawings
    (r"\bdirector\s*drawing\b|\bdrawing\b|\bcapital\s*withdraw\b|\bpromoter\s*withdraw\b",
     "Capital Withdrawn", "outflow", 0.85),

    # E-commerce / marketplace receipts
    (r"\bamazon\s*pay\b|\bflipkart\s*seller\b|\bmeesho\b|\bsnapdeal\b",
     "Receipts", "inflow", 0.88),

    # Advertising / marketing
    (r"\bgoogle\s*ads?\b|\bfacebook\s*ads?\b|\bmeta\s*ads?\b|\binsta\s*ads?\b"
     r"|\bjustdial\b|\bsulekha\b|\bindiamart\b",
     "Marketing", "outflow", 0.88),

    # Travel / transport
    (r"\buber\b|\bola\b|\brapido\b|\bairlines?\b|\bairways\b|\birctc\b"
     r"|\btrain\s*ticket\b|\bflight\b",
     "Travel & Transport", "outflow", 0.85),

    # Penalties / late fees
    (r"\bpenalt\w+\b|\blate\s*fee\b|\bfine\b|\boverdue\b|\bpenalty\b",
     "Penalties", "outflow", 0.85),

    # Professional / consulting fees
    (r"\bconsulting\b|\bconsultancy\b|\bprofessional\s*fee\b|\blegal\s*fee\b"
     r"|\baudit\s*fee\b|\bca\s*fee\b",
     "Professional Fees", "outflow", 0.85),

    # Research & development
    (r"\bresearch\b|\br\s*&\s*d\b|\bdevelopment\s*expense\b|\bprototype\b",
     "R&D", "outflow", 0.80),
]

# Pre-compile regex patterns for speed
_COMPILED_REGEX: list[tuple[re.Pattern, str, str, float]] = [
    (re.compile(p, re.IGNORECASE), h, t, c)
    for p, h, t, c in _BUILT_IN_REGEX
]

# ---------------------------------------------------------------------------
# Refund / reversal detection
# ---------------------------------------------------------------------------
_REFUND_RE = re.compile(
    r"\bref(?:und)?\b|\breversal\b|\brev\b|\breverse\b|\bcancell?ed\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Channel-prefix stripping (UPI / NEFT / IMPS / etc.)
# ---------------------------------------------------------------------------
_CHANNEL_PREFIX_RE = re.compile(
    r"^(?:upi|neft|imps|rtgs|nach|ecs|ach|bbps|netbanking|nbd|ift|"
    r"trf|transfer|pymt|pmt|paymt|int(?:ernet)?\s*banking|mobile\s*banking|"
    r"atm|pos|sms|bill\s*pay)\s*[-/:~|]\s*",
    re.IGNORECASE,
)

# Legal suffix stripping
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(?:pvt\.?\s*ltd\.?|limited|llp|inc\.?|corp\.?|co\.?|"
    r"technologies?|tech|solutions?|services?|enterprises?|"
    r"group|india|software|systems?)\b.*$",
    re.IGNORECASE,
)


def normalize_vendor(description: str) -> str:
    """Return the first significant vendor token from a raw bank narration.

    Steps:
      1. Strip channel prefixes (UPI-, NEFT/, IMPS- …)
      2. Strip legal suffixes (Pvt Ltd, LLP, Technologies …)
      3. Lowercase + collapse whitespace
      4. Return the first token
    """
    s = description.strip()
    s = _CHANNEL_PREFIX_RE.sub("", s)
    s = _LEGAL_SUFFIX_RE.sub("", s)
    s = s.lower()
    # Remove special chars; keep alphanumeric + space
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    token = s.split()[0] if s.split() else ""
    return token


def is_refund_reversal(description: str) -> bool:
    """Return True if the transaction looks like a refund / reversal."""
    return bool(_REFUND_RE.search(description))


# ---------------------------------------------------------------------------
# RuleEngine
# ---------------------------------------------------------------------------

class RuleEngine:
    """Stateless rule-matching engine.  Instantiate once, call match() per txn."""

    # Minimum overlap fraction for user_learned phrase matching
    PHRASE_OVERLAP_THRESHOLD = 0.60
    # Minimum difflib ratio for fuzzy matching
    FUZZY_RATIO_THRESHOLD = 0.85
    FUZZY_CONFIDENCE = 0.75

    def match(
        self,
        txn: dict,
        db_rules: list[dict],
    ) -> Optional[dict]:
        """Try to classify *txn* using db_rules + built-ins.

        Returns a dict with keys::

            head, type, confidence, matched_rule_id, matched_rule_source

        or ``None`` if nothing matched (caller should fall back to LLM).

        *db_rules* is a list of dicts with keys:
          id, key_phrase, head, type, rule_type, pattern,
          normalized_vendor, is_enabled, confidence, scope
        """
        description: str = txn.get("description", "") or ""
        raw_type: str = txn.get("type", "") or ""

        # Filter to only enabled rules
        enabled_rules = [r for r in db_rules if r.get("is_enabled", True)]

        # Detect refund / reversal → may flip effective_type
        effective_type = raw_type
        if is_refund_reversal(description):
            if raw_type == "inflow":
                effective_type = "outflow"
            elif raw_type == "outflow":
                effective_type = "inflow"

        # --- Phase 1: user_learned ------------------------------------------
        result = self._match_user_learned(description, enabled_rules)
        if result:
            return result

        # --- Phase 2: vendor_exact ------------------------------------------
        result = self._match_vendor_exact(description, enabled_rules)
        if result:
            return result

        # --- Phase 3: regex_keyword -----------------------------------------
        result = self._match_regex(description, enabled_rules)
        if result:
            return result

        # --- Phase 4: fuzzy --------------------------------------------------
        result = self._fuzzy_match(description, enabled_rules)
        if result:
            return result

        return None  # LLM fallback

    # ------------------------------------------------------------------ #
    #  Private matchers                                                    #
    # ------------------------------------------------------------------ #

    def _match_user_learned(
        self, description: str, rules: list[dict]
    ) -> Optional[dict]:
        # Import here to avoid circular import with classifier.py
        from .classifier import extract_key_phrase  # noqa: PLC0415

        learned = [r for r in rules if r.get("rule_type", "user_learned") == "user_learned"]
        if not learned:
            return None

        desc_phrase = extract_key_phrase(description)
        if not desc_phrase:
            return None

        desc_tokens = set(desc_phrase.lower().split())
        best: Optional[dict] = None
        best_overlap = 0.0

        for rule in learned:
            kp = rule.get("key_phrase", "") or ""
            rule_tokens = set(kp.lower().split())
            if not rule_tokens:
                continue
            shared = desc_tokens & rule_tokens
            if not shared:
                continue
            overlap = len(shared) / max(len(desc_tokens), len(rule_tokens))
            if overlap >= self.PHRASE_OVERLAP_THRESHOLD and overlap > best_overlap:
                best_overlap = overlap
                best = rule

        if best:
            return {
                "head": best["head"],
                "type": best["type"],
                "confidence": best.get("confidence", 0.99),
                "matched_rule_id": best.get("id"),
                "matched_rule_source": "user_learned",
            }
        return None

    def _match_vendor_exact(
        self, description: str, rules: list[dict]
    ) -> Optional[dict]:
        vendor_token = normalize_vendor(description)
        if not vendor_token:
            return None

        # First check DB vendor_exact rules
        for rule in rules:
            if rule.get("rule_type") != "vendor_exact":
                continue
            nv = rule.get("normalized_vendor", "") or ""
            if nv and nv.lower() == vendor_token:
                return {
                    "head": rule["head"],
                    "type": rule["type"],
                    "confidence": rule.get("confidence", 0.95),
                    "matched_rule_id": rule.get("id"),
                    "matched_rule_source": "vendor_exact",
                }

        # Then check built-in vendor dict
        if vendor_token in _BUILT_IN_VENDORS:
            head, typ, conf = _BUILT_IN_VENDORS[vendor_token]
            return {
                "head": head,
                "type": typ,
                "confidence": conf,
                "matched_rule_id": None,
                "matched_rule_source": "vendor_exact",
            }

        return None

    def _match_regex(
        self, description: str, rules: list[dict]
    ) -> Optional[dict]:
        # DB regex rules first
        for rule in rules:
            if rule.get("rule_type") != "regex_keyword":
                continue
            pattern_str = rule.get("pattern") or ""
            if not pattern_str:
                continue
            try:
                if re.search(pattern_str, description, re.IGNORECASE):
                    return {
                        "head": rule["head"],
                        "type": rule["type"],
                        "confidence": rule.get("confidence", 0.88),
                        "matched_rule_id": rule.get("id"),
                        "matched_rule_source": "regex",
                    }
            except re.error:
                continue

        # Built-in compiled regex patterns
        for compiled_pat, head, typ, conf in _COMPILED_REGEX:
            if compiled_pat.search(description):
                return {
                    "head": head,
                    "type": typ,
                    "confidence": conf,
                    "matched_rule_id": None,
                    "matched_rule_source": "regex",
                }

        return None

    def _fuzzy_match(
        self, description: str, rules: list[dict]
    ) -> Optional[dict]:
        # Import here to avoid circular import
        from .classifier import extract_key_phrase  # noqa: PLC0415

        desc_phrase = extract_key_phrase(description).lower()
        if not desc_phrase:
            return None

        best: Optional[dict] = None
        best_ratio = 0.0

        for rule in rules:
            kp = (rule.get("key_phrase", "") or "").lower()
            if not kp:
                continue
            ratio = difflib.SequenceMatcher(None, desc_phrase, kp).ratio()
            if ratio >= self.FUZZY_RATIO_THRESHOLD and ratio > best_ratio:
                best_ratio = ratio
                best = rule

        if best:
            return {
                "head": best["head"],
                "type": best["type"],
                "confidence": self.FUZZY_CONFIDENCE,
                "matched_rule_id": best.get("id"),
                "matched_rule_source": "fuzzy",
            }

        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
rule_engine = RuleEngine()
