import React, { useEffect, useMemo, useState } from "react"

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet"

import "leaflet/dist/leaflet.css"

import RAW_COMMUNITY_AREAS from "../../../data/raw/community-areas.geojson"

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
  const communityAreaColors = ["#eff3ff", "#bdd7e7", "#6baed6", "#2171b5"]

  const [currentYearData, setCurrentYearData] = useState([])
  const [year, setYear] = useState(2026)

  useEffect(() => {
    fetch(`/map-data/?year=${year}`)
      .then((res) => res.json())
      .then((rows) => setCurrentYearData(rows))
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

  function getColor(percentageOfPermits) {
    if (percentageOfPermits > 0.75) return communityAreaColors[3]
    if (percentageOfPermits > 0.5) return communityAreaColors[2]
    if (percentageOfPermits > 0.25) return communityAreaColors[1]
    return communityAreaColors[0]
  }

  function setAreaInteraction(feature, layer) {
    const areaId = feature.properties.area_numbe
    const count = countsById.get(String(areaId)) || 0
    const pct = maxNumPermits > 0 ? count / maxNumPermits : 0

    layer.setStyle({
      fillColor: getColor(pct),
      fillOpacity: 0.75,
      weight: 1,
      color: "#666",
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
      <MapContainer id="restaurant-map" center={[41.88, -87.62]} zoom={10}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"
        />
        {currentYearData.length > 0 ? (
          <GeoJSON
            data={RAW_COMMUNITY_AREAS}
            onEachFeature={setAreaInteraction}
            key={maxNumPermits}
          />
        ) : null}
      </MapContainer>
    </>
  )
}
