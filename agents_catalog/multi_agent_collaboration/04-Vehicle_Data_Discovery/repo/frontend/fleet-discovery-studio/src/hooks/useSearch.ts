"use client"

import { useState } from "react"

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
  metadata?: any          // S3 vectors metadata

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
    console.log('🔍 useSearch - search function called with:', { query, options })
    
    if (!query.trim() && !options?.sceneId) {
      console.log('❌ useSearch - early return: no query or sceneId')
      setResults(null)
      setError(null)
      return
    }

    try {
      console.log('🚀 useSearch - starting search...')
      setLoading(true)
      setError(null)

      // Construct the Twin Engine payload
      const payload = {
        query: query || undefined,
        limit: 12,
        index_type: options?.mode || 'behavioral',
        scene_id: options?.sceneId
      }

      console.log('📦 useSearch - API payload:', payload)
      console.log('🌐 useSearch - API_BASE_URL:', API_BASE_URL)
      console.log('🎯 useSearch - Full URL:', `${API_BASE_URL}/search`)

      console.log('📡 useSearch - About to make fetch request...')
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })

      console.log('📨 useSearch - Response received:', {
        status: response.status,
        ok: response.ok,
        statusText: response.statusText,
        url: response.url
      })

      if (!response.ok) {
        console.error('❌ useSearch - Response not OK')
        throw new Error(`Search failed: ${response.statusText}`)
      }

      console.log('📄 useSearch - Parsing JSON...')
      const data: SearchResponse = await response.json()
      console.log('✅ useSearch - Data parsed successfully:', {
        query: data.query,
        resultsCount: data.results?.length || 0,
        enginesActive: data.engines_active,
        hasError: !!data.error
      })
      
      setResults(data)

      // Only add to history if it's a text search
      if (query && !options?.sceneId) {
        console.log('📚 useSearch - Adding to history')
        setSearchHistory(prev => {
          const newHistory = [query, ...prev.filter(q => q !== query)]
          return newHistory.slice(0, 10)
        })
      }

    } catch (err) {
      console.error('💥 useSearch - Error caught:', err)
      console.error('💥 useSearch - Error type:', typeof err)
      console.error('💥 useSearch - Error message:', err instanceof Error ? err.message : String(err))
      setError(err instanceof Error ? err.message : "Search failed")
    } finally {
      console.log('🏁 useSearch - Finally block, setting loading false')
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