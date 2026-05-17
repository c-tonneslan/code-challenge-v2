from __future__ import annotations

from rest_framework import serializers

from map.models import CommunityArea


class CommunityAreaSerializer(serializers.ModelSerializer):
    """Serialize a community area plus its permit count for one year.

    The expensive counts and per-type breakdowns are NOT derived per-row.
    The view builds them once via a single GROUP BY query and passes them
    through `serializer.context` so each `get_*` is a dict lookup.
    """

    class Meta:
        model = CommunityArea
        fields = [
            "name",
            "area_id",
            "population",
            "num_permits",
            "permits_per_10k",
            "permits_by_type",
        ]

    num_permits = serializers.SerializerMethodField()
    permits_per_10k = serializers.SerializerMethodField()
    permits_by_type = serializers.SerializerMethodField()

    def get_num_permits(self, obj: CommunityArea) -> int:
        counts: dict[str, int] = self.context.get("permits_by_area", {})
        return counts.get(str(obj.area_id), 0)

    def get_permits_per_10k(self, obj: CommunityArea) -> float | None:
        count = self.get_num_permits(obj)
        if not obj.population:
            return None
        return round(count / obj.population * 10_000, 2)

    def get_permits_by_type(self, obj: CommunityArea) -> dict[str, int]:
        types: dict[str, dict[str, int]] = self.context.get("types_by_area", {})
        return types.get(str(obj.area_id), {})
