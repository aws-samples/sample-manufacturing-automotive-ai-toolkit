/**
 * SceneGrid - Grid Display for Scene Cards
 * 
 * Renders scenes as a responsive grid of SceneCards with optional
 * verified/unverified grouping for search results.
 * 
 * @param scenes - Array of scene data to display
 * @param isLoading - Loading state to show placeholder
 */
"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import { Sparkles, Layers } from "lucide-react"
import SceneCard from "./SceneCard"

interface SceneResult {
  scene_id: string
  is_verified?: boolean
  highlight?: string
  timestamp?: string
  risk_score?: number
  anomaly_status?: string
  hil_priority?: string
  description_preview?: string
  tags?: string[]
  confidence_score?: number
  video_url?: string
  thumbnail_url?: string
  safety_score?: number
  camera_angles?: string[]
  analysis_summary?: string
  anomaly_detected?: boolean
}

interface SceneGridProps {
  scenes: SceneResult[]
  isLoading: boolean
}

export default function SceneGrid({ scenes, isLoading }: SceneGridProps) {
  // Separate verified and non-verified results
  const verifiedScenes = useMemo(
    () => scenes.filter(scene => scene.is_verified || scene.highlight === "gold"),
    [scenes]
  )
  const additionalScenes = useMemo(
    () => scenes.filter(scene => !scene.is_verified && scene.highlight !== "gold"),
    [scenes]
  )

  if (isLoading) return null

  return (
    <div className="space-y-8">
      {/* Verified Matches Section */}
      {verifiedScenes.length > 0 && (
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
                {verifiedScenes.length}
              </span>
            </div>
          </div>
          
          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            {verifiedScenes.map((scene, index) => (
              <motion.div
                key={scene.scene_id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{
                  duration: 0.6, // Slower for premium feel
                  delay: index * 0.1,
                  type: "spring",
                  stiffness: 80
                }}
              >
                <SceneCard scene={scene} index={index} />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      )}

      {/* Additional Discoveries Section */}
      {additionalScenes.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: verifiedScenes.length > 0 ? 0.3 : 0 }}
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl">
              <Layers className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-700">Additional Discoveries</h2>
              <span className="px-2 py-1 bg-gray-200/50 text-gray-600 text-xs font-medium rounded-full">
                {additionalScenes.length}
              </span>
            </div>
          </div>
          
          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            {additionalScenes.map((scene, index) => (
              <motion.div
                key={scene.scene_id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{
                  duration: 0.4,
                  delay: index * 0.05,
                  type: "spring",
                  stiffness: 100
                }}
              >
                <SceneCard scene={scene} index={index} />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      )}

      {/* Empty State */}
      {scenes.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-16"
        >
          <div className="text-gray-400 mb-4">
            <Sparkles className="w-16 h-16 mx-auto" />
          </div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">
            No matching scenarios found
          </h3>
          <p className="text-gray-500">
            Try adjusting your search terms or explore different scenarios.
          </p>
        </motion.div>
      )}
    </div>
  )
}
