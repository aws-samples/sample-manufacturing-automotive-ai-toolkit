/**
 * useAnalytics - Analytics data fetching hook
 * 
 * Fetches aggregated analytics data including risk trends, coverage metrics,
 * and DTO efficiency statistics from multiple API endpoints.
 * 
 * @returns {Object} Analytics state
 * @returns {AnalyticsData | null} data - Combined trends and stats data
 * @returns {CoverageData | null} coverageData - ODD coverage matrix data
 * @returns {boolean} loading - Loading state
 * 
 * @example
 * const { data, coverageData, loading } = useAnalytics()
 * 
 * API Endpoints:
 * - GET /stats/trends - Risk timeline data
 * - GET /stats/overview - Fleet statistics
 * - GET /analytics/coverage-matrix - ODD coverage analysis
 */
"use client"
import { useState, useEffect } from "react"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

interface AnalyticsData {
  risk_timeline?: Array<{ date: string; risk_score?: number; scene_id?: string }>
  anomalies_by_type?: Record<string, number>
  total_scenes_analyzed?: number
  scenarios_processed?: number
  dto_efficiency_percent?: number
  anomalies_detected?: number
  [key: string]: unknown
}

interface CoverageData {
  coverage_matrix?: {
    industry_standard_categories?: CoverageCategory[]
    discovered_categories?: CoverageCategory[]
    coverage_analysis?: Record<string, unknown>
  }
  [key: string]: unknown
}

interface CoverageCategory {
  category: string
  description?: string
  type?: string
  status?: string
  hil_priority?: string
  risk_adaptive_target?: number
  actual_scenes?: number
  current?: number
  target?: number
  average_risk_score?: number
  uniqueness_score?: number
  percentage?: number
}

export function useAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [coverageData, setCoverageData] = useState<CoverageData | null>(null)
  const [loading, setLoading] = useState(true)

  async function fetchAnalytics(cacheBust = false) {
    try {
      const cacheBustParam = cacheBust ? `?_t=${Date.now()}` : ''

      const [trendsRes, statsRes, coverageRes] = await Promise.all([
        fetch(`${API_BASE_URL}/stats/trends${cacheBustParam}`),
        fetch(`${API_BASE_URL}/stats/overview${cacheBustParam}`),
        fetch(`${API_BASE_URL}/analytics/coverage-matrix${cacheBustParam}`)
      ])

      if (!trendsRes.ok) throw new Error(`Trends API failed: ${trendsRes.status}`)
      if (!statsRes.ok) throw new Error(`Stats API failed: ${statsRes.status}`)
      if (!coverageRes.ok) throw new Error(`Coverage API failed: ${coverageRes.status}`)

      const trends = await trendsRes.json()
      const stats = await statsRes.json()
      const coverage = await coverageRes.json()

      setData({ ...trends, ...stats })
      setCoverageData(coverage)
    } catch {
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
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalytics()

    // Refresh every 2 minutes
    const interval = setInterval(() => fetchAnalytics(), 120000)
    return () => clearInterval(interval)
  }, [])

  // Refetch function for manual refresh (with cache-busting)
  const refetch = async () => {
    setLoading(true)
    await fetchAnalytics(true)
  }

  return { data, coverageData, loading, refetch }
}