/**
 * useTrafficLightStats - Scene risk distribution hook
 * 
 * Fetches traffic-light style risk categorization (critical/warning/normal)
 * for the fleet's driving scenes.
 * 
 * @returns {Object} Traffic light stats state
 * @returns {TrafficLightStats | null} stats - Risk distribution counts
 * @returns {boolean} loading - Loading state
 * @returns {string | null} error - Error message if fetch failed
 * 
 * @example
 * const { stats, loading } = useTrafficLightStats()
 * if (stats) {
 *   console.log(`Critical: ${stats.critical.count}`)
 *   console.log(`Warning: ${stats.warning.count}`)
 *   console.log(`Normal: ${stats.normal.count}`)
 * }
 * 
 * API Endpoint:
 * - GET /stats/traffic-light
 */
"use client"

import { useState, useEffect } from "react"
import { authenticatedFetch } from "@/lib/api"

interface TrafficLightStats {
  total_scenes: number
  critical: {
    count: number
    percentage: number
  }
  deviation: {
    count: number
    percentage: number
  }
  normal: {
    count: number
    percentage: number
  }
  status: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export function useTrafficLightStats() {
  const [stats, setStats] = useState<TrafficLightStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchTrafficLightStats() {
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/stats/traffic-light`)
        if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch traffic light stats`)
        const data = await response.json()
        setStats(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }

    fetchTrafficLightStats()
    // Refresh every 30 seconds for live updates
    const interval = setInterval(fetchTrafficLightStats, 30000)
    return () => clearInterval(interval)
  }, [])

  return { stats, loading, error }
}