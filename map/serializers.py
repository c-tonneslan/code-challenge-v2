from rest_framework import serializers

from map.models import CommunityArea


class CommunityAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityArea
        fields = ["name", "area_id", "population", "num_permits", "permits_per_10k"]

    num_permits = serializers.SerializerMethodField()
    permits_per_10k = serializers.SerializerMethodField()

    def get_num_permits(self, obj):
        counts = self.context.get("permits_by_area", {})
        return counts.get(str(obj.area_id), 0)

    def get_permits_per_10k(self, obj):
        count = self.get_num_permits(obj)
        if not obj.population:
            return None
        return round(count / obj.population * 10_000, 2)
