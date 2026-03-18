/**
 * Search Page - Semantic Search Interface
 * 
 * Landing page for semantic search with example queries
 * and search input. Redirects to /search/results with query.
 * 
 * @route /search
 */
"use client"

import { useState, useRef, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import DashboardLayout from "@/components/layout/DashboardLayout"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Search,
  Brain,
  Zap,
  ArrowRight,
  X,
  Lightbulb,
  Clock
} from "lucide-react"

const EXAMPLE_QUERIES = [
  "Car running a red light",
  "Pedestrian jaywalking",
  "Emergency vehicle approaching",
  "Construction zone navigation",
  "Night driving with rain",
  "Aggressive lane changing",
  "Vehicle following too closely",
  "Intersection with poor visibility"
]

export default function SearchPage() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [isFocused, setIsFocused] = useState(false)
  const [searchHistory] = useState<string[]>([]) // Placeholder for search history
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Focus on search input when page loads
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  const handleSearch = async (searchQuery?: string) => {
    const queryToSearch = searchQuery || query
    if (queryToSearch.trim()) {
      // Navigate to unified search results page
      const params = new URLSearchParams()
      params.set('q', queryToSearch.trim())
      router.push(`/search/results?${params.toString()}`)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch()
    }
    if (e.key === "Escape") {
      setQuery("")
      inputRef.current?.blur()
    }
  }

  const handleExampleClick = (exampleQuery: string) => {
    setQuery(exampleQuery)
    handleSearch(exampleQuery)
  }

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery)
    handleSearch(historyQuery)
  }

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Search Header */}
        <div className="text-center space-y-6">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-r from-[var(--cyber-blue)] to-[var(--cyber-blue)]/70 rounded-xl flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-3xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
                Neural Search
              </h1>
            </div>
            <p className="text-lg text-[var(--slate-grey)] max-w-2xl mx-auto leading-relaxed">
              Semantic search across your entire fleet dataset using AI-powered scene understanding.
              Find driving scenarios using natural language descriptions.
            </p>
          </motion.div>

          {/* Omni-Bar */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="relative max-w-3xl mx-auto"
          >
            <Card
              className={`
                relative overflow-hidden bg-white/70 backdrop-blur-xl border-0 shadow-2xl
                transition-all duration-500 ease-out
                ${isFocused
                  ? "ring-2 ring-[var(--cyber-blue)]/50 shadow-[0_20px_40px_-12px_rgba(0,122,255,0.25)]"
                  : "shadow-[0_10px_30px_-10px_rgba(0,0,0,0.1)]"
                }
              `}
            >
              <div className="relative flex items-center">
                <div className="absolute left-6 z-10">
                  <Search className="w-6 h-6 text-[var(--slate-grey)]" />
                </div>

                <Input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Describe the driving scenario you're looking for..."
                  className="w-full h-16 pl-16 pr-32 text-lg bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-[var(--slate-grey)]/60"
                />

                <div className="absolute right-4 flex items-center gap-2">
                  {query && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      onClick={() => setQuery("")}
                      className="w-8 h-8 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
                    >
                      <X className="w-4 h-4 text-[var(--slate-grey)]" />
                    </motion.button>
                  )}

                  <Button
                    onClick={() => handleSearch()}
                    disabled={!query.trim()}
                    className="h-10 px-6 bg-[var(--cyber-blue)] hover:bg-[var(--cyber-blue)]/90"
                  >
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4" />
                      Search
                    </div>
                  </Button>
                </div>

                {/* Animated border */}
                {isFocused && (
                  <motion.div
                    layoutId="searchBorder"
                    className="absolute inset-0 rounded-lg border-2 border-[var(--cyber-blue)]/30"
                    initial={false}
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
              </div>

              {/* Search suggestions dropdown */}
              <AnimatePresence>
                {isFocused && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="absolute top-full left-0 right-0 mt-2 p-4 bg-white/90 backdrop-blur-xl border border-gray-200/50 rounded-lg shadow-xl z-50"
                  >
                    {/* Recent searches */}
                    {searchHistory.length > 0 && (
                      <div className="mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Clock className="w-4 h-4 text-[var(--slate-grey)]" />
                          <span className="text-sm font-medium text-[var(--slate-grey)]">
                            Recent Searches
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {searchHistory.slice(0, 3).map((historyQuery, index) => (
                            <button
                              key={index}
                              onClick={() => handleHistoryClick(historyQuery)}
                              className="text-sm bg-[var(--soft-grey)] hover:bg-gray-200 text-[var(--slate-grey)] px-3 py-1 rounded-full transition-colors"
                            >
                              {historyQuery}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Example queries */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Lightbulb className="w-4 h-4 text-[var(--slate-grey)]" />
                        <span className="text-sm font-medium text-[var(--slate-grey)]">
                          Try These Examples
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {EXAMPLE_QUERIES.slice(0, 6).map((example, index) => (
                          <button
                            key={index}
                            onClick={() => handleExampleClick(example)}
                            className="flex items-center justify-between p-2 text-sm text-left bg-[var(--soft-grey)] hover:bg-[var(--cyber-blue)]/10 hover:text-[var(--cyber-blue)] rounded-lg transition-all duration-200 group"
                          >
                            <span>{example}</span>
                            <ArrowRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </button>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>
          </motion.div>
        </div>

        {/* Search Instructions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="text-center max-w-2xl mx-auto"
        >
          <Card className="p-8 bg-gradient-to-r from-[var(--cyber-blue)]/5 to-[var(--cyber-blue)]/10 border-[var(--cyber-blue)]/20">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-[var(--cyber-blue)]/20 rounded-xl flex items-center justify-center flex-shrink-0">
                <Brain className="w-5 h-5 text-[var(--cyber-blue)]" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-[var(--deep-charcoal)] mb-2">
                  How Neural Search Works
                </h3>
                <div className="space-y-2 text-sm text-[var(--slate-grey)]">
                  <p>
                    <strong>Semantic Understanding:</strong> Our AI converts your natural language query into a mathematical representation (vector) using Cohere embed-v4 and Cosmos visual embeddings.
                  </p>
                  <p>
                    <strong>Meaning-Based Matching:</strong> Instead of keyword matching, we find scenes with similar behavioral patterns and contexts.
                  </p>
                  <p>
                    <strong>Similarity Scoring:</strong> Results show percentage matches based on semantic similarity: <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">similarity_score = 1.0 - cosine_distance</code>
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </DashboardLayout>
  )
}