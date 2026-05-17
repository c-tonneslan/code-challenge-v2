import React, { useEffect, useMemo, useState } from "react"

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet"

import "leaflet/dist/leaflet.css"

import RAW_COMMUNITY_AREAS from "../../../data/raw/community-areas.geojson"

const COMMUNITY_AREA_COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#2171b5"]

function Legend({ maxNumPermits }) {
  if (!maxNumPermits) return null
  // Walk the four shades and spell out the permit-count range each one
  // represents for the current year, so a viewer can read the map without
  // having to hover every shape.
  const bands = COMMUNITY_AREA_COLORS.map((color, i) => {
    const upper = Math.round(((i + 1) / COMMUNITY_AREA_COLORS.length) * maxNumPermits)
    const lower =
      i === 0 ? 0 : Math.round((i / COMMUNITY_AREA_COLORS.length) * maxNumPermits) + 1
    return { color, label: lower === upper ? `${upper}` : `${lower}–${upper}` }
  })
  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mb-3 small">
      <span className="text-muted">Permits issued:</span>
      {bands.map(({ color, label }) => (
        <span key={color} className="d-inline-flex align-items-center gap-1">
          <span
            style={{
              width: 16,
              height: 16,
              background: color,
              border: "1px solid #999",
              display: "inline-block",
            }}
          />
          <span>{label}</span>
        </span>
      ))}
    </div>
  )
}

function YearSelect({ year, setYear }) {
  // Filter by the permit issue year for each restaurant
  const startYear = 2026
  const years = [...Array(11).keys()].map((i) => startYear - i)

  return (
    <>
      <label htmlFor="yearSelect" className="fs-3">
        Filter by year:{" "}
      </label>
      <select
        id="yearSelect"
        className="form-select form-select-lg mb-3"
        value={year}
        onChange={(e) => setYear(Number(e.target.value))}
      >
        {years.map((y) => (
          <option value={y} key={y}>
            {y}
          </option>
        ))}
      </select>
    </>
  )
}

export default function RestaurantPermitMap() {
  const [currentYearData, setCurrentYearData] = useState([])
  const [year, setYear] = useState(2026)

  useEffect(() => {
    const controller = new AbortController()
    fetch(`/map-data/?year=${year}`, { signal: controller.signal })
      .then((res) => res.json())
      .then((rows) => setCurrentYearData(rows))
      .catch((err) => {
        if (err.name !== "AbortError") throw err
      })
    return () => controller.abort()
  }, [year])

  const countsById = useMemo(() => {
    const map = new Map()
    for (const row of currentYearData) {
      map.set(String(row.area_id), row.num_permits)
    }
    return map
  }, [currentYearData])

  const totalPermits = useMemo(
    () => currentYearData.reduce((sum, row) => sum + row.num_permits, 0),
    [currentYearData]
  )

  const maxNumPermits = useMemo(
    () => currentYearData.reduce((m, row) => Math.max(m, row.num_permits), 0),
    [currentYearData]
  )

  const topAreas = useMemo(() => {
    return [...currentYearData]
      .filter((row) => row.num_permits > 0)
      .sort((a, b) => b.num_permits - a.num_permits)
      .slice(0, 5)
  }, [currentYearData])

  function getColor(percentageOfPermits) {
    if (percentageOfPermits > 0.75) return COMMUNITY_AREA_COLORS[3]
    if (percentageOfPermits > 0.5) return COMMUNITY_AREA_COLORS[2]
    if (percentageOfPermits > 0.25) return COMMUNITY_AREA_COLORS[1]
    return COMMUNITY_AREA_COLORS[0]
  }

  function setAreaInteraction(feature, layer) {
    const areaId = feature.properties.area_numbe
    const name = feature.properties.community
    const count = countsById.get(String(areaId)) || 0
    const pct = maxNumPermits > 0 ? count / maxNumPermits : 0

    layer.setStyle({
      fillColor: getColor(pct),
      fillOpacity: 0.75,
      weight: 1,
      color: "#666",
    })

    layer.bindPopup(
      `<strong>${name}</strong><br/>${count} permit${count === 1 ? "" : "s"} in ${year}`
    )
    layer.on("mouseover", () => {
      layer.setStyle({ weight: 2, color: "#222" })
      layer.openPopup()
    })
    layer.on("mouseout", () => {
      layer.setStyle({ weight: 1, color: "#666" })
      layer.closePopup()
    })
  }

  return (
    <>
      <YearSelect year={year} setYear={setYear} />
      <p className="fs-4">
        Restaurant permits issued this year: <strong>{totalPermits.toLocaleString()}</strong>
      </p>
      <p className="fs-4">
        Maximum number of restaurant permits in a single area:{" "}
        <strong>{maxNumPermits.toLocaleString()}</strong>
      </p>

      <Legend maxNumPermits={maxNumPermits} />

      <MapContainer id="restaurant-map" center={[41.88, -87.62]} zoom={10}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"
        />
        {currentYearData.length > 0 ? (
          <GeoJSON
            data={RAW_COMMUNITY_AREAS}
            onEachFeature={setAreaInteraction}
            key={`${year}-${maxNumPermits}`}
          />
        ) : null}
      </MapContainer>

      {topAreas.length > 0 && (
        <div className="mt-4">
          <h2 className="fs-3">Most permits in {year}</h2>
          <ol className="fs-5">
            {topAreas.map((row) => (
              <li key={row.area_id}>
                {row.name.replace(/\b\w/g, (c) => c.toUpperCase())}
                <span className="text-muted">
                  {" "}({row.num_permits.toLocaleString()})
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </>
  )
}
