import os

from django.db.models import Count
from django.shortcuts import render
from django.views.generic import TemplateView

from rest_framework.views import APIView
from rest_framework.response import Response

from map.models import CommunityArea, RestaurantPermit
from map.serializers import CommunityAreaSerializer


class Home(TemplateView):
    template_name = "map/home_page.html"


class MapDataView(APIView):
    def get(self, request):
        year = request.query_params.get("year")

        permits_by_area = {}
        if year:
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                year_int = None
            if year_int is not None:
                counts = (
                    RestaurantPermit.objects
                    .filter(issue_date__year=year_int)
                    .values("community_area_id")
                    .annotate(n=Count("id"))
                )
                permits_by_area = {row["community_area_id"]: row["n"] for row in counts}

        community_areas = CommunityArea.objects.all()
        serializer = CommunityAreaSerializer(
            community_areas,
            many=True,
            context={"permits_by_area": permits_by_area},
        )
        return Response(serializer.data)


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
