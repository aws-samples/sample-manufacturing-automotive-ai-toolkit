/**
 * useSearch - Semantic search hook
 * 
 * Provides semantic search over driving scenes using text queries
 * or visual similarity (scene-to-scene matching).
 * 
 * @returns {Object} Search state and methods
 * @returns {SearchResponse | null} results - Search results with scores
 * @returns {boolean} loading - Search in progress
 * @returns {string | null} error - Error message if search failed
 * @returns {Function} search - Execute search (query, options)
 * @returns {Function} clearResults - Clear current results
 * @returns {string[]} searchHistory - Recent search queries
 * 
 * @example
 * const { results, loading, search } = useSearch()
 * 
 * // Text search
 * search("pedestrian crossing at night")
 * 
 * // Visual similarity search
 * search("", { mode: "visual", sceneId: "scene-0001" })
 * 
 * API Endpoint:
 * - POST /search { query, mode, scene_id }
 */
"use client"

import { useState } from "react"
import { authenticatedFetch } from "@/lib/api"

interface SearchResult {
  scene_id: string
  similarity_score: number  // Keep for backward compatibility
  score: number            // New: unified score from backend
  description: string
  input_type: string

  // Twin Engine fields
  engines: string[]        // ["behavioral"] or ["visual"] or ["behavioral", "visual"]
  matches: string[]        // ["Concept Match"] or ["Visual Pattern"] or both
  is_verified: boolean     // true when found by both engines
  metadata?: Record<string, unknown>  // S3 vectors metadata

  // Camera-aware search fields (NEW)
  cameras?: Array<{
    camera: string         // e.g., "CAM_FRONT", "CAM_LEFT", etc.
    score: number         // Individual camera match score
    video_uri: string     // S3 URI for specific camera video
  }>

  // Optional fields for compatibility with SceneCard
  timestamp?: string
  video_url?: string
  thumbnail_url?: string
  risk_score?: number
  safety_score?: number
  tags?: string[]
  analysis_summary?: string
  anomaly_detected?: boolean
  relevance_score?: number // For backward compatibility
}

interface SearchResponse {
  query: string
  results: SearchResult[]
  engines_active: string[] // ["behavioral", "visual"] from backend
  total_results: number
  search_time?: number
  semantic_insights?: {
    query_interpretation: string
    key_concepts: string[]
    search_strategy?: string
  }
  error?: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export function useSearch() {
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchHistory, setSearchHistory] = useState<string[]>([])

  const search = async (query: string, options?: { mode?: 'visual' | 'behavioral', sceneId?: string }) => {
    
    if (!query.trim() && !options?.sceneId) {
      setResults(null)
      setError(null)
      return
    }

    try {
      setLoading(true)
      setError(null)

      // Construct the Twin Engine payload
      const payload = {
        query: query || undefined,
        limit: 12,
        index_type: options?.mode || 'behavioral',
        scene_id: options?.sceneId
      }


      const response = await authenticatedFetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`)
      }

      const data: SearchResponse = await response.json()
      
      setResults(data)

      // Only add to history if it's a text search
      if (query && !options?.sceneId) {
        setSearchHistory(prev => {
          const newHistory = [query, ...prev.filter(q => q !== query)]
          return newHistory.slice(0, 10)
        })
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed")
    } finally {
      setLoading(false)
    }
  }

  const clearResults = () => {
    setResults(null)
    setError(null)
  }

  const clearHistory = () => {
    setSearchHistory([])
  }

  return {
    results,
    loading,
    error,
    searchHistory,
    search,
    clearResults,
    clearHistory
  }
}