"use client"

import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"

export type FilterType = "metadata" | "semantic"

interface FilterOption {
  id: string
  label: string
  type: FilterType
  query?: string // For semantic search
}

interface FilterPillsProps {
  activeFilter: string
  onFilterChange: (filterId: string, type: FilterType, query?: string) => void
}

// Apple-Grade Grouped Filter Design
const FILTER_GROUPS: Record<string, FilterOption[]> = {
  "🚦 Anomaly Analysis": [
    { id: "critical", label: "🔴 Critical", type: "metadata" },
    { id: "deviation", label: "🟡 Deviation", type: "metadata" },
    { id: "normal", label: "🟢 Normal", type: "metadata" },
  ],
  "🎯 HIL Strategy": [
    { id: "hil_high", label: "🔥 High Value", type: "metadata" },
    { id: "hil_medium", label: "⚡ Medium Value", type: "metadata" },
    { id: "hil_low", label: "📊 Low Value", type: "metadata" },
  ],
  "🔍 Neural Triggers": [
    { id: "construction", label: "🚧 Construction", type: "semantic", query: "construction zones work sites roadwork construction equipment" },
    { id: "night", label: "🌙 Night Ops", type: "semantic", query: "night driving dark conditions low visibility nighttime" },
    { id: "weather", label: "🌧️ Weather", type: "semantic", query: "bad weather rain snow fog adverse weather conditions" },
  ]
}

export default function FilterPills({ activeFilter, onFilterChange }: FilterPillsProps) {
  return (
    <div className="space-y-4 mb-6">
      {/* All Scenes Filter (Special Case) */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-[var(--deep-charcoal)] mr-2">
          Filter:
        </span>
        <motion.button
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onFilterChange("all", "metadata")}
          className="relative"
        >
          <Badge
            variant={activeFilter === "all" ? "default" : "outline"}
            className={`
              px-4 py-2 text-sm font-medium cursor-pointer transition-all duration-200
              ${activeFilter === "all"
                ? 'bg-[var(--cyber-blue)] text-white border-[var(--cyber-blue)] shadow-lg'
                : 'bg-[var(--pure-white)] text-[var(--slate-grey)] border-gray-300 hover:bg-[var(--soft-grey)]'
              }
            `}
          >
            All Scenes
          </Badge>
        </motion.button>
      </div>

      {/* Grouped Filters */}
      <div className="flex gap-8 overflow-x-auto pb-2 no-scrollbar">
        {Object.entries(FILTER_GROUPS).map(([groupName, options], groupIndex) => (
          <div key={groupName} className="flex items-center gap-3 border-r border-gray-200 pr-6 last:border-0">
            {/* Group Label */}
            <span className="text-xs font-bold text-[var(--slate-grey)] uppercase tracking-wider whitespace-nowrap">
              {groupName}
            </span>

            {/* Group Options */}
            <div className="flex gap-2">
              {options.map((option, index) => {
                const isActive = activeFilter === option.id

                return (
                  <motion.button
                    key={option.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: (groupIndex * 0.1) + (index * 0.05) }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => onFilterChange(option.id, option.type, option.query)}
                    className={`
                      px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 whitespace-nowrap
                      ${isActive
                        ? "bg-[var(--deep-charcoal)] text-white shadow-md"
                        : "bg-[var(--pure-white)] text-[var(--slate-grey)] hover:bg-[var(--soft-grey)] border border-gray-200"}
                    `}
                  >
                    {option.label}
                  </motion.button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}