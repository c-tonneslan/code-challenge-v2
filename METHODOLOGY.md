# Methodology

Short notes on where the data comes from, how it gets joined, and what it does and doesn't tell you. Worth a skim before drawing conclusions from the map.

## Data sources

**Restaurant permits.** Sourced from the City of Chicago's Business Affairs and Consumer Protection permit dataset, filtered to restaurant license categories. Each row carries an issue date and the community area number assigned at application time. The CSV that ships in `data/raw/chicago-restaurants.csv` is a snapshot, not a live pull, so the map reflects the period covered by that file.

**Community area boundaries.** The 77 community areas defined by the University of Chicago's Social Science Research Committee in the 1920s, plus O'Hare and Edgewater added later. The GeoJSON in `data/raw/community-areas.geojson` is the same shapefile the City and CMAP publish. Each feature carries a `community` (name) and `area_numbe` (1–77).

**Population.** From the City of Chicago's `t68z-cikk` dataset, "ACS 5 Year Data by Community Area," 2023 vintage. The City rolls up tract-level American Community Survey estimates into community-area totals, which is the same number you'd get pulling tract-level ACS via DataMade's `census` library and summing by tract-to-community-area assignment. We use the pre-rolled-up version because it removes the need for a Census API key and a tract crosswalk.

## How the join works

`RestaurantPermit.community_area_id` is a `CharField` (the CSV ships the number as a string like `"17"`). `CommunityArea.area_id` is an `IntegerField`. The view aggregates permits with one `GROUP BY community_area_id` query and the serializer matches by `str(area.area_id)` against the dict key. The frontend joins API rows to the GeoJSON features on `area_numbe` (string) against `area_id` (number, coerced to string).

If a permit row has a `community_area_id` that doesn't match any CommunityArea (junk data, area number outside 1–77), it falls through the join and is silently excluded from the per-area count. The yearly total in the UI still includes it, but it won't show up under any neighborhood. This is intentional, not a bug; the alternative is making up an "Unknown" community area, which would mislead the choropleth.

## How the per-capita number is computed

`permits_per_10k = round(num_permits / population * 10_000, 2)`, where `num_permits` is for the selected year and `population` is the 2023 ACS 5-year estimate. We don't year-match the population to the permit year, both because the 2023 5-year estimate already pools 2019–2023 and because community-area populations are stable enough year over year that the comparison would be noise. If the area is missing a population row, the serializer returns `null` and the map renders the area in a light gray with an "n/a" popup.

## What this map does not tell you

- **Closures aren't visible.** A permit is issued, not retired, so a neighborhood with churn shows as active even if half those restaurants closed by year-end. The next iteration could join the city's business-closure dataset.
- **The permit `permit_type` is not broken out.** A new-issuance permit and a renewal are both counted equally. A future view could split renewals from openings, which would change the story for stable neighborhoods.
- **Geocoding accuracy varies.** A handful of permits in the raw CSV have invalid lat/long and were skipped at load time. The loader logs them. They contribute zero to all per-area counts.
- **2026 is partial.** The dataset is filtered to issue-year buckets, so 2026 only contains permits issued up to the snapshot date.
- **Per-capita has a denominator problem in non-residential areas.** The Loop community area is ~30k residents but has hundreds of restaurants, because almost no one lives there. The per-capita view will rank the Loop very high; that's not a bug, it's a property of the metric. If you want a workplace-normalized version, the right denominator is daytime population, not residential.

## Reproducing the data load

```bash
docker compose run --rm app python manage.py loaddata \
  map/fixtures/community_areas.json \
  map/fixtures/restaurant_permits.json

docker compose run --rm app python manage.py load_community_area_population \
  data/raw/community_area_population_acs2023.csv
```

The population CSV was pulled with:

```bash
curl -sL "https://data.cityofchicago.org/resource/t68z-cikk.csv?\$select=community_area,total_population&\$where=acs_year='2023'&\$limit=100" \
  > data/raw/community_area_population_acs2023.csv
```

So it's reproducible from the same Socrata endpoint without any setup.
