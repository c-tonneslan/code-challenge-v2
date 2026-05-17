"""Scraper for Chicago's restaurant permit feed.

Built on scrapelib (https://github.com/datamade/scrapelib), the same library
DataMade uses across its civic-data work. scrapelib gives us retries with
backoff, a persistent session, and an on-disk request cache for free, all
backed by requests. That matters here because the Chicago Data Portal
occasionally drops connections on the bulk query, and we'd rather have a
scraper that finishes than one that 90% finishes.

The query: every restaurant retail-food permit with an issue_date in the
configured date window, returned as CSV. Same dataset the original Makefile
hits via plain curl - this just makes the call repeatable, retryable, and
testable.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from urllib.parse import quote_plus

import scrapelib

logger = logging.getLogger(__name__)


# Column projection. Keeping it narrow makes the bulk query 4x smaller on the
# wire than the full row, and we don't read the dropped columns anyway.
COLUMNS = [
    "id",
    "permit_",
    "permit_type",
    "review_type",
    "application_start_date",
    "issue_date",
    "processing_time",
    "street_number",
    "street_direction",
    "street_name",
    "work_description",
    "community_area",
    "census_tract",
    "ward",
    "latitude",
    "longitude",
    "location",
]


@dataclass(frozen=True)
class PermitWindow:
    """Inclusive issue_date range to pull."""
    start: date
    end: date

    def soql(self) -> str:
        # SoQL floating_timestamp literal. The portal accepts ISO 8601.
        return (
            f'`issue_date` BETWEEN '
            f'"{self.start.isoformat()}T00:00:00" :: floating_timestamp '
            f'AND "{self.end.isoformat()}T00:00:00" :: floating_timestamp'
        )


class ChicagoPermitScraper(scrapelib.Scraper):
    """Resilient HTTP client for the Chicago Data Portal's restaurant permits.

    Inherits from scrapelib.Scraper to pick up retries-with-backoff and
    optional on-disk caching. The portal's bulk query is the choke point;
    one transient 502 used to kill the loader. Now it retries 3 times with
    exponential backoff before giving up.
    """

    BASE = "https://data.cityofchicago.org"
    DATASET_ID = "fr9j-f3pa"  # Restaurant retail food permits

    def __init__(self, cache_dir: str | None = None) -> None:
        super().__init__(
            requests_per_minute=60,
            retry_attempts=3,
            retry_wait_seconds=2.0,
        )
        # Identify ourselves so the portal's logs aren't 'requests/2.x'.
        self.headers["User-Agent"] = "datamade-challenge-charlie-tonneslan/1.0"
        # Carry the optional app token without committing it. Portal allows
        # anonymous reads but rate-limits them; an app token raises the cap.
        token = os.environ.get("CDP_APP_TOKEN")
        if token:
            self.headers["X-App-Token"] = token

    def fetch_permits(self, window: PermitWindow) -> str:
        """Return the CSV body of every permit in the window."""
        query = self._build_query(window)
        url = (
            f"{self.BASE}/api/v3/views/{self.DATASET_ID}/query.csv"
            f"?query={quote_plus(query)}"
        )
        logger.info("scraping %s rows from %s", window, self.DATASET_ID)
        response = self.get(url)
        response.raise_for_status()
        return response.text

    def fetch_community_areas(self) -> str:
        """Return the community-areas GeoJSON. Different dataset, same portal."""
        url = f"{self.BASE}/resource/igwz-8jzy.geojson"
        response = self.get(url)
        response.raise_for_status()
        return response.text

    def _build_query(self, window: PermitWindow) -> str:
        cols = ",\n  ".join(f"`{c}`" for c in COLUMNS)
        return f"SELECT\n  {cols}\nWHERE\n  {window.soql()}"


def iter_csv_rows(body: str) -> Iterator[dict[str, str]]:
    """Yield dict rows from a CSV body. Wraps csv.DictReader so callers
    don't have to deal with the StringIO dance."""
    reader = csv.DictReader(io.StringIO(body))
    yield from reader
