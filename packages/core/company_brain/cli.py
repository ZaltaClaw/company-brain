"""`company-brain` CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load .env from cwd or repo root.
for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break

console = Console()


@click.group()
def cli() -> None:
    """Company Brain — local-first unified memory engine."""


@cli.command("init-db")
def init_db() -> None:
    """Apply schema.sql to the configured Postgres."""
    from company_brain.stores.postgres import PostgresStore

    store = PostgresStore.from_env()
    store.init_schema()
    console.print("[green]✓[/green] schema applied")
    store.close()


@cli.command()
@click.argument("source", type=click.Choice(["fabric", "work", "foundry", "all"]))
def ingest(source: str) -> None:
    """Run a connector ingest."""
    from company_brain.store import get_store

    store = get_store()
    try:
        if source in ("fabric", "all"):
            from connectors.fabric_iq.ingest import run as run_fabric

            run_fabric(store, console=console)
        if source in ("work", "all"):
            from connectors.work_iq.ingest import run as run_work

            run_work(store, console=console)
        if source in ("foundry", "all"):
            from connectors.foundry_iq.ingest import run as run_foundry

            run_foundry(store, console=console)
    finally:
        store.close()


@cli.command()
@click.argument("query")
@click.option("--container-tag", "-c", default=None, help="Prefix filter, e.g. 'fabric:'.")
@click.option("--limit", "-n", default=10, type=int)
@click.option("--json", "as_json", is_flag=True)
def search(query: str, container_tag: str | None, limit: int, as_json: bool) -> None:
    """Vector search over memories."""
    from company_brain.store import get_store

    store = get_store()
    try:
        results = store.search(query, container_tag=container_tag, limit=limit)
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                [
                    {
                        "score": r.score,
                        "content": r.memory.content,
                        "container_tag": r.memory.container_tag,
                        "source": r.memory.source,
                        "fact_type": r.memory.fact_type,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
        return

    table = Table(title=f"search: {query!r}")
    table.add_column("score", justify="right")
    table.add_column("source")
    table.add_column("type")
    table.add_column("container")
    table.add_column("content", overflow="fold")
    for r in results:
        table.add_row(
            f"{r.score:.3f}",
            r.memory.source,
            r.memory.fact_type or "-",
            r.memory.container_tag,
            r.memory.content,
        )
    console.print(table)


@cli.command()
@click.option("--container-tag", "-c", default=None)
def profile(container_tag: str | None) -> None:
    """Show aggregate profile for a container tag (or all)."""
    from company_brain.store import get_store

    store = get_store()
    try:
        p = store.profile(container_tag=container_tag)
    finally:
        store.close()
    console.print_json(data=p)


@cli.command()
def status() -> None:
    """Connect to Postgres and show row counts per container_tag."""
    from company_brain.stores.postgres import PostgresStore

    store = PostgresStore.from_env()
    try:
        rows = store.status_by_tag()
    except Exception as e:
        console.print(f"[red]✗ could not connect:[/red] {e}")
        sys.exit(1)
    finally:
        store.close()

    if not rows:
        console.print("[yellow]no data ingested yet[/yellow]")
        return
    t = Table(title="company-brain status")
    t.add_column("container_tag")
    t.add_column("documents", justify="right")
    t.add_column("memories", justify="right")
    for tag, d, m in rows:
        t.add_row(tag or "-", str(d), str(m))
    console.print(t)


if __name__ == "__main__":
    cli()
