/**
 * NeuralSearchBar - Semantic Search Input
 * 
 * Search input with AI-powered suggestions and visual feedback.
 * Triggers semantic search on submit, navigates to results page.
 */
"use client"

import { Search, Sparkles, X } from "lucide-react"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

interface NeuralSearchBarProps {
  onSearch: (query: string) => void
  onClear: () => void
  isSearching: boolean
  hasResults: boolean
}

export default function NeuralSearchBar({ onSearch, onClear, isSearching, hasResults }: NeuralSearchBarProps) {
  const [query, setQuery] = useState("")
  const [isFocused, setIsFocused] = useState(false)

  const handleSearch = () => {
    if (query.trim()) {
      // Twin Engine: Backend automatically runs both Cohere + Cosmos
      onSearch(query.trim())
    }
  }

  const handleClear = () => {
    setQuery("")
    onClear()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch()
    }
    if (e.key === "Escape") {
      handleClear()
    }
  }

  return (
    <div className="relative max-w-2xl w-full group">
      {/* Magical Glow Effect */}
      <div className={`absolute inset-0 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-xl opacity-0 blur-xl transition-opacity duration-300 ${
        isFocused ? 'opacity-20' : 'opacity-10'
      }`} />

      {/* Search Container */}
      <div className={`relative bg-white rounded-xl shadow-lg flex items-center p-2 border transition-all duration-300 ${
        isFocused
          ? 'border-[var(--cyber-blue)]/50 shadow-[0_20px_40px_-12px_rgba(0,122,255,0.25)]'
          : 'border-gray-100 shadow-[var(--shadow-card)]'
      }`}>

        {/* Search Icon */}
        <div className="ml-3 flex-shrink-0">
          {isSearching ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            >
              <Sparkles className="w-5 h-5 text-[var(--cyber-blue)]" />
            </motion.div>
          ) : (
            <Search className="w-5 h-5 text-[var(--slate-grey)]" />
          )}
        </div>

        {/* Input Field */}
        <input
          className="flex-1 p-3 outline-none text-[var(--deep-charcoal)] placeholder:text-[var(--slate-grey)]/60 bg-transparent"
          placeholder="Describe a scenario (e.g., 'Construction zone at night with pedestrians')..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          disabled={isSearching}
        />

        {/* Action Buttons */}
        <div className="flex items-center gap-2 mr-2">
          {/* Clear Button */}
          <AnimatePresence>
            {(query || hasResults) && (
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                onClick={handleClear}
                className="w-8 h-8 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors"
              >
                <X className="w-4 h-4 text-[var(--slate-grey)]" />
              </motion.button>
            )}
          </AnimatePresence>

          {/* Search Button */}
          <motion.button
            onClick={handleSearch}
            disabled={!query.trim() || isSearching}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="px-4 py-2 bg-[var(--deep-charcoal)] text-white rounded-lg hover:bg-[var(--deep-charcoal)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2"
          >
            {isSearching ? (
              <>
                <Sparkles className="w-4 h-4" />
                <span className="text-sm">Searching...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span className="text-sm">Search</span>
              </>
            )}
          </motion.button>
        </div>
      </div>

      {/* Search Status Indicator - Removed to prevent UI overlap */}
    </div>
  )
}