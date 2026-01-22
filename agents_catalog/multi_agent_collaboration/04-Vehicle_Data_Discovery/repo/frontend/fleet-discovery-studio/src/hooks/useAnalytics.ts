"use client"
import { useState, useEffect } from "react"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

console.log("Analytics Hook - API_BASE_URL:", API_BASE_URL)

export function useAnalytics() {
  const [data, setData] = useState<any>(null)
  const [coverageData, setCoverageData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    console.log("useAnalytics hook - useEffect started")
    console.log("Analytics Hook - API_BASE_URL:", API_BASE_URL)

    async function fetchAnalytics() {
      try {
        console.log("Fetching analytics data from API...")

        const [trendsRes, statsRes, coverageRes] = await Promise.all([
          fetch(`${API_BASE_URL}/stats/trends`),
          fetch(`${API_BASE_URL}/stats/overview`),
          fetch(`${API_BASE_URL}/analytics/coverage-matrix`)
        ])

        console.log(" API Response Status:")
        console.log("- Trends:", trendsRes.status, trendsRes.ok)
        console.log("- Stats:", statsRes.status, statsRes.ok)
        console.log("- Coverage:", coverageRes.status, coverageRes.ok)

        if (!trendsRes.ok) throw new Error(`Trends API failed: ${trendsRes.status}`)
        if (!statsRes.ok) throw new Error(`Stats API failed: ${statsRes.status}`)
        if (!coverageRes.ok) throw new Error(`Coverage API failed: ${coverageRes.status}`)

        const trends = await trendsRes.json()
        const stats = await statsRes.json()
        const coverage = await coverageRes.json()

        console.log(" Analytics data received:")
        console.log("- Trends:", trends)
        console.log("- Stats:", stats)
        console.log("- Coverage:", coverage)

        console.log("Setting state data...")
        setData({ ...trends, ...stats })
        setCoverageData(coverage)
        console.log("State updated successfully")
      } catch (e) {
        console.error(" Analytics fetch failed:", e)
        console.log("Setting fallback data...")
        // Set fallback data to prevent UI crashes
        setData({
          anomalies_by_type: {"Behavioral": 0, "Environmental": 0, "Traffic": 0, "Unknown": 0},
          risk_timeline: [],
          total_scenes_analyzed: 0,
          dto_efficiency_percent: 0
        })
        setCoverageData({
          coverage_matrix: {
            industry_standard_categories: [],
            discovered_categories: [],
            coverage_analysis: {
              total_scenes_analyzed: 0,
              industry_approach: { categories: 0, estimated_coverage: 0 },
              discovered_approach: { categories: 0, actual_coverage: 0 }
            }
          },
          recommendations: {},
          metadata: { analysis_type: "hybrid_odd_coverage" }
        })
        console.log("Fallback data set")
      } finally {
        setLoading(false)
        console.log("Loading state set to false")
      }
    }

    fetchAnalytics()

    // Refresh every 2 minutes
    const interval = setInterval(fetchAnalytics, 120000)
    return () => clearInterval(interval)
  }, [])

  console.log(" useAnalytics hook - Current state:", {
    data: data ? Object.keys(data) : null,
    coverageData: coverageData ? Object.keys(coverageData) : null,
    loading
  })

  return { data, coverageData, loading }
}