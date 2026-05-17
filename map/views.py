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


class DataSummary(TemplateView):
    template_name = "map/data_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        yearly = (
            RestaurantPermit.objects
            .annotate(year=ExtractYear("issue_date"))
            .values("year")
            .annotate(n=Count("id"))
            .order_by("year")
        )
        yearly_list = [{"year": r["year"], "count": r["n"]} for r in yearly if r["year"]]

        max_count = max((r["count"] for r in yearly_list), default=0)
        chart_width = 640
        chart_height = 240
        bar_gap = 8
        n = len(yearly_list)
        bar_width = (chart_width - bar_gap * (n - 1)) / n if n else 0

        for i, r in enumerate(yearly_list):
            ratio = r["count"] / max_count if max_count else 0
            r["bar_height"] = round(ratio * (chart_height - 24))
            r["bar_x"] = round(i * (bar_width + bar_gap))
            r["bar_y"] = chart_height - r["bar_height"] - 18
            r["bar_width"] = round(bar_width)
            r["label_x"] = round(i * (bar_width + bar_gap) + bar_width / 2)
            r["label_y"] = chart_height - 2

        ctx["yearly"] = yearly_list
        ctx["chart_width"] = chart_width
        ctx["chart_height"] = chart_height
        ctx["total"] = sum(r["count"] for r in yearly_list)

        top_areas = (
            RestaurantPermit.objects
            .values("community_area_id")
            .annotate(n=Count("id"))
            .order_by("-n")[:10]
        )
        area_lookup = {
            str(a.area_id): a.name
            for a in CommunityArea.objects.all()
        }
        ctx["top_areas"] = [
            {
                "name": area_lookup.get(row["community_area_id"], f"Area {row['community_area_id']}"),
                "count": row["n"],
            }
            for row in top_areas
        ]

        return ctx


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
