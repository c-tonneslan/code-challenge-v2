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
