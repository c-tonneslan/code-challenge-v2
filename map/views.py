import os

from django.db.models import Count
from django.db.models.functions import ExtractYear
from django.shortcuts import render
from django.views.generic import TemplateView

from rest_framework.views import APIView
from rest_framework.response import Response

from map.models import CommunityArea, RestaurantPermit
from map.renderers import CSVRenderer, JSONRenderer
from map.serializers import CommunityAreaSerializer


class Home(TemplateView):
    template_name = "map/home_page.html"


class MapDataView(APIView):
    renderer_classes = [JSONRenderer, CSVRenderer]

    def get(self, request):
        year = request.query_params.get("year")

        permits_by_area = {}
        types_by_area = {}
        if year:
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                year_int = None
            if year_int is not None:
                rows = (
                    RestaurantPermit.objects
                    .filter(issue_date__year=year_int)
                    .values("community_area_id", "permit_type")
                    .annotate(n=Count("id"))
                )
                for row in rows:
                    area_id = row["community_area_id"]
                    permits_by_area[area_id] = permits_by_area.get(area_id, 0) + row["n"]
                    types_by_area.setdefault(area_id, {})[row["permit_type"]] = row["n"]

        community_areas = CommunityArea.objects.all()
        serializer = CommunityAreaSerializer(
            community_areas,
            many=True,
            context={
                "permits_by_area": permits_by_area,
                "types_by_area": types_by_area,
            },
        )
        return Response(serializer.data)


class TrendsView(APIView):
    """Per-community-area permit counts grouped by year.

    Response shape:
        {"trends": {"<area_id>": {"<year>": <count>, ...}, ...}}

    One query, server aggregates. Frontend uses this to draw a sparkline
    next to the top-N list without having to re-fetch the per-year view
    for every year.
    """

    def get(self, request):
        rows = (
            RestaurantPermit.objects
            .annotate(year=ExtractYear("issue_date"))
            .values("community_area_id", "year")
            .annotate(n=Count("id"))
        )

        trends = {}
        for row in rows:
            area_id = row["community_area_id"]
            if not area_id:
                continue
            trends.setdefault(area_id, {})[row["year"]] = row["n"]

        return Response({"trends": trends})


def robots_txt(request):
    return render(
        request,
        "map/robots.txt",
        {"ALLOW_CRAWL": True if os.getenv("ALLOW_CRAWL") == "True" else False},
        content_type="text/plain",
    )


def page_not_found(request, exception, template_name="404.html"):
    return render(request, template_name, status=404)


def server_error(request, template_name="500.html"):
    return render(request, template_name, status=500)
