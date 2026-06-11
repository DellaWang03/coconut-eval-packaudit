from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


REQUIRED_ORDER_COLUMNS = {"package_id", "carrier", "promised_ship_time"}
REQUIRED_SCAN_COLUMNS = {"package_id", "scan_time"}


class AuditError(Exception):
    pass


def load_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise AuditError(f"File not found: {path}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise AuditError(f"File is empty or has no header: {path}")
            missing = required_columns - set(reader.fieldnames)
            if missing:
                raise AuditError(
                    f"Missing required columns in {path.name}: {sorted(missing)}"
                )
            return list(reader)
    except UnicodeDecodeError as e:
        raise AuditError(f"Cannot read {path}: {e}") from e


def parse_datetime(value: str, field_name: str, row_context: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise AuditError(
        f"Bad datetime '{value}' in {field_name} (row: {row_context}). "
        f"Expected format: YYYY-MM-DD HH:MM:SS"
    )


def audit(
    orders_path: Path, scans_path: Path, as_of: datetime
) -> dict:
    orders = load_csv(orders_path, REQUIRED_ORDER_COLUMNS)
    scans = load_csv(scans_path, REQUIRED_SCAN_COLUMNS)

    scan_map: dict[str, list[datetime]] = {}
    for row in scans:
        pkg = row["package_id"].strip()
        if not pkg:
            continue
        ts = parse_datetime(row["scan_time"], "scan_time", f"package_id={pkg}")
        scan_map.setdefault(pkg, []).append(ts)

    results: list[dict] = []
    carrier_delays: dict[str, int] = {}

    for row in orders:
        pkg = row["package_id"].strip()
        carrier = row["carrier"].strip()
        promised = parse_datetime(
            row["promised_ship_time"], "promised_ship_time", f"package_id={pkg}"
        )

        pkg_scans = scan_map.get(pkg, [])
        pkg_scans_sorted = sorted(pkg_scans)

        issues: list[str] = []
        first_scan = None
        last_scan = None
        is_delayed = False

        if not pkg_scans_sorted:
            issues.append("missing_scan")
            if as_of > promised:
                is_delayed = True
        else:
            first_scan = pkg_scans_sorted[0]
            last_scan = pkg_scans_sorted[-1]
            if last_scan > promised:
                is_delayed = True

            seen: set[str] = set()
            for ts in pkg_scans_sorted:
                key = ts.isoformat()
                if key in seen:
                    if "duplicate_scan" not in issues:
                        issues.append("duplicate_scan")
                else:
                    seen.add(key)

        if is_delayed:
            carrier_delays[carrier] = carrier_delays.get(carrier, 0) + 1

        results.append(
            {
                "package_id": pkg,
                "carrier": carrier,
                "promised_ship_time": promised.isoformat(),
                "first_scan": first_scan.isoformat() if first_scan else None,
                "last_scan": last_scan.isoformat() if last_scan else None,
                "is_delayed": is_delayed,
                "issues": issues,
            }
        )

    return {
        "as_of": as_of.isoformat(),
        "total_orders": len(results),
        "delayed_orders": sum(1 for r in results if r["is_delayed"]),
        "orders": results,
        "carrier_delay_summary": carrier_delays,
    }


def write_report(report: dict, output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
