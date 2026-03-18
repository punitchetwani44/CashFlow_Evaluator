import re
import pandas as pd
import pdfplumber
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ── Column keyword lists ──────────────────────────────────────────────────────

DATE_KEYWORDS = [
    "date", "txn date", "transaction date", "value date", "posting date",
    "dt", "trans date", "val dt",
]
DESC_KEYWORDS = [
    "description", "narration", "particulars", "remarks", "reference",
    "details", "transaction remarks", "chq", "trans details",
]
DEBIT_KEYWORDS = [
    "debit", "withdrawal", "withdrawals", "debit amount",
    "paid out", "debit(dr)", "dr amount",
]
CREDIT_KEYWORDS = [
    "credit", "deposit", "deposits", "credit amount",
    "paid in", "credit(cr)", "cr amount",
]
BALANCE_KEYWORDS = [
    "balance", "bal", "closing balance", "running balance",
    "avail bal", "available balance",
]
# Combined amount column (used together with a DR/CR indicator column)
AMOUNT_KEYWORDS = [
    "amount", "amount(inr)", "transaction amount", "txn amount",
    "amt", "net amount",
]
# DR / CR indicator column
DRCR_KEYWORDS = [
    "debit/credit", "dr/cr", "cr/dr", "type", "txn type",
    "transaction type", "dr or cr",
]

