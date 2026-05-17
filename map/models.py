from django.contrib.gis.db import models as gis_models
from django.db import models


class CommunityArea(models.Model):
    name = models.CharField(max_length=32, null=True, blank=True)
    area_id = models.IntegerField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name.title()


class RestaurantPermit(models.Model):
    permit_id = models.CharField(max_length=16, null=True, blank=True)
    permit_type = models.CharField(max_length=64, null=True, blank=True)
    application_start_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    work_description = models.TextField(null=True, blank=True)
    street_number = models.CharField(max_length=16, null=True, blank=True)
    street_direction = models.CharField(max_length=8, null=True, blank=True)
    street_name = models.CharField(max_length=32, null=True, blank=True)
    location = gis_models.PointField(null=True, blank=True)
    community_area_id = models.CharField(max_length=2, null=True, blank=True)

    class Meta:
        indexes = [
            # Serves the choropleth's per-year GROUP BY community_area_id.
            models.Index(
                fields=["issue_date", "community_area_id"],
                name="permit_date_area_idx",
            ),
        ]
