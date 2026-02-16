/**
 * SearchResultsContent - Full Search Results Page Content
 * 
 * Handles search execution, result filtering, deduplication, and display.
 * Supports both text-based and visual similarity search modes.
 */
"use client"

import { useEffect, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { Brain, Search, ArrowLeft, Sparkles, Layers } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import NeuralSearchBar from "@/components/fleet/NeuralSearchBar"
import SceneCard from "@/components/fleet/SceneCard"
import { useSearch } from "@/hooks/useSearch"

interface CameraInfo {
  camera: string
  score?: number
}

interface SearchResult {
  scene_id: string
  score?: number
  description?: string
  input_type?: string
  cameras?: CameraInfo[]
  is_verified?: boolean
  engines?: string[]
}

export default function SearchResultsContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const query = searchParams?.get('q') || ''

  const { results, loading, error, search } = useSearch()
  const [hasSearched, setHasSearched] = useState(false)

  // Execute search when component loads with query parameter
  useEffect(() => {
    const query = searchParams?.get('q')
    const mode = searchParams?.get('mode')
    const refScene = searchParams?.get('ref')


    if (!hasSearched) {
      // LOGIC BRANCH 1: Visual Search (Scene-to-Scene)
      if (refScene && mode === 'visual') {
        search("", { mode: 'visual', sceneId: refScene })
        setHasSearched(true)
      } 
      // LOGIC BRANCH 2: Text Search (Twin Engine)
      else if (query) {
        search(query, { mode: 'behavioral' })
        setHasSearched(true)
      }
    }
  }, [searchParams, hasSearched, search])

  const handleNewSearch = async (newQuery: string) => {
    // Update URL with new query
    const params = new URLSearchParams()
    params.set('q', newQuery)
    router.push(`/search/results?${params.toString()}`)

    // Execute search
    await search(newQuery)
    setHasSearched(true)
  }

  const handleBackToFleet = () => {
    router.push('/')
  }

  // Filter and deduplicate results for best UX
  // Lowered from 0.4 to 0.1 - semantic search scores of 10-20% are meaningful matches
  const SIMILARITY_THRESHOLD = 0.1
  const allResults = results?.results || []

  // First filter by similarity threshold
  const relevantResults = allResults.filter(result => {
    const similarity = result.score || 0
    return similarity >= SIMILARITY_THRESHOLD
  })

  // Then deduplicate by scene_id, keeping the highest scoring result per scene
  const deduplicatedMap = new Map()
  relevantResults.forEach(result => {
    const existingResult = deduplicatedMap.get(result.scene_id)
    const currentSimilarity = result.score || 0
    const existingSimilarity = existingResult?.score || 0

    if (!existingResult || currentSimilarity > existingSimilarity) {
      deduplicatedMap.set(result.scene_id, result)
    }
  })

  const searchResults = Array.from(deduplicatedMap.values()).sort((a, b) => {
    const aScore = a.score || 0
    const bScore = b.score || 0
    return bScore - aScore // Sort by similarity descending
  })

  const totalResults = searchResults.length
  const filteredCount = allResults.length - relevantResults.length
  const deduplicatedCount = relevantResults.length - searchResults.length

  // Transform search results to match SceneCard component data structure
  const transformedResults = searchResults.map(result => {
    // Extract camera information from the new camera-aware search results
    const cameras = result.cameras || []
    const primaryCamera = cameras.length > 0 ? cameras[0] : null
    const cameraNames = cameras.map((c: CameraInfo) => c.camera).join(", ") || "CAM_FRONT"

    // Generate camera badge text for display
    const cameraInfo = cameras.length > 1
      ? `${cameras.length} cameras`
      : cameras.length === 1
        ? cameras[0].camera.replace('CAM_', '').toLowerCase()
        : 'front cam'

    return {
      scene_id: result.scene_id,
      timestamp: new Date().toISOString(), // Use current time as placeholder
      video_url: "",
      thumbnail_url: "",
      // Generate reasonable risk score based on similarity (higher similarity = lower risk for most scenarios)
      risk_score: Math.max(0.1, 1 - (result.score || 0.5)),
      safety_score: result.score || 0.5,
      tags: [
        ...(result.input_type ? [result.input_type.replace('_', ' ').toLowerCase()] : ['semantic match']),
        cameraInfo // Add camera info as a tag
      ],
      camera_angles: cameras.length > 0
        ? cameras.map((c: CameraInfo) => c.camera)
        : ["CAM_FRONT", "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_BACK_RIGHT"],
      analysis_summary: result.description ?
        result.description.substring(0, 100) + (result.description.length > 100 ? '...' : '') :
        `Semantic match for scene ${result.scene_id}${cameras.length > 0 ? ` (${cameraNames})` : ''}`,
      anomaly_detected: (result.score || 0) > 0.6,
      hil_qualification: {
        level: ((result.score || 0) > 0.5 ? "HIGH" : (result.score || 0) > 0.4 ? "MEDIUM" : "LOW") as "HIGH" | "MEDIUM" | "LOW",
        anomaly_detected: (result.score || 0) > 0.5,
        reason: `Semantic match score: ${Math.round((result.score || 0) * 100)}%`
      },
      // Add search-specific data for similarity badge
      similarity_score: result.score,
      relevance_score: result.score, // for backward compatibility
      // Add tiered UI fields
      is_verified: result.is_verified || false,
      engines: result.engines || [],
      highlight: result.is_verified ? "gold" : undefined,
      // Camera-aware navigation data (NEW)
      cameras: cameras, // Pass through camera data for SceneCard navigation
      primary_camera: primaryCamera?.camera, // Don't force fallback - undefined if no camera data
      primary_video_uri: primaryCamera?.video_uri || ''
    }
  })

  // Separate verified and non-verified results for tiered display
  const verifiedResults = transformedResults.filter(scene => scene.is_verified || scene.highlight === "gold")
  const additionalResults = transformedResults.filter(scene => !scene.is_verified && scene.highlight !== "gold")

  return (
    <div className="space-y-6">
      {/* Header with Back Button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={handleBackToFleet}
            className="bg-[var(--pure-white)] border-gray-300 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)]"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Fleet
          </Button>

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-xl flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <motion.h1
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight"
              >
                Neural Search Results
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="text-[var(--slate-grey)] mt-1"
              >
                AI-powered semantic scenario discovery
              </motion.p>
            </div>
          </div>
        </div>

        <Badge variant="outline" className="bg-[var(--cyber-blue)]/10 text-[var(--cyber-blue)] border-[var(--cyber-blue)]/20">
          {totalResults} matches found
        </Badge>
      </div>

      {/* Search Bar */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex justify-center"
      >
        <NeuralSearchBar
          onSearch={handleNewSearch}
          onClear={() => router.push('/')}
          isSearching={loading}
          hasResults={totalResults > 0}
        />
      </motion.div>

      {/* Current Search Query Display */}
      {query && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <p className="text-sm text-[var(--slate-grey)]">
            Searching for: <span className="font-medium text-[var(--deep-charcoal)]">&quot;{query}&quot;</span>
          </p>
        </motion.div>
      )}


      {/* Loading State */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="bg-[var(--soft-grey)] aspect-video rounded-t-lg"></div>
              <div className="bg-[var(--pure-white)] border border-gray-200 rounded-b-lg p-4 space-y-3">
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                <div className="h-2 bg-gray-200 rounded w-full"></div>
                <div className="flex gap-2">
                  <div className="h-5 bg-gray-200 rounded w-16"></div>
                  <div className="h-5 bg-gray-200 rounded w-12"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-12"
        >
          <div className="text-[var(--error-red)] mb-4">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">Search Error</h3>
          <p className="text-[var(--slate-grey)] mb-4">{error}</p>
          <Button onClick={() => search(query)} variant="outline">
            <Search className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </motion.div>
      )}

      {/* Tiered Search Results */}
      {!loading && !error && transformedResults.length > 0 && (
        <div className="space-y-8">
          {/* Search Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-between"
          >
            <p className="text-sm text-[var(--slate-grey)]">
              Showing {totalResults} semantic matches{results?.search_time ? ` in ${results.search_time.toFixed(2)}s` : ''}
              {results?.engines_active && ` • Twin Engine Active`}
            </p>
          </motion.div>

          {/* Verified Matches Section */}
          {verifiedResults.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-50 to-amber-100/50 border border-amber-200/50 rounded-xl backdrop-blur-sm">
                  <Sparkles className="w-5 h-5 text-amber-600" />
                  <h2 className="text-lg font-semibold text-amber-800">High Confidence Results</h2>
                  <span className="px-2 py-1 bg-amber-200/50 text-amber-700 text-xs font-medium rounded-full">
                    {verifiedResults.length}
                  </span>
                </div>
              </div>

              <motion.div
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                {verifiedResults.map((scene, index) => (
                  <motion.div
                    key={`verified-${scene.scene_id}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{
                      duration: 0.6, // Slower for premium feel
                      delay: index * 0.1,
                      type: "spring",
                      stiffness: 80
                    }}
                  >
                    <div className="relative">
                      <SceneCard scene={scene} index={index} />
                      {/* Twin Match Badge */}
                      <div className="absolute top-3 left-3 z-20">
                        <Badge className="bg-gradient-to-r from-amber-500 to-amber-600 border-0 text-white text-xs font-medium shadow-lg">
                          <Layers className="w-3 h-3 mr-1" />
                          AI Consensus
                        </Badge>
                      </div>
                      {/* Similarity Score Badge */}
                      <div className="absolute top-3 right-3 z-20">
                        <Badge className="bg-[var(--cyber-blue)] border-0 text-white text-xs font-medium shadow-lg">
                          {Math.round((scene.similarity_score || 0) * 100)}%
                        </Badge>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            </motion.div>
          )}

          {/* Additional Discoveries Section */}
          {additionalResults.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: verifiedResults.length > 0 ? 0.3 : 0 }}
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl">
                  <Layers className="w-5 h-5 text-gray-600" />
                  <h2 className="text-lg font-semibold text-gray-700">Additional Discoveries</h2>
                  <span className="px-2 py-1 bg-gray-200/50 text-gray-600 text-xs font-medium rounded-full">
                    {additionalResults.length}
                  </span>
                </div>
              </div>

              <motion.div
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                {additionalResults.map((scene, index) => (
                  <motion.div
                    key={`additional-${scene.scene_id}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{
                      duration: 0.4,
                      delay: index * 0.05,
                      type: "spring",
                      stiffness: 100
                    }}
                  >
                    <div className="relative">
                      <SceneCard scene={scene} index={index} />
                      {/* Similarity Score Badge */}
                      <div className="absolute top-3 right-3 z-20">
                        <Badge className="bg-[var(--cyber-blue)] border-0 text-white text-xs font-medium shadow-lg">
                          {Math.round((scene.similarity_score || 0) * 100)}% match
                        </Badge>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            </motion.div>
          )}
        </div>
      )}

      {/* No Results State */}
      {!loading && !error && hasSearched && transformedResults.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-12"
        >
          <div className="text-[var(--slate-grey)] mb-4">
            <Search className="w-12 h-12 mx-auto" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">No Matches Found</h3>
          <p className="text-[var(--slate-grey)] mb-6">
            No scenes semantically match &quot;{query}&quot;. Try rephrasing your search or using more general terms.
          </p>

          {/* Example searches */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-[var(--deep-charcoal)]">Try these example searches:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                "urban driving",
                "pedestrian crossing",
                "construction zone",
                "rainy weather",
                "emergency braking"
              ].map((example) => (
                <Button
                  key={example}
                  variant="outline"
                  size="sm"
                  onClick={() => handleNewSearch(example)}
                  className="text-xs"
                >
                  <Sparkles className="w-3 h-3 mr-1" />
                  {example}
                </Button>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}