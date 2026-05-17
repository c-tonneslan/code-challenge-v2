from rest_framework import serializers

from map.models import CommunityArea


class CommunityAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityArea
        fields = ["name", "area_id", "num_permits"]

    num_permits = serializers.SerializerMethodField()

    def get_num_permits(self, obj):
        counts = self.context.get("permits_by_area", {})
        return counts.get(str(obj.area_id), 0)
