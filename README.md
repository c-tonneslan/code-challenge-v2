# DataMade Code Challenge: React Map

> ## Solution by Charlie Tonneslan
>
> This is my completion of DataMade's public code challenge. I'm not in an application window right now, I just wanted to do the work because civic data tooling is the kind of thing I want to build. The original brief is below, unchanged.
>
> **What I did**
>
> The challenge ships skeletons in `map/serializers.py`, `map/views.py`, `map/static/js/RestaurantPermitMap.js`, and `tests/test_views.py`. I filled them in and pushed iteratively, so the commit log walks through the work:
>
> - Implemented `get_num_permits` first as a per-area filter inside the serializer. Realized that was 77 SELECTs per map load and refactored: the view runs one `GROUP BY` query and hands the serializer a `{community_area_id: count}` dict to look up.
> - Filled in the existing test, then added two more cases (no-year request, area with zero permits) plus a different-year permit in the original test so the year filter is actually exercised.
> - Wired the React component end-to-end. Year filter, fetch on change, choropleth shaded by quartile of the year's max, total + max above the map, hover popup with the area name and count.
> - Hit two bugs while clicking around: same-max years didn't re-style (the GeoJSON layer is keyed on `maxNumPermits`, which was stable across some year switches — fixed by keying on `${year}-${maxNumPermits}`), and fast year-changes were letting stale fetches race the new one — fixed with `AbortController` on cleanup.
> - Added polish that turns the map into something readable on its own: a legend that spells out the permit-count range for each shade, a top-5 list under the map, and a visible error message when `/map-data/` fails instead of swallowing.
>
> **Files changed:** `map/serializers.py`, `map/views.py`, `map/static/js/RestaurantPermitMap.js`, `tests/test_views.py`, `README.md`.
>
> After the basics worked I went further:
>
> - Added a `population` column on `CommunityArea`, a loader, and a CSV of 2023 5-year ACS totals per community area (sourced from the City of Chicago's `t68z-cikk` dataset). The API now returns `permits_per_10k` alongside the raw count.
> - Added a toggle on the page between raw counts and per-capita. Per-capita re-ranks the map: Lincoln Park and Loop drop, smaller dense neighborhoods rise.
> - Composite index on `(issue_date, community_area_id)` so the aggregate runs as a bitmap index scan instead of seq scan. Before/after `EXPLAIN ANALYZE` in the commit body.
> - `/map-data/?year=2021&format=csv` returns the same rows as CSV, for journalists who want the dataset without a JSON parser.
> - Break the per-area count out by `permit_type`. The popup now shows the top two categories under the count, so a heavy-renovation neighborhood reads different from a heavy-new-construction one.
> - Title-cased the community area names at load time (with manual overrides for O'Hare and McKinley Park). Used to be a regex in the React component.
> - Loading and empty-state messages so a year outside the dataset's range doesn't render a blank map without an explanation.
> - Wrote [`METHODOLOGY.md`](METHODOLOGY.md) covering sources, joins, the per-capita formula, and what the map *doesn't* see (closures, permit type, denominator quirks like the Loop's daytime-population problem).
>
> **Running the tests:** `docker compose -f docker-compose.yml -f tests/docker-compose.yml run --rm app` &rarr; `6 passed`.
>
> **Loading the data:**
>
> ```bash
> docker compose run --rm app python manage.py loaddata \
>   map/fixtures/community_areas.json map/fixtures/restaurant_permits.json
> docker compose run --rm app python manage.py load_community_area_population \
>   data/raw/community_area_population_acs2023.csv
> ```

---

![2026 DataMade Code Challenge](https://github.com/datamade/code-challenge-v2/blob/main/map/static/images/2026-datamade-code-challenge.jpg)

Welcome to the 2026 DataMade code challenge! 👋

## Overview

Your task is to complete the following programming exercise to show us some of your code! This exercise is based on work that DataMade does every day: pulling data from the web, debugging tricky code, and presenting information to the world.

Submissions should be submitted as a pull request against your fork of this original repository. **Make sure to make your pull request against your own fork of the repository, not the original DataMade repository**.

There’s no time limit, but don’t feel the need to go over the top with your submission. We expect this task to take about two hours to complete, but it could take more or less time depending on your familiarity with Django and React. When you’re all set, share your code with us as a repository on GitHub.

We’ll be evaluating whether the code works, as well as its quality. Before submitting, make sure that your code does what you expect it to do, that it’s clean and neat enough to meet your standards, and that you’ve provided us some instructions on how to run it.

## Installation

Development requires a local installation of [Docker](https://docs.docker.com/get-started/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/). These are the only two system-level dependencies you should need.

Once you have Docker and Docker Compose installed, build the application containers from the project's root directory:

```bash
docker compose build
```

Load in the data:

```bash
docker compose run --rm app python manage.py loaddata map/fixtures/restaurant_permits.json map/fixtures/community_areas.json
```

And finally, run the app:

```bash
docker compose up
```

The app will log to the console, and you should be able to visit it at http://localhost:8000

## Completing the Challenge

Once you have the app up and running on your computer, you'll need to flesh out certain code blocks to make the map functional. You'll be using [Django](https://docs.djangoproject.com/en/6.0/) and [React-Leaflet](https://react-leaflet.js.org/docs/api-components/) to complete this task. By the end of this challenge, you should have:

- a map that displays Chicago's community areas, shaded depending on how many new restaurant permits were issued in a given year
- community area shapes that show some light details on that community area when a user interacts with them
- a filter that allows users to request permits that were issued in a given year
- UI components that display the total number of permits and max number of permits in one community area for that year

This way you go about completing these goals is meant to be open-ended, so tackle the following steps in whatever way you're most comfortable!

### Step 1: Supplement the community area geojson data

In `map/serializers.py`, supplement each community area with data on the amount of permits issued in each area during the currently filtered year. From here, the view will pass that data to the front end.

### Step 2: Write a test for your data endpoint

In `tests/test_views.py` implement a test to validate the data that your endpoint produces. You will want to create some test `CommunityArea` and `RestaurantPermit` objects and then assert that the expected values are returned when querying the endpoint.

Use this command to run tests:

```bash
 docker compose -f docker-compose.yml -f tests/docker-compose.yml run --rm app
```

### Step 3: Filter results by a specific year

In `map/static/js/RestaurantPermitMap.js`, create a filter that allows users to send a request for a specific year to the backend. The options shoulds be any year between 2016 and 2026, inclusive. Then, use the fetch api in the map component to make a request and receive that data.

### Step 4: Display results on the page

In the map component, process the community area and use it to display shapes for all areas on the map. Then, display the total number of restaurant permits that year as well as the maximum number of permits in any one area.

### Step 5: Make the map dynamic

Start displaying some data! Use the `setAreaInteraction()` method to shade the map according to how many permits it has in a year, making sure that it updates automatically when a new year is selected. In this same method, have each area display a popup during some kind of user interaction. The popup should have some light details to help the user understand what they're looking at.

### Step 6: Submit your work

To submit your work, create a feature branch for your code, commit your changes, push your commits up to your fork, and open up a pull request against main. Finally, drop a link to your pull request in your application.

_Note: If you would prefer to keep your code challenge private, please share access with the following members of DataMade on GitHub:_

| Member    | GitHub Account                   |
| --------- | -------------------------------- |
| Hannah    | https://github.com/hancush       |
| Derek     | https://github.com/derekeder     |
| Monkruman | https://github.com/antidipyramid |
| Xavier    | https://github.com/xmedr         |
| Hayley    | https://github.com/haowens       |

Keep in mind that you cannot create a private fork of a public repository on GitHub, so you’ll need to [follow these instructions](https://gist.github.com/0xjac/85097472043b697ab57ba1b1c7530274) to create a private copy of the repo.