# ── Noise-row patterns to skip (no-date rows that might slip through) ─────────
_NOISE_DESC = re.compile(
    r"^\s*(opening\s+balance|closing\s+balance|transaction\s+total"
    r"|balance\s+b[\./]?f|brought\s+forward|carried\s+forward"
    r"|opening\s+bal\.?|closing\s+bal\.?|total\s+dr|total\s+cr"
    r"|legend\s*:|unless\s+the|depositor|insurance|registered\s+office"
    r"|branch\s+address|note\s*:)\b",
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_amount(value) -> Optional[float]:
    """Parse a monetary string to float, returning None for non-numeric values."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "nan", "None", "-", "N/A", "DR", "CR", "dr", "cr"):
        return None
    # Remove currency symbols, Indian number separators, whitespace
    s = re.sub(r"[₹$\s]", "", s)
    s = re.sub(r"Rs\.?", "", s, flags=re.IGNORECASE)
    # Remove commas (handles both 1,000.00 and 1,00,000.00 formats)
    s = s.replace(",", "")
    # Handle negative in parentheses: (1000) → -1000
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # Strip trailing Dr/Cr suffixes some banks append
    s = re.sub(r"[dDcC][rR]$", "", s).strip()
    try:
        val = float(s)
        return val if val != 0.0 else None
    except ValueError:
        return None


def _parse_date(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if not s or s in ("nan", "None"):
        return None
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y",
        "%d %B %Y", "%d-%B-%Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d/%m/%y", "%d-%m-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _score_column(col_name: str, keywords: List[str]) -> int:
    col_lower = str(col_name).lower().strip()
    score = 0
    for kw in keywords:
        if col_lower == kw:
            score += 10
        elif kw in col_lower:
            score += 5
        elif any(word in col_lower for word in kw.split()):
            score += 2
    return score


def _detect_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Return a mapping of logical field → actual column name.

    Detects two layouts:
      A) Separate debit / credit columns
      B) Single amount column + DR/CR indicator column  ← Axis Bank style
    """
    mapping: Dict[str, Optional[str]] = {
        "date": None, "description": None,
        "debit": None, "credit": None, "balance": None,
        # extras for layout B
        "amount": None, "dr_cr": None,
    }
    scores: Dict[str, List[Tuple[str, int]]] = {k: [] for k in mapping}

    for col in columns:
        scores["date"].append((col, _score_column(col, DATE_KEYWORDS)))
        scores["description"].append((col, _score_column(col, DESC_KEYWORDS)))
        scores["debit"].append((col, _score_column(col, DEBIT_KEYWORDS)))
        scores["credit"].append((col, _score_column(col, CREDIT_KEYWORDS)))
        scores["balance"].append((col, _score_column(col, BALANCE_KEYWORDS)))
        scores["amount"].append((col, _score_column(col, AMOUNT_KEYWORDS)))
        scores["dr_cr"].append((col, _score_column(col, DRCR_KEYWORDS)))

    for key in mapping:
        candidates = sorted(scores[key], key=lambda x: -x[1])
        if candidates and candidates[0][1] > 0:
            mapping[key] = candidates[0][0]

    # Prefer layout B when a DR/CR indicator column was found AND the
    # top-scoring "debit" / "credit" column is the *same* column (both keywords
    # matched a single "Debit/Credit" header) — meaning there is no real
    # separate debit column.
    if (
        mapping["dr_cr"]
        and mapping["amount"]
        and mapping["debit"] == mapping["credit"]   # same col matched both
    ):
        mapping["debit"] = None   # suppress — we'll use amount + dr_cr instead
        mapping["credit"] = None

    return mapping


def _find_header_row(df: pd.DataFrame) -> int:
    """
    Scan up to the first 40 rows to find the row that contains both a date-like
    and a description-like column header.  Returns the 0-based row index.
    """
    for i in range(min(40, len(df))):
        row_vals = [str(v).lower().strip() for v in df.iloc[i] if pd.notna(v) and str(v).strip()]
        has_date = any(any(kw in v for kw in DATE_KEYWORDS) for v in row_vals)
        has_desc = any(any(kw in v for kw in DESC_KEYWORDS) for v in row_vals)
        if has_date and has_desc:
            return i
        # partial match – peek at next row
        if (has_date or has_desc) and i + 1 < len(df):
            next_vals = [str(v).lower().strip() for v in df.iloc[i + 1] if pd.notna(v)]
            if any(any(kw in v for kw in DATE_KEYWORDS) for v in next_vals):
                continue
            return i
    return 0


def _find_data_end(df: pd.DataFrame, date_col: str, desc_col: str) -> int:
    """
    Return the index (exclusive) of the last real transaction row.

    Stops at the first row that:
      - Has an empty / unparseable date AND a description matching footer patterns
        (CLOSING BALANCE, TRANSACTION TOTAL, etc.)
      - OR: is an all-NaN row followed only by legend / disclaimer text
    """
    last_data_idx = 0
    for i, row in df.iterrows():
        date_val = str(row.get(date_col, "")).strip()
        desc_val = str(row.get(desc_col, "")).strip().lower()
        date_ok = bool(_parse_date(date_val))

        if not date_ok:
            # Rows with no date are already skipped in _normalize_rows,
            # but if they look like footer rows we stop scanning entirely
            # so we don't accidentally pick up stray later data rows.
            if _NOISE_DESC.match(desc_val):
                return last_data_idx + 1
        else:
            last_data_idx = i   # type: ignore[assignment]

    return last_data_idx + 1   # type: ignore[operator]


def _normalize_rows(df: pd.DataFrame, col_map: Dict) -> List[Dict]:
    transactions: List[Dict] = []
    date_col   = col_map.get("date")
    desc_col   = col_map.get("description")
    debit_col  = col_map.get("debit")
    credit_col = col_map.get("credit")
    bal_col    = col_map.get("balance")
    amt_col    = col_map.get("amount")    # layout B
    drcr_col   = col_map.get("dr_cr")    # layout B

    if not date_col or not desc_col:
        raise ValueError(
            f"Could not detect required columns. Detected mapping: {col_map}. "
            "Ensure the file has Date and Description/Narration/Particulars columns."
        )

    use_layout_b = bool(amt_col and drcr_col and not debit_col and not credit_col)
    logger.info(
        "Column map: %s  |  layout=%s", col_map, "B (amount+dr_cr)" if use_layout_b else "A (debit/credit)"
    )

    for _, row in df.iterrows():
        # ── Date ──────────────────────────────────────────────────────────────
        date_str = _parse_date(row.get(date_col))
        if not date_str:
            continue   # header repeat, opening/closing balance rows, legend, etc.

        # ── Description ───────────────────────────────────────────────────────
        description = str(row.get(desc_col, "")).strip()
        if not description or description.lower() in ("nan", "none", ""):
            continue

        # Explicitly skip known noise descriptions (OPENING BALANCE etc.)
        if _NOISE_DESC.match(description):
            continue

        # ── Amount ────────────────────────────────────────────────────────────
        balance = _clean_amount(row.get(bal_col)) if bal_col else None

        if use_layout_b:
            # Layout B: single Amount column + DR/CR indicator
            raw_amount = _clean_amount(row.get(amt_col))
            if raw_amount is None:
                continue

            indicator = str(row.get(drcr_col, "")).strip().upper()
            if indicator in ("CR", "C", "CREDIT"):
                debit, credit = None, raw_amount
                txn_type = "inflow"
            elif indicator in ("DR", "D", "DEBIT"):
                debit, credit = raw_amount, None
                txn_type = "outflow"
            else:
                # Fallback: can't determine direction → skip
                logger.warning("Unknown DR/CR indicator '%s' for row: %s", indicator, description)
                continue
        else:
            # Layout A: separate debit / credit columns
            debit  = _clean_amount(row.get(debit_col))  if debit_col  else None
            credit = _clean_amount(row.get(credit_col)) if credit_col else None

            if debit and debit > 0:
                txn_type = "outflow"
            elif credit and credit > 0:
                txn_type = "inflow"
            else:
                continue   # row has no amount — skip

            raw_amount = debit or credit

        amount = abs(raw_amount) if raw_amount else (debit or credit or 0)
        month = date_str[:7]

        transactions.append({
            "date":        date_str,
            "description": description,
            "amount":      amount,
            "type":        txn_type,
            "head":        None,
            "month":       month,
            "comments":    None,
            "raw_debit":   debit,
            "raw_credit":  credit,
            "raw_balance": balance,
            "status":      "unmapped",
        })

    return transactions


# ── Main parser class ─────────────────────────────────────────────────────────

class FileParser:

    def parse(self, file_path: str, file_type: str) -> List[Dict]:
        file_type = file_type.lower().lstrip(".")
        if file_type in ("xls", "xlsx"):
            return self._parse_excel(file_path)
        elif file_type == "csv":
            return self._parse_csv(file_path)
        elif file_type == "pdf":
            return self._parse_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    # ── Excel ─────────────────────────────────────────────────────────────────

    def _parse_excel(self, file_path: str) -> List[Dict]:
        try:
            raw = pd.read_excel(file_path, header=None, dtype=str)
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {e}")

        header_row = _find_header_row(raw)
        logger.info("Excel header detected at row index %d", header_row)

        df = pd.read_excel(file_path, header=header_row, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all")

        # Drop rows that are clearly account-info / legend text:
        # they have the first non-null cell contain a long prose sentence.
        df = _drop_non_table_rows(df)

        col_map = _detect_columns(list(df.columns))
        return _normalize_rows(df, col_map)

    # ── CSV ───────────────────────────────────────────────────────────────────

    def _parse_csv(self, file_path: str) -> List[Dict]:
        try:
            raw = pd.read_csv(file_path, header=None, dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            raw = pd.read_csv(file_path, header=None, dtype=str, encoding="latin-1")

        header_row = _find_header_row(raw)
        try:
            df = pd.read_csv(
                file_path, header=header_row, dtype=str, encoding="utf-8-sig",
                skiprows=range(1, header_row) if header_row > 0 else None,
            )
        except Exception:
            df = pd.read_csv(file_path, header=header_row, dtype=str, encoding="latin-1")

        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all")

        col_map = _detect_columns(list(df.columns))
        return _normalize_rows(df, col_map)

    # ── PDF ───────────────────────────────────────────────────────────────────

    def _parse_pdf(self, file_path: str) -> List[Dict]:
        all_rows: List[List[str]] = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        cleaned = [str(c).strip() if c else "" for c in row]
                        if not any(cleaned):
                            continue
                        all_rows.append(cleaned)

        if not all_rows:
            return self._parse_pdf_text(file_path)

        # Find header row in extracted rows
        header_idx = 0
        for i, row in enumerate(all_rows[:20]):
            row_lower = [v.lower() for v in row]
            if any(any(kw in v for kw in DATE_KEYWORDS) for v in row_lower):
                header_idx = i
                break

        if not all_rows[header_idx:]:
            raise ValueError("No transaction data found in PDF")

        headers   = all_rows[header_idx]
        data_rows = all_rows[header_idx + 1:]

        df = pd.DataFrame(data_rows, columns=headers)
        df.columns = [str(c).strip() for c in df.columns]

        col_map = _detect_columns(list(df.columns))
        return _normalize_rows(df, col_map)

    def _parse_pdf_text(self, file_path: str) -> List[Dict]:
        """Fallback: parse PDF as raw text using regex."""
        transactions = []
        date_pattern   = re.compile(
            r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}\s+\w{3}\s+\d{4})"
        )
        amount_pattern = re.compile(r"[\d,]+\.\d{2}")

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.split("\n")
                for line in lines:
                    date_match = date_pattern.search(line)
                    if not date_match:
                        continue
                    amounts = amount_pattern.findall(line)
                    if not amounts:
                        continue
                    date_str = _parse_date(date_match.group(0))
                    if not date_str:
                        continue
                    description = line[:date_match.start()].strip() or line[date_match.end():].strip()
                    description = re.sub(r"\s+", " ", description).strip()
                    if not description:
                        continue
                    clean_amounts = [float(a.replace(",", "")) for a in amounts]
                    if len(clean_amounts) >= 2:
                        amount  = clean_amounts[-2]
                        balance = clean_amounts[-1]
                    else:
                        amount  = clean_amounts[0]
                        balance = None

                    month = date_str[:7]
                    transactions.append({
                        "date":        date_str,
                        "description": description,
                        "amount":      amount,
                        "type":        "outflow",   # classifier will fix this
                        "head":        None,
                        "month":       month,
                        "comments":    None,
                        "raw_debit":   None,
                        "raw_credit":  None,
                        "raw_balance": balance,
                        "status":      "unmapped",
                    })

        return transactions


# ── Post-read row filter ──────────────────────────────────────────────────────

def _drop_non_table_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    After loading the DataFrame with the detected header, drop rows that are
    clearly NOT transaction rows:

    - Rows where column 0 (or the leftmost non-null value) is a long prose
      string (>80 chars) — these are legend / disclaimer / address lines that
      sometimes appear below the transaction table in Indian bank statements.
    - Rows where every cell except the first is empty AND the first cell
      starts with a common footer keyword.
    """
    keep_mask = []
    cols = list(df.columns)
    first_col = cols[0] if cols else None

    for _, row in df.iterrows():
        if first_col is None:
            keep_mask.append(True)
            continue

        first_val = str(row[first_col]).strip()

        # Long prose sentence → footer / legend row
        if len(first_val) > 80:
            keep_mask.append(False)
            continue

        # Footer keyword in first cell, all other cells empty
        other_vals = [str(row[c]).strip() for c in cols[1:]]
        all_other_empty = all(v in ("", "nan", "None") for v in other_vals)
        if all_other_empty and _NOISE_DESC.match(first_val):
            keep_mask.append(False)
            continue

        keep_mask.append(True)

    return df[keep_mask].reset_index(drop=True)
