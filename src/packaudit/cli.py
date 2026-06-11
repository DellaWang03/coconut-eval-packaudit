from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click

from packaudit.core import AuditError, audit, write_report


@click.group()
def main():
    """PackAudit — shipment CSV auditing tool."""


@main.command()
@click.option("--orders", required=True, type=click.Path(), help="Path to orders CSV")
@click.option("--scans", required=True, type=click.Path(), help="Path to scans CSV")
@click.option(
    "--as-of",
    required=True,
    type=str,
    help="Reference date (YYYY-MM-DD) for delay evaluation",
)
@click.option(
    "--output", required=True, type=click.Path(), help="Output path for JSON report"
)
def audit_cmd(orders: str, scans: str, as_of: str, output: str):
    """Audit orders against scan records and produce a JSON report."""
    try:
        as_of_dt = datetime.strptime(as_of.strip(), "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError:
        click.echo(
            f"Error: Bad date '{as_of}'. Expected format: YYYY-MM-DD", err=True
        )
        sys.exit(1)

    try:
        report = audit(Path(orders), Path(scans), as_of_dt)
        write_report(report, Path(output))
    except AuditError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(
        f"Report written to {output} "
        f"({report['total_orders']} orders, {report['delayed_orders']} delayed)"
    )
