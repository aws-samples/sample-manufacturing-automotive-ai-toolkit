"use client"

import { useState, useEffect } from "react"

interface OddCategory {
  category: string
  description: string
  total_scenes: number
  estimated_unique_scenes: number
  uniqueness_score: number
  redundancy_ratio: number
  uniqueness_quality: "excellent" | "good" | "moderate" | "poor"
  dto_value_estimate: number
  similarity_distribution: {
    high_similarity_count: number
    medium_similarity_count: number
    low_similarity_count: number
  }
}

interface OddDiscoveryData {
  analysis_method: string
  analysis_timestamp: string
  total_categories_analyzed: number
  total_scenes_analyzed: number
  total_unique_scenes_estimated: number
  overall_uniqueness_ratio: number
  overall_redundancy_ratio: number
  dto_cost_per_scene: number
  dto_savings_estimate: {
    naive_cost_usd: number
    intelligent_cost_usd: number
    estimated_savings_usd: number
    efficiency_gain_percent: number
  }
  uniqueness_results: OddCategory[]
  analysis_quality: "high" | "medium" | "low"
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export function useOddDiscovery() {
  const [data, setData] = useState<OddDiscoveryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchOddDiscoveryData() {
      try {
        console.log("🧠 Fetching ODD discovery data from:", `${API_BASE_URL}/analytics/odd-uniqueness-analysis`)
        const response = await fetch(`${API_BASE_URL}/analytics/odd-uniqueness-analysis`)
        console.log(" ODD discovery response:", response.status, response.ok)

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: Failed to fetch ODD discovery data`)
        }

        const oddData = await response.json()
        console.log("🧠 ODD discovery data:", oddData)
        setData(oddData)
      } catch (err) {
        console.error("ODD discovery fetch error:", err)
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }

    fetchOddDiscoveryData()
    // Refresh every 5 minutes for updated analysis
    const interval = setInterval(fetchOddDiscoveryData, 300000)
    return () => clearInterval(interval)
  }, [])

  return { data, loading, error }
}

export type { OddCategory, OddDiscoveryData }