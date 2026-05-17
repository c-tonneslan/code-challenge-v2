"""Regenerate the community-area population CSV from raw ACS tract data.

Uses DataMade's `census` library (https://github.com/datamade/census) to
hit the Census Bureau's API directly, sums tract-level total population
into community areas via the crosswalk at
`data/raw/tract_to_community_area.csv`, and writes the result to
`data/raw/community_area_population_acs2023.csv`.

Run:

    CENSUS_API_KEY=your-key docker compose run --rm app \\
        python manage.py refresh_population_from_acs

You can get a free key in about 30 seconds at
https://api.census.gov/data/key_signup.html.

Without an API key the shipped CSV (already in this repo) is sufficient
for the loader; this command is only needed to refresh against a newer
ACS vintage or to change the variable being pulled.
"""

import csv
import os
import sys

from django.core.management.base import BaseCommand

# Cook County, Illinois.
STATE_FIPS = "17"
COUNTY_FIPS = "031"

# B01003_001E is total population. Swap for B19013_001E (median household
# income) etc. if you want different ACS variables.
ACS_VARIABLE = "B01003_001E"
ACS_YEAR = 2023

CROSSWALK_PATH = "data/raw/tract_to_community_area.csv"
OUTPUT_PATH = "data/raw/community_area_population_acs2023.csv"


class Command(BaseCommand):
    help = "Refresh community-area population from raw ACS tract data via the census library."

    def handle(self, *args, **kwargs):
        api_key = os.getenv("CENSUS_API_KEY")
        if not api_key:
            self.stderr.write(
                "CENSUS_API_KEY env var is required. Get one at "
                "https://api.census.gov/data/key_signup.html"
            )
            sys.exit(1)

        try:
            from census import Census
        except ImportError:
            self.stderr.write(
                "datamade/census is not installed. `pip install census` and rerun."
            )
            sys.exit(1)

        # Pull total population by tract for every tract in Cook County. The
        # `*` argument is the census library's way to ask for all tracts in
        # the given state/county.
        client = Census(api_key, year=ACS_YEAR)
        tracts = client.acs5.state_county_tract(
            ("NAME", ACS_VARIABLE),
            STATE_FIPS,
            COUNTY_FIPS,
            Census.ALL,
        )

        # tractce is the 6-digit tract code. The crosswalk's geoid10 is
        # state(2) + county(3) + tract(6), so reconstruct that here for the
        # join key.
        tract_pop = {}
        for row in tracts:
            geoid = f"{row['state']}{row['county']}{row['tract']}"
            value = row.get(ACS_VARIABLE)
            if value is not None:
                tract_pop[geoid] = int(value)

        with open(CROSSWALK_PATH) as f:
            reader = csv.DictReader(f)
            tract_to_area = {row["geoid10"]: row["commarea_n"] for row in reader if row["commarea_n"]}

        # Sum tract population into community areas. We also need names; the
        # GeoJSON has uppercase names indexed by area_numbe, but for output
        # we just use the area number and let the loader join on name via
        # the existing CSV format. To keep the output schema stable with the
        # shipped CSV, we look up names from the existing CSV header order.
        pop_by_area = {}
        for geoid, area_num in tract_to_area.items():
            pop_by_area[area_num] = pop_by_area.get(area_num, 0) + tract_pop.get(geoid, 0)

        # Preserve the shipped CSV's name-keyed shape so load_community_area_population
        # keeps working unchanged. Read existing CSV for the name -> area_num mapping.
        try:
            with open(OUTPUT_PATH) as f:
                existing = list(csv.DictReader(f))
            name_for_area = {}
            for row in existing:
                # Existing CSV has community_area + total_population, no area_num.
                # We need a name→number map. Read it from the GeoJSON instead.
                pass
        except FileNotFoundError:
            existing = []

        # Easier path: read the GeoJSON for the name <-> number mapping.
        import json
        with open("data/raw/community-areas.geojson") as f:
            features = json.load(f)["features"]
        name_for_area = {
            f["properties"]["area_numbe"]: f["properties"]["community"]
            for f in features
        }

        with open(OUTPUT_PATH, "w", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["community_area", "total_population"])
            for area_num, pop in sorted(pop_by_area.items(), key=lambda kv: name_for_area.get(kv[0], "")):
                name = name_for_area.get(area_num)
                if not name:
                    self.stdout.write(self.style.WARNING(f"No GeoJSON name for area {area_num}, skipping."))
                    continue
                writer.writerow([name, float(pop)])

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {OUTPUT_PATH} with {len(pop_by_area)} community areas from "
                f"{ACS_YEAR} ACS5 (variable {ACS_VARIABLE})."
            )
        )
