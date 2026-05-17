"""Refresh restaurant permits straight from the Chicago Data Portal.

The original Makefile shells out to `curl` to pull the CSV. That works once
but breaks on the first transient 502 and leaves you debugging a half-empty
file. This command uses scrapelib for retries + backoff, writes to the
canonical raw path, then re-runs the existing loader so the database matches
the new file in one step.

Usage:
    python manage.py scrape_permits                    # last 10 years
    python manage.py scrape_permits --since 2020-01-01 # custom window
    python manage.py scrape_permits --dry-run          # fetch + show stats, don't load
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser

from map.scraping import ChicagoPermitScraper, PermitWindow, iter_csv_rows

DEFAULT_RAW_PATH = Path("data/raw/chicago-restaurants.csv")


class Command(BaseCommand):
    help = "Pull the latest Chicago restaurant permits via scrapelib and load them."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="ISO date (YYYY-MM-DD) lower bound. Default: 10 years ago.",
        )
        parser.add_argument(
            "--until",
            type=str,
            default=None,
            help="ISO date (YYYY-MM-DD) upper bound. Default: today.",
        )
        parser.add_argument(
            "--out",
            type=Path,
            default=DEFAULT_RAW_PATH,
            help=f"Path to write the CSV to. Default: {DEFAULT_RAW_PATH}",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and print stats but skip the load step.",
        )

    def handle(self, *args: object, **opts: object) -> None:
        # Django types kwargs as object; argparse has already enforced shape
        # by this point, so cast for the type checker.
        from typing import cast
        since = cast(str | None, opts["since"])
        until = cast(str | None, opts["until"])
        out_path = cast(Path, opts["out"])
        window = self._parse_window(since, until)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"Scraping permits from {window.start} → {window.end}")
        scraper = ChicagoPermitScraper()
        body = scraper.fetch_permits(window)

        out_path.write_text(body)
        rows = list(iter_csv_rows(body))
        size_kb = len(body.encode("utf-8")) // 1024
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(rows)} rows ({size_kb} KB) → {out_path}"
            )
        )

        if opts["dry_run"]:
            self.stdout.write("Dry run, skipping load.")
            return

        self.stdout.write("Loading into the database…")
        call_command("load_restaurant_permits", str(out_path))

    @staticmethod
    def _parse_window(since: str | None, until: str | None) -> PermitWindow:
        if since:
            try:
                start = datetime.fromisoformat(since).date()
            except ValueError as e:
                raise CommandError(f"--since: {e}") from e
        else:
            today = date.today()
            start = today.replace(year=today.year - 10)
        if until:
            try:
                end = datetime.fromisoformat(until).date()
            except ValueError as e:
                raise CommandError(f"--until: {e}") from e
        else:
            end = date.today()
        if end <= start:
            raise CommandError("--until must be after --since")
        return PermitWindow(start=start, end=end)
