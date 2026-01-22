"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { RefreshCw, Grid3X3, List, Brain } from "lucide-react"
import MetricsRibbon from "./MetricsRibbon"
import FilterPills from "./FilterPills"
import SceneCard from "./SceneCard"
import SceneListItem from "./SceneListItem"
import NeuralSearchBar from "./NeuralSearchBar"
import SearchResultsContent from "./SearchResultsContent"
import { useFleetOverview } from "@/hooks/useFleetData"
import { Button } from "@/components/ui/button"

type ViewMode = "grid" | "list"

interface FleetCommandProps {
  initialStats?: any
  initialFleetData?: any
  initialError?: string | null
}

export default function FleetCommand({
  initialStats,
  initialFleetData,
  initialError
}: FleetCommandProps) {
  const router = useRouter()
  const [filter, setFilter] = useState("all")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [page, setPage] = useState(1)

  // Always use hook data for CloudFront deployment (no SSR data)
  const hookData = useFleetOverview(page, 20, filter)
  const data = hookData.data
  const loading = hookData.loading
  const error = hookData.error
  const refetch = hookData.refetch

  // Debug logging for data state
  console.log(" FleetCommand Debug:", {
    filter,
    page,
    hookDataScenes: hookData.data?.scenes?.length || 0,
    finalDataScenes: data?.scenes?.length || 0,
    loading,
    error
  })

  const handleRefresh = () => {
    // Force cache bypass by clearing any existing data and refetching
    console.log(" Force refresh initiated - clearing cache and fetching latest data...")
    refetch()
  }

  const handleSearch = async (query: string) => {
    // Navigate to unified search results page
    const params = new URLSearchParams()
    params.set('q', query)
    router.push(`/search/results?${params.toString()}`)
  }

  const handleClearSearch = () => {
    // No-op since we're navigating away
  }

  // Apple-Grade Dual Routing Logic: Metadata vs Semantic Filtering
  const handleFilterChange = (filterId: string, type: "metadata" | "semantic", query?: string) => {
    setFilter(filterId)
    setPage(1) // Reset to first page when filtering

    if (type === "semantic" && query) {
      // Route to semantic search using S3 Vectors neural search
      console.log(`Neural search triggered for: ${query}`)
      handleSearch(query)
    } else {
      // Route to metadata filtering (instant backend filtering)
      console.log(`Metadata filter applied: ${filterId}`)
      // The setFilter above will trigger useFleetOverview hook to refetch with filter param
      // This provides instant business rule filtering
    }
  }

  // Semantic query mapping for neural triggers (legacy support)
  const getSemanticQuery = (filterId: string): string => {
    const semanticQueries: { [key: string]: string } = {
      construction: "construction zones work sites roadwork construction equipment",
      night: "night driving dark conditions low visibility nighttime",
      weather: "bad weather rain snow fog adverse weather conditions"
    }
    return semanticQueries[filterId] || ""
  }

  return (
    <div className="space-y-6">
      {/* Integrated Header with Neural Search */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-xl flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <motion.h1
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight"
              >
                Fleet Command
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="text-[var(--slate-grey)] mt-1"
              >
                Real-time monitoring & AI-powered scenario discovery
              </motion.p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* View Mode Toggle */}
            <div className="flex bg-[var(--soft-grey)] rounded-lg p-1">
              <Button
                variant={viewMode === "grid" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode("grid")}
                className={`h-8 px-3 ${
                  viewMode === "grid"
                    ? "bg-[var(--cyber-blue)] text-white"
                    : "text-[var(--slate-grey)]"
                }`}
              >
                <Grid3X3 className="w-4 h-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode("list")}
                className={`h-8 px-3 ${
                  viewMode === "list"
                    ? "bg-[var(--cyber-blue)] text-white"
                    : "text-[var(--slate-grey)]"
                }`}
              >
                <List className="w-4 h-4" />
              </Button>
            </div>

            {/* Refresh Button */}
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={loading}
                className="bg-[var(--pure-white)] border-gray-300 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)]"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </motion.div>
          </div>
        </div>

        {/* Neural Search Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex justify-center"
        >
          <NeuralSearchBar
            onSearch={handleSearch}
            onClear={handleClearSearch}
            isSearching={false}
            hasResults={false}
          />
        </motion.div>
      </div>

      {/* Metrics Ribbon */}
      <MetricsRibbon initialStats={initialStats} />

      {/* Filter Pills */}
      <FilterPills activeFilter={filter} onFilterChange={handleFilterChange} />

      {/* Scene Grid/List */}
      {loading && !data ? (
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
      ) : error ? (
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
          <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">
            Unable to load fleet data
          </h3>
          <p className="text-[var(--slate-grey)] mb-4">
            {error}
          </p>
          <Button onClick={handleRefresh} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </motion.div>
      ) : (
        <>
          {/* Results Count */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-between"
          >
            <p className="text-sm text-[var(--slate-grey)]">
              Showing {data?.scenes?.length || 0} of {data?.total_count || 0} scenes
            </p>
            {filter !== "all" && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFilter("all")}
                className="text-[var(--slate-grey)] hover:text-[var(--deep-charcoal)]"
              >
                Clear filters
              </Button>
            )}
          </motion.div>

          {/* Twin Engine Search Results */}
          {viewMode === "grid" ? (
            <SearchResultsContent scenes={data?.scenes || []} isLoading={loading} />
          ) : (
            data?.scenes?.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center py-16"
              >
                <div className="text-[var(--slate-grey)] mb-4">
                  <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">
                  No scenes found
                </h3>
                <p className="text-[var(--slate-grey)] mb-4">
                  {filter !== "all"
                    ? `No scenes match the "${filter.replace('_', ' ')}" filter. Try a different filter or clear all filters.`
                    : "No scenes are currently available."}
                </p>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
                className="space-y-3"
              >
                {data?.scenes?.map((scene: any, index: number) => (
                  <SceneListItem
                    key={scene.scene_id}
                    scene={scene}
                    index={index}
                  />
                ))}
              </motion.div>
            )
          )}

          {/* Pagination - Shows for both Grid and List views */}
          {data && data.total_count >= 20 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex justify-center mt-8"
            >
              <div className="flex items-center gap-3 bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
                <Button
                  variant="outline"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                  className="bg-white border-gray-300 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)]"
                >
                  Previous
                </Button>
                <div className="flex items-center gap-2 px-4">
                  <span className="text-sm text-[var(--slate-grey)]">
                    Page <span className="font-medium text-[var(--deep-charcoal)]">{page}</span> of <span className="font-medium text-[var(--deep-charcoal)]">{Math.ceil(data.total_count / 20)}</span>
                  </span>
                  <div className="text-xs text-[var(--slate-grey)] border-l border-gray-200 pl-2">
                    {data.total_count} total scenes
                  </div>
                </div>
                <Button
                  variant="outline"
                  disabled={page >= Math.ceil(data.total_count / 20)}
                  onClick={() => setPage(page + 1)}
                  className="bg-white border-gray-300 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)]"
                >
                  Next
                </Button>
              </div>
            </motion.div>
          )}


          {/* No Results State */}
          {data?.scenes && data.scenes.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-12"
            >
              <div className="text-[var(--slate-grey)] mb-4">
                <Grid3X3 className="w-12 h-12 mx-auto" />
              </div>
              <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">
                No Scenes Found
              </h3>
              <p className="text-[var(--slate-grey)]">
                No scenes match the current filter criteria.
              </p>
            </motion.div>
          )}
        </>
      )}
    </div>
  )
}