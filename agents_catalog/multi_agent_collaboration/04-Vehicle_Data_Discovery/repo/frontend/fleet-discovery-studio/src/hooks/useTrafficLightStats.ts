"use client"

import { useState, useEffect } from "react"

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
        console.log("Fetching traffic light stats from:", `${API_BASE_URL}/stats/traffic-light`)
        const response = await fetch(`${API_BASE_URL}/stats/traffic-light`)
        console.log(" Traffic light response:", response.status, response.ok)
        if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch traffic light stats`)
        const data = await response.json()
        console.log("Traffic light data:", data)
        setStats(data)
      } catch (err) {
        console.error(" Traffic light stats fetch error:", err)
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