"""
CLI for the AI Job Discovery Agent.
Usage:
  python -m app.cli discover --help
  python -m app.cli discover --max-companies 10 --fetch-jd
  python -m app.cli discover --all
"""
from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="AI Job Discovery Agent CLI")
console = Console()


@app.command()
def discover(
    max_companies: Optional[int] = typer.Option(
        None,
        "--max-companies",
        help="Limit number of companies to crawl (default: all)",
    ),
    fetch_jd: bool = typer.Option(
        False,
        "--fetch-jd",
        help="Also fetch full job descriptions from ATS platforms",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without persisting to database",
    ),
) -> None:
    """Discover job listings from Bangalore Startup Map and persist to database."""
    asyncio.run(_run_discovery(max_companies, fetch_jd, dry_run))


async def _run_discovery(
    max_companies: int | None,
    fetch_jd: bool,
    dry_run: bool,
) -> None:
    from app.core.database import AsyncSessionLocal
    from app.services.discovery.discovery_service import DiscoveryService

    console.print("[bold cyan]Starting job discovery...[/bold cyan]")
    if dry_run:
        console.print("[yellow]DRY RUN — nothing will be saved to database[/yellow]")

    async with AsyncSessionLocal() as db:
        service = DiscoveryService(db)
        stats = await service.run_discovery(
            max_companies=max_companies,
            fetch_jd=fetch_jd,
        )

    table = Table(title="Discovery Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)
    console.print("[bold green]Discovery complete![/bold green]")


@app.command()
def list_jobs(
    limit: int = typer.Option(20, "--limit", "-n"),
    level: Optional[str] = typer.Option(None, "--level"),
) -> None:
    """List discovered jobs."""
    asyncio.run(_list_jobs(limit, level))


async def _list_jobs(limit: int, level: str | None) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.database import AsyncSessionLocal
    from app.models.models import Job, Company

    async with AsyncSessionLocal() as db:
        stmt = select(Job).options(selectinload(Job.company)).limit(limit).order_by(Job.discovered_at.desc())
        if level:
            stmt = stmt.where(Job.level.ilike(f"%{level}%"))
        jobs = (await db.execute(stmt)).scalars().all()

    table = Table(title=f"Jobs (top {limit})", show_header=True)
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Company", style="green")
    table.add_column("Level", style="yellow")
    table.add_column("ATS")
    table.add_column("Status")

    for j in jobs:
        company_name = j.company.name if j.company else "Unknown"
        table.add_row(j.title, company_name, j.level or "-", j.ats_platform or "-", j.status)

    console.print(table)


if __name__ == "__main__":
    app()
