from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from packaudit.core import AuditError, audit, load_csv


@pytest.fixture()
def tmp_csv(tmp_path):
    """Helper to write CSV files for tests."""

    def _write(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    return _write


class TestNormalReport:
    def test_basic_report(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 18:00:00\n"
            "PKG002,YTO,2026-06-11 20:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n"
            "PKG001,2026-06-11 09:00:00\n"
            "PKG001,2026-06-11 15:00:00\n"
            "PKG002,2026-06-11 10:00:00\n"
            "PKG002,2026-06-11 19:30:00\n",
        )
        as_of = datetime(2026, 6, 11, 23, 59, 59)
        report = audit(orders, scans, as_of)

        assert report["total_orders"] == 2
        assert report["delayed_orders"] == 0
        assert report["carrier_delay_summary"] == {}

        pkg1 = report["orders"][0]
        assert pkg1["package_id"] == "PKG001"
        assert pkg1["first_scan"] == "2026-06-11T09:00:00"
        assert pkg1["last_scan"] == "2026-06-11T15:00:00"
        assert pkg1["is_delayed"] is False
        assert pkg1["issues"] == []


class TestDelayed:
    def test_delayed_order(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 12:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n"
            "PKG001,2026-06-11 09:00:00\n"
            "PKG001,2026-06-11 14:00:00\n",
        )
        report = audit(orders, scans, datetime(2026, 6, 11, 23, 59, 59))

        assert report["delayed_orders"] == 1
        assert report["orders"][0]["is_delayed"] is True
        assert report["carrier_delay_summary"] == {"SF-Express": 1}

    def test_multiple_carriers_delay_summary(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 10:00:00\n"
            "PKG002,YTO,2026-06-11 10:00:00\n"
            "PKG003,YTO,2026-06-11 10:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n"
            "PKG001,2026-06-11 11:00:00\n"
            "PKG002,2026-06-11 12:00:00\n"
            "PKG003,2026-06-11 09:00:00\n",
        )
        report = audit(orders, scans, datetime(2026, 6, 11, 23, 59, 59))
        assert report["carrier_delay_summary"] == {"SF-Express": 1, "YTO": 1}


class TestMissingScan:
    def test_missing_scan_flagged(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 18:00:00\n",
        )
        scans = tmp_csv("scans.csv", "package_id,scan_time\n")
        report = audit(orders, scans, datetime(2026, 6, 11, 23, 59, 59))

        pkg = report["orders"][0]
        assert "missing_scan" in pkg["issues"]
        assert pkg["first_scan"] is None
        assert pkg["last_scan"] is None
        assert pkg["is_delayed"] is True


class TestDuplicateScan:
    def test_duplicate_scan_flagged(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 18:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n"
            "PKG001,2026-06-11 09:00:00\n"
            "PKG001,2026-06-11 09:00:00\n"
            "PKG001,2026-06-11 15:00:00\n",
        )
        report = audit(orders, scans, datetime(2026, 6, 11, 23, 59, 59))

        pkg = report["orders"][0]
        assert "duplicate_scan" in pkg["issues"]
        assert pkg["is_delayed"] is False


class TestBadCSV:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(AuditError, match="File not found"):
            audit(
                tmp_path / "nope.csv",
                tmp_path / "also_nope.csv",
                datetime(2026, 6, 11),
            )

    def test_missing_columns(self, tmp_csv):
        orders = tmp_csv("orders.csv", "package_id,carrier\nPKG001,SF\n")
        scans = tmp_csv("scans.csv", "package_id,scan_time\nPKG001,2026-06-11 09:00:00\n")
        with pytest.raises(AuditError, match="Missing required columns"):
            audit(orders, scans, datetime(2026, 6, 11))

    def test_bad_datetime_in_orders(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,not-a-date\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n" "PKG001,2026-06-11 09:00:00\n",
        )
        with pytest.raises(AuditError, match="Bad datetime"):
            audit(orders, scans, datetime(2026, 6, 11))

    def test_bad_datetime_in_scans(self, tmp_csv):
        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 18:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n" "PKG001,garbage\n",
        )
        with pytest.raises(AuditError, match="Bad datetime"):
            audit(orders, scans, datetime(2026, 6, 11))

    def test_empty_file(self, tmp_csv):
        orders = tmp_csv("orders.csv", "")
        scans = tmp_csv("scans.csv", "package_id,scan_time\n")
        with pytest.raises(AuditError, match="empty or has no header"):
            audit(orders, scans, datetime(2026, 6, 11))


class TestCLI:
    def test_happy_path(self, tmp_csv, tmp_path):
        from click.testing import CliRunner
        from packaudit.cli import main

        orders = tmp_csv(
            "orders.csv",
            "package_id,carrier,promised_ship_time\n"
            "PKG001,SF-Express,2026-06-11 18:00:00\n"
            "PKG002,YTO,2026-06-11 12:00:00\n",
        )
        scans = tmp_csv(
            "scans.csv",
            "package_id,scan_time\n"
            "PKG001,2026-06-11 10:00:00\n"
            "PKG002,2026-06-11 14:00:00\n",
        )
        output = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["audit", "--orders", str(orders), "--scans", str(scans),
             "--as-of", "2026-06-11", "--output", str(output)],
        )
        assert result.exit_code == 0
        assert output.exists()

        report = json.loads(output.read_text())
        assert report["total_orders"] == 2
        assert "carrier_delay_summary" in report
        assert report["carrier_delay_summary"] == {"YTO": 1}
        assert len(report["orders"]) == 2

    def test_bad_date_flag(self, tmp_csv, tmp_path):
        from click.testing import CliRunner
        from packaudit.cli import main

        orders = tmp_csv("orders.csv", "package_id,carrier,promised_ship_time\n")
        scans = tmp_csv("scans.csv", "package_id,scan_time\n")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["audit", "--orders", str(orders), "--scans", str(scans),
             "--as-of", "nope", "--output", str(tmp_path / "out.json")],
        )
        assert result.exit_code != 0
        assert "Bad date" in result.output
