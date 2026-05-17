import pytest
from datetime import date

from django.shortcuts import reverse
from rest_framework.test import APIClient

from map.models import CommunityArea, RestaurantPermit


@pytest.mark.django_db
def test_map_data_view():
    # Create some test community areas
    area1 = CommunityArea.objects.create(name="Beverly", area_id="1")
    area2 = CommunityArea.objects.create(name="Lincoln Park", area_id="2")

    # Test permits for Beverly
    RestaurantPermit.objects.create(
        community_area_id=area1.area_id, issue_date=date(2021, 1, 15)
    )
    RestaurantPermit.objects.create(
        community_area_id=area1.area_id, issue_date=date(2021, 2, 20)
    )

    # Test permits for Lincoln Park
    RestaurantPermit.objects.create(
        community_area_id=area2.area_id, issue_date=date(2021, 3, 10)
    )
    RestaurantPermit.objects.create(
        community_area_id=area2.area_id, issue_date=date(2021, 2, 14)
    )
    RestaurantPermit.objects.create(
        community_area_id=area2.area_id, issue_date=date(2021, 6, 22)
    )

    # A permit in a different year, shouldn't show up in the 2021 count
    RestaurantPermit.objects.create(
        community_area_id=area1.area_id, issue_date=date(2020, 6, 1)
    )

    # Query the map data endpoint
    client = APIClient()
    response = client.get(reverse("map_data", query={"year": 2021}))

    assert response.status_code == 200

    by_name = {row["name"]: row for row in response.data}

    assert set(by_name) == {"Beverly", "Lincoln Park"}
    assert by_name["Beverly"]["num_permits"] == 2
    assert by_name["Lincoln Park"]["num_permits"] == 3


@pytest.mark.django_db
def test_map_data_view_no_year_returns_zero_counts():
    CommunityArea.objects.create(name="Beverly", area_id="1")
    RestaurantPermit.objects.create(
        community_area_id="1", issue_date=date(2021, 1, 15)
    )

    client = APIClient()
    response = client.get(reverse("map_data"))

    assert response.status_code == 200
    assert response.data[0]["num_permits"] == 0


@pytest.mark.django_db
def test_map_data_view_area_with_no_permits():
    CommunityArea.objects.create(name="Beverly", area_id="1")
    CommunityArea.objects.create(name="Lincoln Park", area_id="2")
    RestaurantPermit.objects.create(
        community_area_id="1", issue_date=date(2021, 1, 15)
    )

    client = APIClient()
    response = client.get(reverse("map_data", query={"year": 2021}))

    by_name = {row["name"]: row for row in response.data}
    assert by_name["Beverly"]["num_permits"] == 1
    assert by_name["Lincoln Park"]["num_permits"] == 0


@pytest.mark.django_db
def test_map_data_view_permits_by_type():
    CommunityArea.objects.create(name="Beverly", area_id="1")

    # Loader prettifies these before insert, mirror that here so the test
    # matches what production stores.
    RestaurantPermit.objects.create(
        community_area_id="1",
        permit_type="Renovation / Alteration",
        issue_date=date(2021, 1, 15),
    )
    RestaurantPermit.objects.create(
        community_area_id="1",
        permit_type="Renovation / Alteration",
        issue_date=date(2021, 2, 1),
    )
    RestaurantPermit.objects.create(
        community_area_id="1",
        permit_type="New Construction",
        issue_date=date(2021, 3, 1),
    )

    client = APIClient()
    response = client.get(reverse("map_data", query={"year": 2021}))

    row = next(r for r in response.data if r["name"] == "Beverly")
    assert row["num_permits"] == 3
    assert row["permits_by_type"] == {
        "Renovation / Alteration": 2,
        "New Construction": 1,
    }


@pytest.mark.django_db
def test_map_data_view_csv():
    CommunityArea.objects.create(name="Beverly", area_id="1", population=20_000)
    RestaurantPermit.objects.create(
        community_area_id="1", issue_date=date(2021, 1, 15)
    )

    client = APIClient()
    response = client.get(reverse("map_data", query={"year": 2021, "format": "csv"}))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")

    body = response.content.decode()
    lines = body.strip().splitlines()
    header = lines[0]
    assert "name" in header
    assert "num_permits" in header
    assert "permits_per_10k" in header
    assert any("Beverly" in line and ",1," in line for line in lines[1:])


@pytest.mark.django_db
def test_map_data_view_permits_per_10k():
    # 5 permits in an area of 20,000 people is 2.5 per 10k
    CommunityArea.objects.create(name="Beverly", area_id="1", population=20_000)
    for _ in range(5):
        RestaurantPermit.objects.create(
            community_area_id="1", issue_date=date(2021, 1, 15)
        )

    # No population, no per-capita number
    CommunityArea.objects.create(name="Mystery", area_id="2", population=None)

    client = APIClient()
    response = client.get(reverse("map_data", query={"year": 2021}))

    by_name = {row["name"]: row for row in response.data}
    assert by_name["Beverly"]["permits_per_10k"] == 2.5
    assert by_name["Mystery"]["permits_per_10k"] is None
