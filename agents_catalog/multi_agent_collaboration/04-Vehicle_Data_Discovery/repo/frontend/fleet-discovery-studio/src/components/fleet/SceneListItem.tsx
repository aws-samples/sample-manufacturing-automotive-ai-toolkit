"use client"

import { motion } from "framer-motion"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import InfoTooltip from "@/components/ui/InfoTooltip"
import { getMetricDefinition } from "@/lib/metricDefinitions"
import {
  Calendar,
  Camera,
  AlertTriangle,
  Target,
  Brain,
  ChevronRight
} from "lucide-react"

interface SceneListItemProps {
  scene: {
    scene_id: string
    timestamp?: string
    risk_score?: number
    safety_score?: number
    tags?: string[]
    camera_angles?: string[]
    analysis_summary?: string
    anomaly_detected?: boolean
    anomaly_status?: 'CRITICAL' | 'DEVIATION' | 'NORMAL'
    hil_qualification?: {
      level: "HIGH" | "MEDIUM" | "LOW"
      anomaly_detected: boolean
      reason: string
    }
    // Search-specific fields
    similarity_score?: number
    relevance_score?: number
    description?: string
  }
  index: number
}

export default function SceneListItem({ scene, index }: SceneListItemProps) {
  const getRiskColor = (score: number) => {
    if (score >= 0.7) return "var(--safety-orange)"
    if (score >= 0.4) return "var(--warning-amber)"
    return "var(--success-green)"
  }

  const formatDate = (timestamp?: string) => {
    if (!timestamp) return "Unknown date"
    const date = new Date(timestamp)
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    const month = months[date.getUTCMonth()]
    const day = date.getUTCDate()
    const hours = date.getUTCHours().toString().padStart(2, '0')
    const minutes = date.getUTCMinutes().toString().padStart(2, '0')

    return `${month} ${day}, ${hours}:${minutes}`
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        duration: 0.3,
        delay: index * 0.02,
      }}
      whileHover={{ x: 4, transition: { duration: 0.2 } }}
      className="group"
    >
      <Link href={`/forensic?id=${scene.scene_id}`}>
        <Card className="p-4 border-0 shadow-sm hover:shadow-md transition-all duration-300 bg-white">
          <div className="flex items-center gap-4">
            {/* Scene ID and Metadata */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <h3 className="font-mono text-sm font-medium text-[var(--deep-charcoal)]">
                  {scene.scene_id}
                </h3>

                {/* Apple-Grade 3-Tier Status */}
                {scene.anomaly_status === "CRITICAL" && (
                  <Badge className="bg-red-500/90 border-0 text-white text-xs animate-pulse">
                    🔴 CRITICAL
                  </Badge>
                )}
                {scene.anomaly_status === "DEVIATION" && (
                  <Badge className="bg-amber-500/90 border-0 text-white text-xs">
                    🟡 DEVIATION
                  </Badge>
                )}
                {scene.anomaly_status === "NORMAL" && (
                  <Badge className="bg-emerald-500/90 border-0 text-white text-xs">
                    🟢 NORMAL
                  </Badge>
                )}

                {/* HIL Badge */}
                {scene.hil_qualification && scene.hil_qualification.level !== "LOW" && (
                  <Badge
                    variant="outline"
                    className={`border-0 text-white font-medium text-xs ${
                      scene.hil_qualification.level === "HIGH"
                        ? "bg-[var(--safety-orange)]"
                        : "bg-[var(--warning-amber)]"
                    }`}
                  >
                    {scene.hil_qualification.level === "HIGH" ? (
                      <>🔥 High Value</>
                    ) : (
                      <>⚡ Medium Value</>
                    )}
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-4 text-xs text-[var(--slate-grey)]">
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(scene.timestamp)}
                </div>

                {scene.camera_angles && (
                  <div className="flex items-center gap-1">
                    <Camera className="w-3 h-3" />
                    {scene.camera_angles.length} cameras
                  </div>
                )}
              </div>
            </div>

            {/* Risk Score */}
            {scene.risk_score !== undefined && (
              <div className="flex items-center gap-2 min-w-0">
                <div className="text-right">
                  <div className="flex items-center gap-1 text-xs text-[var(--slate-grey)] mb-1">
                    <span>Risk Score</span>
                    <InfoTooltip
                      title={getMetricDefinition('risk_score')?.title || 'Risk Score'}
                      description={getMetricDefinition('risk_score')?.description || 'Overall safety risk assessment'}
                      calculation={getMetricDefinition('risk_score')?.calculation}
                      size="sm"
                      position="auto"
                    />
                  </div>
                  <div className="text-lg font-bold" style={{ color: getRiskColor(scene.risk_score) }}>
                    {(scene.risk_score * 100).toFixed(0)}
                  </div>
                </div>
                <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${scene.risk_score * 100}%` }}
                    transition={{ duration: 0.8, delay: index * 0.02 }}
                    className="h-full rounded-full"
                    style={{ backgroundColor: getRiskColor(scene.risk_score) }}
                  />
                </div>
              </div>
            )}

            {/* Tags */}
            <div className="flex flex-wrap gap-1 max-w-xs min-w-0">
              {(scene.tags || []).slice(0, 2).map((tag, i) => (
                <span
                  key={i}
                  className="text-[10px] px-2 py-1 bg-gray-50 text-gray-500 rounded-md font-medium border border-gray-100 truncate"
                >
                  {tag}
                </span>
              ))}
            </div>

            {/* HIL Reasoning (if available) */}
            {scene.hil_qualification && scene.hil_qualification.level !== "LOW" && (
              <div className="flex items-center gap-1 text-[10px] text-[var(--slate-grey)] max-w-xs min-w-0">
                <Brain className="w-3 h-3 opacity-60 flex-shrink-0" />
                <span className="font-medium opacity-80 truncate">
                  {scene.hil_qualification.reason}
                </span>
              </div>
            )}

            {/* Arrow */}
            <div className="flex-shrink-0">
              <ChevronRight className="w-4 h-4 text-[var(--slate-grey)] opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
            </div>
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}