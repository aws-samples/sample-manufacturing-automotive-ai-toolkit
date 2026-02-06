/**
 * useFleetData - Fleet data fetching hooks
 * 
 * Provides hooks for fetching fleet statistics and scene overview data
 * with pagination and filtering support.
 * 
 * Exports:
 * - useFleetStats() - Fetch aggregate fleet statistics
 * - useFleetOverview(page, limit, filter) - Fetch paginated scene list
 * 
 * @example
 * // Get fleet stats
 * const { stats, loading, error } = useFleetStats()
 * 
 * // Get paginated scenes with filtering
 * const { data, loading, refetch } = useFleetOverview(1, 20, "anomaly")
 * 
 * API Endpoints:
 * - GET /stats/overview - Fleet statistics
 * - GET /fleet/overview?page=1&limit=20&filter=all - Paginated scenes
 */
"use client"

import { useState, useEffect } from "react"

interface FleetStats {
  scenarios_processed: number
  anomalies_detected: number
  dto_savings_usd: number
  status: string
}

interface SceneData {
  scene_id: string
  timestamp: string
  risk_score: number
  anomaly_status: string // "NORMAL" or "ANOMALY"
  hil_priority: string // "LOW", "MEDIUM", "HIGH"
  description_preview: string
  tags: string[]
  confidence_score: number
  // Required fields for UI components
  video_url: string
  thumbnail_url: string
  safety_score: number
  camera_angles: string[]
  analysis_summary: string
  anomaly_detected: boolean
}

interface FleetOverview {
  scenes: SceneData[]
  total_count: number
  page: number
  limit: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export function useFleetStats() {
  const [stats, setStats] = useState<FleetStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch(`${API_BASE_URL}/stats/overview`)
        if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch stats`)
        const data = await response.json()
        setStats(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  return { stats, loading, error }
}

export function useFleetOverview(page = 1, limit = 20, filter = "all") {
  const [data, setData] = useState<FleetOverview | null>(null)
  const [allScenes, setAllScenes] = useState<SceneData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchOverview(forceRefresh = false) {
      try {
        setLoading(true)
        // Backend now supports pagination
        let url = `${API_BASE_URL}/fleet/overview`
        const params = new URLSearchParams()
        params.set('page', page.toString())
        params.set('limit', limit.toString())

        if (filter !== "all") {
          params.set('filter', filter)
        }

        // Add cache-busting timestamp for force refresh
        if (forceRefresh) {
          params.set('_t', Date.now().toString())
        }

        url += `?${params.toString()}`

        const response = await fetch(url)

        if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch fleet overview`)
        const paginationResponse = await response.json()

        // Handle new pagination structure
        const scenesArray = paginationResponse.scenes || paginationResponse || []
        const totalCount = paginationResponse.total_count || scenesArray.length
        const totalPages = paginationResponse.total_pages || 1


interface ApiScene {
  scene_id: string
  description_preview?: string
  anomaly_status?: string
  risk_score?: number
  timestamp?: string
  hil_priority?: string
  tags?: string[]
  confidence_score?: number
}

        // Transform API response to expected format
        const transformedScenes = scenesArray.map((scene: ApiScene) => ({
          ...scene,
          // Add compatibility fields for existing UI components
          analysis_summary: scene.description_preview,
          anomaly_detected: scene.anomaly_status === "ANOMALY",
          safety_score: scene.risk_score,
          camera_angles: ["CAM_FRONT", "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"],
          // Required fields for SceneCard component
          video_url: `${API_BASE_URL}/scene/${scene.scene_id}/video`,
          thumbnail_url: `${API_BASE_URL}/scene/${scene.scene_id}/thumbnail`
        }))

        // Use server-side pagination directly (no client-side slicing needed)
        const serverPaginatedData = {
          scenes: transformedScenes,
          total_count: totalCount,
          page: paginationResponse.page || 1,
          limit: paginationResponse.limit || limit,
          total_pages: totalPages
        }

        setData(serverPaginatedData)
        setAllScenes(transformedScenes) // Keep for compatibility
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }

  useEffect(() => {
    fetchOverview()
  }, [filter, page, limit])

  return {
    data,
    loading,
    error,
    refetch: () => fetchOverview(true) // Always force refresh when manually triggered
  }
}