import csv

from django.core.management.base import BaseCommand

from map.models import CommunityArea


class Command(BaseCommand):
    help = (
        "Backfill CommunityArea.population from a CSV with columns "
        "community_area (name, uppercase) and total_population."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the population CSV (see data/raw/community_area_population_acs2023.csv).",
        )

    def handle(self, *args, **kwargs):
        path = kwargs["csv_file"]

        # Normalize names so "O'Hare" matches "OHARE", "McKinley Park"
        # matches "MCKINLEY PARK", etc.
        def norm(s):
            return "".join(ch for ch in (s or "").upper() if ch.isalnum())

        with open(path, "r") as f:
            reader = csv.DictReader(f)
            populations = {
                norm(row["community_area"]): int(float(row["total_population"]))
                for row in reader
                if row["total_population"]
            }

        updated = 0
        missing = []
        for area in CommunityArea.objects.all():
            pop = populations.get(norm(area.name))
            if pop is None:
                missing.append(area.name)
                continue
            area.population = pop
            area.save(update_fields=["population"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated population on {updated} community areas."))
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"No population row matched {len(missing)} areas: {', '.join(missing)}"
                )
            )
