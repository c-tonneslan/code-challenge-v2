import React, { useEffect, useMemo, useState } from "react"

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet"

import "leaflet/dist/leaflet.css"

import RAW_COMMUNITY_AREAS from "../../../data/raw/community-areas.geojson"

const COMMUNITY_AREA_COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#2171b5"]

// Render the per-capita number with one decimal when small, no decimal otherwise.
function formatPerCapita(n) {
  if (n == null) return "n/a"
  return n < 10 ? n.toFixed(1) : Math.round(n).toString()
}

function Legend({ max, unitLabel, format }) {
  if (!max) return null
  // Walk the four shades and spell out the range each one represents for
  // the current view, so a viewer can read the map without hovering every
  // shape.
  const bands = COMMUNITY_AREA_COLORS.map((color, i) => {
    const upper = ((i + 1) / COMMUNITY_AREA_COLORS.length) * max
    const lower = i === 0 ? 0 : (i / COMMUNITY_AREA_COLORS.length) * max
    return { color, label: `${format(lower)} – ${format(upper)}` }
  })
  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mb-3 small">
      <span className="text-muted">{unitLabel}:</span>
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

function MetricToggle({ mode, setMode }) {
  return (
    <div className="btn-group mb-3" role="group" aria-label="Metric">
      <button
        type="button"
        className={`btn btn-outline-primary ${mode === "count" ? "active" : ""}`}
        onClick={() => setMode("count")}
      >
        Raw permit count
      </button>
      <button
        type="button"
        className={`btn btn-outline-primary ${mode === "per_capita" ? "active" : ""}`}
        onClick={() => setMode("per_capita")}
      >
        Per 10k residents
      </button>
    </div>
  )
}

export default function RestaurantPermitMap() {
  const [currentYearData, setCurrentYearData] = useState([])
  const [year, setYear] = useState(2026)
  const [mode, setMode] = useState("count")
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    fetch(`/map-data/?year=${year}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`map-data returned ${res.status}`)
        return res.json()
      })
      .then((rows) => setCurrentYearData(rows))
      .catch((err) => {
        if (err.name === "AbortError") return
        setError(err.message)
      })
    return () => controller.abort()
  }, [year])

  // The current metric, as a function. Keeps the rest of the component
  // metric-agnostic.
  const metric = (row) =>
    mode === "per_capita" ? row.permits_per_10k : row.num_permits

  const rowsById = useMemo(() => {
    const map = new Map()
    for (const row of currentYearData) {
      map.set(String(row.area_id), row)
    }
    return map
  }, [currentYearData])

  const totalPermits = useMemo(
    () => currentYearData.reduce((sum, row) => sum + row.num_permits, 0),
    [currentYearData]
  )

  const maxValue = useMemo(() => {
    let m = 0
    for (const row of currentYearData) {
      const v = metric(row)
      if (v != null && v > m) m = v
    }
    return m
  }, [currentYearData, mode])

  const topAreas = useMemo(() => {
    return [...currentYearData]
      .filter((row) => {
        const v = metric(row)
        return v != null && v > 0
      })
      .sort((a, b) => metric(b) - metric(a))
      .slice(0, 5)
  }, [currentYearData, mode])

  function getColor(ratio) {
    if (ratio > 0.75) return COMMUNITY_AREA_COLORS[3]
    if (ratio > 0.5) return COMMUNITY_AREA_COLORS[2]
    if (ratio > 0.25) return COMMUNITY_AREA_COLORS[1]
    return COMMUNITY_AREA_COLORS[0]
  }

  function setAreaInteraction(feature, layer) {
    const areaId = feature.properties.area_numbe
    const row = rowsById.get(String(areaId))
    const name = row ? row.name : feature.properties.community
    const value = row ? metric(row) : null
    const ratio = maxValue > 0 && value != null ? value / maxValue : 0

    layer.setStyle({
      fillColor: value == null ? "#eee" : getColor(ratio),
      fillOpacity: value == null ? 0.4 : 0.75,
      weight: 1,
      color: "#666",
    })

    const popupLine =
      mode === "per_capita"
        ? value == null
          ? "no population data"
          : `${formatPerCapita(value)} permits per 10k residents`
        : `${value || 0} permit${value === 1 ? "" : "s"}`
    layer.bindPopup(`<strong>${name}</strong><br/>${popupLine} in ${year}`)

    layer.on("mouseover", () => {
      layer.setStyle({ weight: 2, color: "#222" })
      layer.openPopup()
    })
    layer.on("mouseout", () => {
      layer.setStyle({ weight: 1, color: "#666" })
      layer.closePopup()
    })
  }

  const headlineMetric =
    mode === "per_capita"
      ? `${formatPerCapita(maxValue)} permits per 10k`
      : `${maxValue.toLocaleString()} permits`

  return (
    <>
      <YearSelect year={year} setYear={setYear} />
      <MetricToggle mode={mode} setMode={setMode} />

      <p className="fs-4">
        Restaurant permits issued this year:{" "}
        <strong>{totalPermits.toLocaleString()}</strong>
      </p>
      <p className="fs-4">
        Highest in a single area: <strong>{headlineMetric}</strong>
      </p>

      <Legend
        max={maxValue}
        unitLabel={mode === "per_capita" ? "Permits per 10k" : "Permits issued"}
        format={mode === "per_capita" ? formatPerCapita : (n) => Math.round(n).toString()}
      />

      {error && (
        <p className="text-danger small">
          Couldn&apos;t load map data: {error}
        </p>
      )}

      <MapContainer id="restaurant-map" center={[41.88, -87.62]} zoom={10}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"
        />
        {currentYearData.length > 0 ? (
          <GeoJSON
            data={RAW_COMMUNITY_AREAS}
            onEachFeature={setAreaInteraction}
            key={`${year}-${mode}-${maxValue}`}
          />
        ) : null}
      </MapContainer>

      {topAreas.length > 0 && (
        <div className="mt-4">
          <h2 className="fs-3">
            {mode === "per_capita"
              ? `Most permits per resident in ${year}`
              : `Most permits in ${year}`}
          </h2>
          <ol className="fs-5">
            {topAreas.map((row) => (
              <li key={row.area_id}>
                {row.name}
                <span className="text-muted">
                  {" "}
                  ({mode === "per_capita"
                    ? `${formatPerCapita(row.permits_per_10k)} per 10k`
                    : row.num_permits.toLocaleString()}
                  )
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </>
  )
}
