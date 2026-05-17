from rest_framework import serializers

from map.models import CommunityArea, RestaurantPermit


class CommunityAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityArea
        fields = ["name", "area_id", "num_permits"]

    num_permits = serializers.SerializerMethodField()

    def get_num_permits(self, obj):
        year = self.context.get("year")
        if not year:
            return 0
        return RestaurantPermit.objects.filter(
            community_area_id=str(obj.area_id),
            issue_date__year=int(year),
        ).count()
