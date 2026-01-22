"use client"

import { motion } from "framer-motion"
import Link from "next/link"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import InfoTooltip from "@/components/ui/InfoTooltip"
import { getMetricDefinition } from "@/lib/metricDefinitions"
import {
  Calendar,
  Camera,
  AlertTriangle,
  Play,
  Target,
  Eye,
  TrendingUp,
  Brain,
  Layers,
  ChevronDown,
  ChevronRight
} from "lucide-react"

interface SceneCardProps {
  scene: {
    scene_id: string
    timestamp?: string
    video_url?: string
    thumbnail_url?: string
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
    score?: number
    relevance_score?: number
    description?: string
    // Twin Engine fields
    engines?: string[]
    matches?: string[]
    is_verified?: boolean
    // Camera-aware navigation fields (NEW)
    cameras?: Array<{
      camera: string
      score: number
      video_uri: string
    }>
    primary_camera?: string
    primary_video_uri?: string
  }
  index: number
  highlight?: "gold" // For verified matches
}

export default function SceneCard({ scene, index, highlight }: SceneCardProps) {
  const router = useRouter()
  const [isCameraExpanded, setIsCameraExpanded] = useState(false)

  // 6-camera configuration helper
  const getCameraDisplayName = (cameraName: string) => {
    const displayMap: { [key: string]: string } = {
      'CAM_FRONT': 'Front',
      'CAM_BACK': 'Rear',
      'CAM_FRONT_LEFT': 'Front L',
      'CAM_FRONT_RIGHT': 'Front R',
      'CAM_BACK_LEFT': 'Rear L',
      'CAM_BACK_RIGHT': 'Rear R'
    }
    return displayMap[cameraName] || cameraName.replace('CAM_', '')
  }

  // Get camera data for Apple-grade display
  const getCameraData = () => {
    if (scene.cameras && scene.cameras.length > 0) {
      // Deduplicate cameras by name (fix for S3 vectors bug)
      const uniqueCameras = scene.cameras.reduce((acc: any[], cam) => {
        const existing = acc.find(c => c.camera === cam.camera)
        if (!existing || (cam.score && cam.score > existing.score)) {
          return [...acc.filter(c => c.camera !== cam.camera), cam]
        }
        return acc
      }, [])

      return uniqueCameras.map(cam => ({
        name: cam.camera,
        displayName: getCameraDisplayName(cam.camera),
        score: cam.score ? Math.round(cam.score * 100) : null
      }))
    }
    return []
  }

  const cameraData = getCameraData()

  // Handler for Visual Search
  const handleVisualSearch = (e: React.MouseEvent) => {
    e.preventDefault() // Prevent clicking the parent Link
    e.stopPropagation()

    // Route to search page with Visual Mode params
    const params = new URLSearchParams()
    params.set('mode', 'visual')       // Tell backend to use Cosmos
    params.set('ref', scene.scene_id)  // The reference scene ID

    router.push(`/search/results?${params.toString()}`)
  }

  // Generate camera-aware forensic URL
  const getForensicUrl = () => {
    const baseUrl = `/forensic?id=${scene.scene_id}`

    // Add camera parameter if available from search results
    if (scene.primary_camera && scene.primary_camera !== 'CAM_FRONT') {
      return `${baseUrl}&camera=${scene.primary_camera}`
    }

    return baseUrl
  }

  // Generate forensic URL for specific camera
  const getCameraSpecificUrl = (cameraName: string) => {
    return `/forensic?id=${scene.scene_id}&camera=${cameraName}`
  }

  const getRiskColor = (score: number) => {
    if (score >= 0.7) return "var(--safety-orange)"
    if (score >= 0.4) return "var(--warning-amber)"
    return "var(--success-green)"
  }

  const formatDate = (timestamp?: string) => {
    if (!timestamp) return "Unknown date"
    // Use manual formatting to ensure server/client consistency
    const date = new Date(timestamp)
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    const month = months[date.getUTCMonth()]
    const day = date.getUTCDate()
    const hours = date.getUTCHours().toString().padStart(2, '0')
    const minutes = date.getUTCMinutes().toString().padStart(2, '0')

    return `${month} ${day}, ${hours}:${minutes}`
  }

  // Verified match styling
  const isVerified = highlight === "gold" || scene.is_verified
  const cardClassName = isVerified 
    ? "overflow-hidden border border-amber-200/50 shadow-[0_8px_30px_rgb(251,191,36,0.1)] hover:shadow-[0_12px_40px_rgb(251,191,36,0.15)] transition-all duration-500 bg-gradient-to-br from-white to-amber-50/30 rounded-2xl"
    : "overflow-hidden border-0 shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-card-hover)] transition-all duration-500 bg-white rounded-2xl"

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{
        duration: isVerified ? 0.5 : 0.4, // Verified cards have "weight"
        delay: index * 0.05,
        type: "spring",
        stiffness: 100
      }}
      whileHover={{ 
        y: -4, 
        transition: { duration: 0.2 }
      }}
      className={`group ${isVerified ? 'relative' : ''}`}
    >
      {/* Shimmer effect for verified cards */}
      {isVerified && (
        <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-amber-200/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000 ease-out" />
        </div>
      )}
      
      <Link href={getForensicUrl()}>
        <Card className={cardClassName}>
          {/* Thumbnail Section */}
          <div className="relative aspect-video bg-gray-100 overflow-hidden">
            <Image
              src={scene.thumbnail_url || "/api/placeholder/400/225"}
              alt={`Scene ${scene.scene_id}`}
              fill
              className="object-cover"
              onError={(e) => {
                // Replace failed image with fallback design
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
              }}
            />
            <div className="w-full h-full bg-gradient-to-br from-gray-800 to-gray-900 items-center justify-center hidden" style={{ display: 'none' }}>
              <div className="text-center">
                <div className="w-16 h-16 bg-[var(--cyber-blue)]/20 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Camera className="w-8 h-8 text-[var(--cyber-blue)]" />
                </div>
                <p className="text-xs text-gray-400 font-mono">SCENE DATA</p>
                <p className="text-[10px] text-gray-500 mt-1">Thumbnail unavailable</p>
              </div>
            </div>

            {/* Refined Overlay: Subtle Gradient instead of flat black */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 flex flex-col items-center justify-center gap-3">
              <motion.div
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                className="w-12 h-12 bg-[var(--cyber-blue)] rounded-full flex items-center justify-center"
              >
                <Play className="w-5 h-5 text-white ml-1" />
              </motion.div>

              {/* Find Similar Button */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileHover={{ scale: 1.05 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <Button 
                    size="sm" 
                    variant="secondary"
                    className="bg-white/90 hover:bg-white text-[var(--cyber-blue)] gap-2 shadow-xl backdrop-blur-sm border-0 font-medium text-xs h-8"
                    onClick={handleVisualSearch}
                >
                    <Eye className="w-3 h-3" />
                    Find Similar
                </Button>
              </motion.div>
            </div>

            {/* Traffic Light Status Badge */}
            <div className="absolute top-3 right-3 flex items-center gap-2">
              {/* Apple-Grade 3-Tier Status */}
              {scene.anomaly_status === "CRITICAL" && (
                <Badge className="bg-red-500/90 border-0 text-white text-xs animate-pulse shadow-lg">
                  🔴 CRITICAL
                </Badge>
              )}
              {scene.anomaly_status === "DEVIATION" && (
                <Badge className="bg-amber-500/90 border-0 text-white text-xs shadow-lg">
                  🟡 DEVIATION
                </Badge>
              )}
              {scene.anomaly_status === "NORMAL" && (
                <Badge className="bg-emerald-500/90 border-0 text-white text-xs shadow-lg">
                  🟢 NORMAL
                </Badge>
              )}

              {/* HIL Qualification Badge with Enhanced Tooltip */}
              {scene.hil_qualification && scene.hil_qualification.level !== "LOW" && (
                <motion.div
                  animate={scene.hil_qualification.level === "HIGH" ? { scale: [1, 1.1, 1] } : {}}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="flex items-center gap-1"
                >
                  <Badge
                    variant="outline"
                    className={`border-0 text-white font-medium ${
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
                  <InfoTooltip
                    title={getMetricDefinition('hil_priority')?.title || 'HIL Priority'}
                    description={`${getMetricDefinition('hil_priority')?.description || 'Hardware-in-Loop testing priority assessment'} This scenario is rated ${scene.hil_qualification.level} priority.`}
                    calculation={`Agent reasoning: ${scene.hil_qualification.reason}`}
                    size="sm"
                    position="auto"
                  />
                </motion.div>
              )}
            </div>

            {/* Apple-Grade Multi-Camera Display */}
            {(scene.camera_angles || cameraData.length > 0) && (
              <div className="absolute top-3 left-3">
                {cameraData.length === 1 ? (
                  // Single Camera - Show Specific Camera Name (not generic "Front")
                  <Badge variant="secondary" className="bg-black/60 backdrop-blur-sm text-white border-0 font-medium">
                    <Camera className="w-3 h-3 mr-1.5" />
                    {/* Show specific camera name for single camera display */}
                    {(() => {
                      const cameraSpecificNames = {
                        'CAM_FRONT': 'Front Center',
                        'CAM_BACK': 'Rear Center',
                        'CAM_FRONT_LEFT': 'Front L',
                        'CAM_FRONT_RIGHT': 'Front R',
                        'CAM_BACK_LEFT': 'Rear L',
                        'CAM_BACK_RIGHT': 'Rear R'
                      }
                      return cameraSpecificNames[cameraData[0].name as keyof typeof cameraSpecificNames] || cameraData[0].displayName
                    })()}
                    {cameraData[0].score && (
                      <span className="ml-1.5 text-blue-200 text-xs">
                        {cameraData[0].score}%
                      </span>
                    )}
                  </Badge>
                ) : cameraData.length > 1 ? (
                  // Multiple Cameras - Expandable Apple-Style
                  <div className="space-y-1">
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setIsCameraExpanded(!isCameraExpanded)
                      }}
                      className="flex items-center gap-1.5 bg-black/60 backdrop-blur-sm text-white border-0 rounded-full px-3 py-1.5 font-medium text-sm hover:bg-black/70 transition-all duration-200"
                    >
                      <Camera className="w-3 h-3" />
                      <span>{cameraData.length} Cameras</span>
                      {isCameraExpanded ? (
                        <ChevronDown className="w-3 h-3 ml-0.5" />
                      ) : (
                        <ChevronRight className="w-3 h-3 ml-0.5" />
                      )}
                    </button>

                    {/* Expandable Camera List */}
                    {isCameraExpanded && (
                      <motion.div
                        initial={{ opacity: 0, y: -5, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -5, scale: 0.95 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        className="bg-black/80 backdrop-blur-md rounded-xl p-2 space-y-1 min-w-[120px]"
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                        }}
                      >
                        {cameraData
                          .sort((a, b) => (b.score || 0) - (a.score || 0)) // Sort by score descending
                          .map((camera) => (
                            <Link
                              key={camera.name}
                              href={getCameraSpecificUrl(camera.name)}
                              onClick={(e) => {
                                e.stopPropagation() // Prevent main card click
                              }}
                              className="flex items-center justify-between px-2 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 transition-colors cursor-pointer"
                            >
                              <span className="text-white text-xs font-medium">
                                {camera.displayName}
                              </span>
                              {camera.score && (
                                <span className="text-blue-200 text-xs font-mono">
                                  {camera.score}%
                                </span>
                              )}
                            </Link>
                          ))
                        }
                      </motion.div>
                    )}
                  </div>
                ) : (
                  // Fallback for legacy data - show camera count
                  <Badge variant="secondary" className="bg-black/60 backdrop-blur-sm text-white border-0">
                    <Camera className="w-3 h-3 mr-1" />
                    {scene.camera_angles?.length || 'Unknown'} Cams
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Content Section - REFINED */}
          <div className="p-5 space-y-5">
            {/* Header with Monospace ID */}
            <div className="flex items-center justify-between">
              <h3 className="font-mono text-sm font-medium text-[var(--slate-grey)]">
                {scene.scene_id}
              </h3>
              <div className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-[var(--slate-grey)] bg-gray-50 px-2 py-1 rounded-full">
                <Calendar className="w-3 h-3" />
                {formatDate(scene.timestamp)}
              </div>
            </div>

            {/* Risk Score with Apple-grade Info Tooltip */}
            {scene.risk_score !== undefined && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[var(--slate-grey)] font-medium">Risk Score</span>
                    <InfoTooltip
                      title={getMetricDefinition('risk_score')?.title || 'Risk Score'}
                      description={getMetricDefinition('risk_score')?.description || 'Overall safety risk assessment for this driving scenario'}
                      calculation={getMetricDefinition('risk_score')?.calculation}
                      size="sm"
                      position="auto"
                    />
                  </div>
                  <span className="font-bold" style={{ color: getRiskColor(scene.risk_score) }}>
                    {(scene.risk_score * 100).toFixed(0)}
                  </span>
                </div>
                <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${scene.risk_score * 100}%` }}
                    transition={{ duration: 1, delay: 0.5 }}
                    className="h-full rounded-full"
                    style={{ backgroundColor: getRiskColor(scene.risk_score) }}
                  />
                </div>
              </div>
            )}

            {/* Footer: Tags + HIL Business Intelligence */}
            <div className="space-y-2 pt-2 border-t border-gray-50">
              {/* Tags Row */}
              <div className="flex flex-wrap gap-1.5">
                {(scene.tags || []).slice(0, 3).map((tag, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-1 bg-gray-50 text-gray-500 rounded-md font-medium border border-gray-100"
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Twin Engine Indicators */}
              {(scene.engines || scene.matches) && (
                <div className="flex items-center gap-1.5 text-[9px]">
                  <span className="text-gray-400 font-medium">Found by:</span>
                  {scene.engines?.includes('behavioral') && (
                    <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded border border-blue-100 font-medium">
                      🧠 Cohere
                    </span>
                  )}
                  {scene.engines?.includes('visual') && (
                    <span className="px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded border border-purple-100 font-medium">
                      👁️ Cosmos
                    </span>
                  )}
                  {isVerified && (
                    <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded border border-amber-200 font-semibold">
                      Both
                    </span>
                  )}
                </div>
              )}

              {/* HIL Business Reasoning - Shows Backend Intelligence */}
              {scene.hil_qualification && scene.hil_qualification.level !== "LOW" && (
                <div className="flex items-start gap-1 text-[9px] text-[var(--slate-grey)]">
                  <Brain className="w-3 h-3 opacity-60 mt-0.5 flex-shrink-0" />
                  <span className="font-medium opacity-80 break-words line-clamp-2 overflow-hidden">
                    {scene.hil_qualification.reason}
                  </span>
                </div>
              )}
            </div>
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}