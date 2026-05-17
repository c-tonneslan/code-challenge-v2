from __future__ import annotations

import os
from typing import Any

from django.db.models import Count
from django.db.models.functions import ExtractYear
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from map.models import CommunityArea, RestaurantPermit
from map.renderers import CSVRenderer, JSONRenderer
from map.serializers import CommunityAreaSerializer


class Home(TemplateView):
    template_name = "map/home_page.html"


class DataSummary(TemplateView):
    template_name = "map/data_summary.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
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

        # Year-over-year movers: top 5 climbers and top 5 droppers for the
        # latest available year pair. Uses the same logic as the /map-data/delta/
        # endpoint so the page agrees with whatever the API returns.
        years_present = sorted({r["year"] for r in yearly_list if r["year"]})
        if len(years_present) >= 2:
            to_year = years_present[-1]
            from_year = years_present[-2]
            from_counts = DeltaView._counts_for_year(from_year)
            to_counts = DeltaView._counts_for_year(to_year)
            movers: list[dict[str, Any]] = []
            for area_id, name in area_lookup.items():
                f = from_counts.get(area_id, 0)
                t = to_counts.get(area_id, 0)
                if f == 0 and t == 0:
                    continue
                movers.append({
                    "name": name,
                    "from": f,
                    "to": t,
                    "delta": t - f,
                })
            movers.sort(key=lambda r: r["delta"], reverse=True)
            ctx["yoy_pair"] = {"from_year": from_year, "to_year": to_year}
            ctx["yoy_up"] = [m for m in movers if m["delta"] > 0][:5]
            ctx["yoy_down"] = sorted(
                [m for m in movers if m["delta"] < 0], key=lambda r: r["delta"]
            )[:5]

        return ctx


class MapDataView(APIView):
    renderer_classes = [JSONRenderer, CSVRenderer]

    def get(self, request: Request) -> Response:
        year = request.query_params.get("year")

        permits_by_area: dict[str, int] = {}
        types_by_area: dict[str, dict[str, int]] = {}
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

    def get(self, request: Request) -> Response:
        rows = (
            RestaurantPermit.objects
            .annotate(year=ExtractYear("issue_date"))
            .values("community_area_id", "year")
            .annotate(n=Count("id"))
        )

        trends: dict[str, dict[int, int]] = {}
        for row in rows:
            area_id = row["community_area_id"]
            if not area_id:
                continue
            trends.setdefault(area_id, {})[row["year"]] = row["n"]

        return Response({"trends": trends})


class DeltaView(APIView):
    """Year-over-year change in permit count per community area.

    Response shape:
        {
          "from_year": 2022,
          "to_year": 2023,
          "areas": [
            {"area_id": "1", "name": "Rogers Park", "from": 12, "to": 18, "delta": 6, "pct_change": 50.0},
            ...
          ],
          "max_abs_delta": 47   // for symmetric choropleth scaling on the client
        }

    The question this answers is the one a journalist would actually ask:
    'which neighborhoods saw the biggest jump or drop in permits between
    these two years?' Two GROUP BY queries, joined in memory because the
    set is ~77 rows. Cheaper than a single window-function query.
    """

    def get(self, request: Request) -> Response:
        try:
            from_year = int(request.query_params.get("from") or 0)
            to_year = int(request.query_params.get("to") or 0)
        except (TypeError, ValueError):
            return Response({"error": "from and to must be integers"}, status=400)
        if not from_year or not to_year:
            return Response({"error": "from and to are required"}, status=400)
        if from_year == to_year:
            return Response({"error": "from and to must differ"}, status=400)

        from_counts = self._counts_for_year(from_year)
        to_counts = self._counts_for_year(to_year)

        area_lookup = {str(a.area_id): a.name for a in CommunityArea.objects.all()}
        rows: list[dict[str, Any]] = []
        max_abs = 0
        for area_id, name in area_lookup.items():
            f = from_counts.get(area_id, 0)
            t = to_counts.get(area_id, 0)
            delta = t - f
            if abs(delta) > max_abs:
                max_abs = abs(delta)
            pct = ((t - f) / f * 100) if f else None
            rows.append({
                "area_id": area_id,
                "name": name,
                "from": f,
                "to": t,
                "delta": delta,
                "pct_change": round(pct, 1) if pct is not None else None,
            })

        rows.sort(key=lambda r: r["delta"], reverse=True)
        return Response({
            "from_year": from_year,
            "to_year": to_year,
            "areas": rows,
            "max_abs_delta": max_abs,
        })

    @staticmethod
    def _counts_for_year(year: int) -> dict[str, int]:
        rows = (
            RestaurantPermit.objects
            .filter(issue_date__year=year)
            .values("community_area_id")
            .annotate(n=Count("id"))
        )
        return {str(r["community_area_id"]): r["n"] for r in rows}


def robots_txt(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "map/robots.txt",
        {"ALLOW_CRAWL": True if os.getenv("ALLOW_CRAWL") == "True" else False},
        content_type="text/plain",
    )


def page_not_found(
    request: HttpRequest, exception: Exception, template_name: str = "404.html"
) -> HttpResponse:
    return render(request, template_name, status=404)


def server_error(request: HttpRequest, template_name: str = "500.html") -> HttpResponse:
    return render(request, template_name, status=500)
