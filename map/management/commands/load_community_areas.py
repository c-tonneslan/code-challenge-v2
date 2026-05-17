import json

from django.core.management.base import BaseCommand

from map.models import CommunityArea


# Toponyms that title() gets wrong. Mostly Irish surnames and a couple
# of contractions that come through the GeoJSON in all-caps.
_NAME_OVERRIDES = {
    # The source GeoJSON has "OHARE" without the apostrophe; restore it.
    "OHARE": "O'Hare",
    "MCKINLEY PARK": "McKinley Park",
}


def prettify(name):
    upper = (name or "").strip().upper()
    if upper in _NAME_OVERRIDES:
        return _NAME_OVERRIDES[upper]
    return upper.title()


class Command(BaseCommand):
    help = "Load restaurant permit data from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "geojson_file", type=str, help="The path to the GeoJSON file to load"
        )

    def handle(self, *args, **kwargs):
        CommunityArea.objects.all().delete()

        geojson_file = kwargs["geojson_file"]

        with open(geojson_file, "r") as f:
            community_areas = json.load(f)

        community_area_objs = [
            CommunityArea(
                name=prettify(c["properties"]["community"]),
                area_id=c["properties"]["area_numbe"],
            )
            for c in community_areas["features"]
        ]

        CommunityArea.objects.bulk_create(community_area_objs)
