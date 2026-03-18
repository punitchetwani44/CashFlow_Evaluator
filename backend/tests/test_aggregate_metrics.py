"""Unit tests for calculate_aggregate_metrics().

Run with:
    cd backend
    /Users/dipenmakati/anaconda3/bin/python3 -m pytest tests/test_aggregate_metrics.py -v
"""
import json
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── In-memory SQLite DB for tests ─────────────────────────────────────────────
from app.database import Base
from app.models import Company, BusinessAccount, Transaction
from app.services.metrics_calculator import calculate_aggregate_metrics

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture()
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def company(db):
    c = Company(name="TestCo", slug="testco", plan="starter", max_business_accounts=5)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def ba1(db, company):
    ba = BusinessAccount(company_id=company.id, name="BA-One")
    db.add(ba)
    db.commit()
    db.refresh(ba)
    return ba


@pytest.fixture()
def ba2(db, company):
    ba = BusinessAccount(company_id=company.id, name="BA-Two")
    db.add(ba)
    db.commit()
    db.refresh(ba)
    return ba


def make_tx(db, ba_id, month, type_, head, amount, status="mapped"):
    t = Transaction(
        business_account_id=ba_id,
        upload_id=1,          # FK not enforced in SQLite without PRAGMA
        date=f"{month}-01",
        description=f"{head} test",
        amount=amount,
        type=type_,
        head=head,
        month=month,
        status=status,
    )
    db.add(t)
    db.commit()
    return t


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSingleBusinessSingleMonth:
    def test_inflow_outflow_sum(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  100_000)
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",   50_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries",  30_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")

        assert result["total_inflow"]  == 150_000
        assert result["total_outflow"] == 30_000
        assert result["net_cashflow"]  == 120_000
        assert result["transaction_count"] == 3

    def test_category_breakdown_populated(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  200_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries", 50_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")
        breakdown = json.loads(result["category_breakdown"])

        assert "inflow:Revenue"   in breakdown
        assert "outflow:Salaries" in breakdown
        assert breakdown["inflow:Revenue"]   == 200_000
        assert breakdown["outflow:Salaries"] == 50_000

    def test_mapped_count(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow", "Revenue", 100_000, status="mapped")
        make_tx(db, ba1.id, "2024-01", "inflow", "Revenue",  50_000, status="unmapped")

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")

        assert result["transaction_count"] == 2
        assert result["mapped_count"] == 1

    def test_fixed_cost_ratio(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  100_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries",  30_000)   # fixed
        make_tx(db, ba1.id, "2024-01", "outflow", "Rentals",   10_000)   # fixed

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")
        # fixed_costs = 40_000, inflow = 100_000 → 40%
        assert result["fixed_cost_ratio"] == pytest.approx(40.0)

    def test_payroll_ratio(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  200_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries",  40_000)   # payroll
        make_tx(db, ba1.id, "2024-01", "outflow", "Bonus Paid", 10_000)  # payroll

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")
        # payroll = 50_000, inflow = 200_000 → 25%
        assert result["payroll_ratio"] == pytest.approx(25.0)

    def test_vendor_dependency(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "outflow", "Suppliers' Payment", 80_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Suppliers' Payment", 20_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-01")
        # vendor_dependency merges by head so both go to same "Suppliers' Payment" key → 100%
        assert result["vendor_dependency"] == pytest.approx(100.0)


class TestMultiBusinessSingleMonth:
    def test_totals_are_sum_of_both_bas(self, db, ba1, ba2):
        make_tx(db, ba1.id, "2024-03", "inflow",  "Revenue", 100_000)
        make_tx(db, ba1.id, "2024-03", "outflow", "Salaries", 40_000)
        make_tx(db, ba2.id, "2024-03", "inflow",  "Revenue", 200_000)
        make_tx(db, ba2.id, "2024-03", "outflow", "Salaries", 60_000)

        result = calculate_aggregate_metrics(db, [ba1.id, ba2.id], "2024-03", "2024-03")

        assert result["total_inflow"]  == 300_000
        assert result["total_outflow"] == 100_000
        assert result["net_cashflow"]  == 200_000
        assert result["transaction_count"] == 4

    def test_category_breakdown_merged(self, db, ba1, ba2):
        make_tx(db, ba1.id, "2024-03", "inflow", "Revenue", 100_000)
        make_tx(db, ba2.id, "2024-03", "inflow", "Revenue", 200_000)

        result = calculate_aggregate_metrics(db, [ba1.id, ba2.id], "2024-03", "2024-03")
        breakdown = json.loads(result["category_breakdown"])

        assert breakdown["inflow:Revenue"] == 300_000

    def test_excludes_other_ba(self, db, ba1, ba2):
        """Transactions from ba2 are excluded when only ba1 is queried."""
        make_tx(db, ba1.id, "2024-03", "inflow", "Revenue", 100_000)
        make_tx(db, ba2.id, "2024-03", "inflow", "Revenue", 999_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-03", "2024-03")

        assert result["total_inflow"] == 100_000


class TestMultiBusinessMultiMonth:
    def test_monthly_breakdown_count(self, db, ba1, ba2):
        for mo in ["2024-01", "2024-02", "2024-03"]:
            make_tx(db, ba1.id, mo, "inflow",  "Revenue", 100_000)
            make_tx(db, ba2.id, mo, "outflow", "Salaries", 30_000)

        result = calculate_aggregate_metrics(db, [ba1.id, ba2.id], "2024-01", "2024-03")

        assert len(result["monthly_breakdown"]) == 3

    def test_monthly_breakdown_sorted(self, db, ba1):
        for mo in ["2024-03", "2024-01", "2024-02"]:
            make_tx(db, ba1.id, mo, "inflow", "Revenue", 10_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-03")
        months = [b["month"] for b in result["monthly_breakdown"]]

        assert months == sorted(months)

    def test_aggregated_totals_correct(self, db, ba1):
        make_tx(db, ba1.id, "2024-01", "inflow", "Revenue", 100_000)
        make_tx(db, ba1.id, "2024-02", "inflow", "Revenue", 200_000)
        make_tx(db, ba1.id, "2024-03", "inflow", "Revenue", 300_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries", 50_000)
        make_tx(db, ba1.id, "2024-02", "outflow", "Salaries", 60_000)
        make_tx(db, ba1.id, "2024-03", "outflow", "Salaries", 70_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-03")

        assert result["total_inflow"]  == 600_000
        assert result["total_outflow"] == 180_000
        assert result["net_cashflow"]  == 420_000


class TestFullYearAggregation:
    def test_fixed_cost_ratio_across_12_months(self, db, ba1):
        """fixed_cost_ratio = total_fixed / total_inflow * 100"""
        for mo in [f"2024-{str(m).zfill(2)}" for m in range(1, 13)]:
            make_tx(db, ba1.id, mo, "inflow",  "Revenue",  100_000)
            make_tx(db, ba1.id, mo, "outflow", "Salaries",  30_000)  # fixed cost

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-12")

        # total_inflow = 1_200_000; fixed_costs = 360_000 → 30%
        assert result["total_inflow"]    == 1_200_000
        assert result["fixed_cost_ratio"] == pytest.approx(30.0)
        assert len(result["monthly_breakdown"]) == 12

    def test_date_range_filtering(self, db, ba1):
        """Transactions outside the range must be excluded."""
        make_tx(db, ba1.id, "2023-12", "inflow", "Revenue", 999_000)  # outside
        make_tx(db, ba1.id, "2024-01", "inflow", "Revenue", 100_000)  # inside
        make_tx(db, ba1.id, "2024-12", "inflow", "Revenue", 200_000)  # inside
        make_tx(db, ba1.id, "2025-01", "inflow", "Revenue", 888_000)  # outside

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-12")

        assert result["total_inflow"] == 300_000


class TestPreviousPeriodComputation:
    def test_previous_period_inflow_outflow(self, db, ba1):
        # Current period: 2024-04 – 2024-06
        make_tx(db, ba1.id, "2024-04", "inflow",  "Revenue",  100_000)
        make_tx(db, ba1.id, "2024-05", "inflow",  "Revenue",  120_000)
        make_tx(db, ba1.id, "2024-06", "inflow",  "Revenue",  130_000)
        # Previous period: 2024-01 – 2024-03
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  80_000)
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries", 20_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-04", "2024-06")

        assert result["prev_total_inflow"]  == pytest.approx(80_000)
        assert result["prev_total_outflow"] == pytest.approx(20_000)
        assert result["prev_net_cashflow"]  == pytest.approx(60_000)
        assert result["prev_period_label"] is not None

    def test_previous_period_label_format(self, db, ba1):
        make_tx(db, ba1.id, "2024-03", "inflow", "Revenue", 50_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-03", "2024-03")
        # Previous period should be 2024-02
        assert "2024-02" in result["prev_period_label"]


class TestSMAWindowFunction:
    """3-month SMA of outflow computed via SQL window function."""

    def test_sma_null_for_first_two_months(self, db, ba1):
        """Months 1 and 2 have no full 3-month window — sma_3 must be None."""
        for mo in ["2024-01", "2024-02", "2024-03"]:
            make_tx(db, ba1.id, mo, "outflow", "Salaries", 30_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-03")
        bd = result["monthly_breakdown"]  # sorted: Jan, Feb, Mar

        assert bd[0]["sma_3"] is None, "Month 1 must have sma_3=None (partial window)"
        assert bd[1]["sma_3"] is None, "Month 2 must have sma_3=None (partial window)"

    def test_sma_value_from_month_three(self, db, ba1):
        """Month 3 SMA = avg of months 1, 2, 3."""
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries", 10_000)
        make_tx(db, ba1.id, "2024-02", "outflow", "Salaries", 20_000)
        make_tx(db, ba1.id, "2024-03", "outflow", "Salaries", 30_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-03")
        bd = result["monthly_breakdown"]

        expected_sma = (10_000 + 20_000 + 30_000) / 3
        assert bd[2]["sma_3"] == pytest.approx(expected_sma)

    def test_sma_rolling_window(self, db, ba1):
        """Month 4 SMA = avg of months 2, 3, 4 (not months 1,2,3)."""
        for mo, amt in [
            ("2024-01", 10_000),
            ("2024-02", 20_000),
            ("2024-03", 30_000),
            ("2024-04", 40_000),
        ]:
            make_tx(db, ba1.id, mo, "outflow", "Salaries", amt)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-04")
        bd = result["monthly_breakdown"]

        # Month 4 window: Feb(20k) + Mar(30k) + Apr(40k)
        expected_sma_m4 = (20_000 + 30_000 + 40_000) / 3
        assert bd[3]["sma_3"] == pytest.approx(expected_sma_m4)

    def test_sma_excludes_inflow(self, db, ba1):
        """SMA should only reflect outflow — inflow must not affect the value."""
        make_tx(db, ba1.id, "2024-01", "outflow", "Salaries", 10_000)
        make_tx(db, ba1.id, "2024-01", "inflow",  "Revenue",  999_000)  # must be ignored
        make_tx(db, ba1.id, "2024-02", "outflow", "Salaries", 10_000)
        make_tx(db, ba1.id, "2024-03", "outflow", "Salaries", 10_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-01", "2024-03")
        bd = result["monthly_breakdown"]

        # All three months have outflow=10k; SMA month-3 = 10k
        assert bd[2]["sma_3"] == pytest.approx(10_000)

    def test_sma_single_month_is_none(self, db, ba1):
        """Single-month query → only 1 data point → sma_3 must be None."""
        make_tx(db, ba1.id, "2024-06", "outflow", "Salaries", 50_000)

        result = calculate_aggregate_metrics(db, [ba1.id], "2024-06", "2024-06")
        bd = result["monthly_breakdown"]

        assert len(bd) == 1
        assert bd[0]["sma_3"] is None

    def test_sma_multi_business_outflow(self, db, ba1, ba2):
        """SMA aggregates outflow across multiple businesses."""
        for mo in ["2024-01", "2024-02", "2024-03"]:
            make_tx(db, ba1.id, mo, "outflow", "Salaries", 10_000)
            make_tx(db, ba2.id, mo, "outflow", "Salaries", 20_000)

        result = calculate_aggregate_metrics(
            db, [ba1.id, ba2.id], "2024-01", "2024-03"
        )
        bd = result["monthly_breakdown"]

        # Combined monthly outflow = 30k; SMA month-3 = avg(30k, 30k, 30k) = 30k
        expected_sma = 30_000.0
        assert bd[2]["sma_3"] == pytest.approx(expected_sma)
