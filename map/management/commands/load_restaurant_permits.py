import csv
from datetime import datetime

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from django.core.management.base import BaseCommand

from map.models import RestaurantPermit


BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Load restaurant permit data from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file", type=str, help="The path to the CSV file to load"
        )

    def handle(self, *args, **kwargs):
        RestaurantPermit.objects.all().delete()

        csv_file = kwargs["csv_file"]

        permits = []
        skipped = 0

        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)

            for row in reader:
                has_valid_dates = row["application_start_date"] and row["issue_date"]
                if not has_valid_dates or not row["location"]:
                    skipped += 1
                    continue

                # Validate the geometry up front. GEOSGeometry will raise on
                # malformed WKT/WKB; we'd rather catch one bad row at parse
                # time than blow up the whole bulk_create later.
                try:
                    location = GEOSGeometry(row["location"])
                except GEOSException:
                    self.stdout.write(
                        f'Invalid location for ID {row["id"]}. Skipping...'
                    )
                    skipped += 1
                    continue

                permits.append(
                    RestaurantPermit(
                        permit_id=row["id"],
                        permit_type=row["permit_type"],
                        application_start_date=datetime.fromisoformat(
                            row["application_start_date"]
                        ),
                        issue_date=datetime.fromisoformat(row["issue_date"]),
                        work_description=row["work_description"],
                        street_number=row["street_number"],
                        street_direction=row["street_direction"],
                        street_name=row["street_name"],
                        location=location,
                        community_area_id=row["community_area"],
                    )
                )

        RestaurantPermit.objects.bulk_create(permits, batch_size=BATCH_SIZE)

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(permits)} permits. Skipped {skipped}."
            )
        )
