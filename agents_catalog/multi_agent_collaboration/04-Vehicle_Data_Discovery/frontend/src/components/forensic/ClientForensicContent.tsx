/**
 * ClientForensicContent - Scene Detail Client Component
 * 
 * Client-side wrapper for forensic page that fetches scene data
 * and renders video player, metrics panel, and agent analysis.
 */
"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import Link from "next/link"
import { ArrowLeft, Download, Share, Trash2 } from "lucide-react"
import MultiCameraPlayer from "./MultiCameraPlayer"
import MetricsPanel from "./MetricsPanel"
import AgentAnalysis from "./AgentAnalysis"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SceneDetail } from "@/types/scene"
import { authenticatedFetch } from "@/lib/api"

interface ClientForensicContentProps {
  sceneData: SceneDetail | null
  sceneId: string
  initialCamera?: string | null // NEW: Camera parameter from URL
}

export default function ClientForensicContent({
  sceneData: initialSceneData,
  sceneId,
  initialCamera
}: ClientForensicContentProps) {
  const [sceneData, setSceneData] = useState<SceneDetail | null>(initialSceneData)
  const [loading, setLoading] = useState(!initialSceneData)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // If we already have data from SSR, don't fetch again
    if (initialSceneData) {
      return
    }

    // Client-side data fetching for CloudFront deployment
    async function fetchSceneData() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api'
        const response = await authenticatedFetch(`${apiUrl}/scene/${sceneId}`)

        if (!response.ok) {
          throw new Error(`Failed to fetch scene details: ${response.statusText}`)
        }

        const apiData = await response.json()

        // Use the same data transformation logic from the original server-side function
        const phase3Data = apiData.phase3_raw_analysis || {}
        const phase6ParsedData = apiData.phase6_parsed || {}

        const cleanPhase6Data = {
          scene_analysis_summary: phase6ParsedData.scene_analysis_summary || "Scene analysis not available",
          key_findings: phase6ParsedData.key_findings || [],
          anomaly_summary: phase6ParsedData.anomaly_summary || "No anomaly analysis available",
          recommendations: phase6ParsedData.recommendations || [],
          confidence_score: phase6ParsedData.confidence_score || 0.0,
          anomaly_severity: phase6ParsedData.anomaly_severity || 0.0
        }

        const quantifiedMetrics = phase3Data.quantified_metrics || {}
        const businessIntel = phase3Data.business_intelligence || quantifiedMetrics.business_intelligence || {}

        const riskScore = quantifiedMetrics.risk_score || 0.0
        const safetyScore = quantifiedMetrics.safety_score || 0.0

        const extractTags = () => {
          const tags = []
          if (businessIntel.environment_type) tags.push(String(businessIntel.environment_type))
          if (businessIntel.weather_condition) tags.push(String(businessIntel.weather_condition))
          if (businessIntel.scenario_type) tags.push(String(businessIntel.scenario_type))
          if (businessIntel.safety_criticality) tags.push(String(businessIntel.safety_criticality))
          return [...new Set(tags)].filter(tag => tag && typeof tag === 'string')
        }

        const anomalyDetected = typeof cleanPhase6Data.anomaly_severity === 'number' ?
          cleanPhase6Data.anomaly_severity > 0 : false

        const transformedSceneData: SceneDetail = {
          scene_id: apiData.scene_id,
          timestamp: apiData.metadata?.processing_timestamp || new Date().toISOString(),
          risk_score: riskScore,
          safety_score: safetyScore,
          tags: extractTags(),
          analysis_summary: cleanPhase6Data.scene_analysis_summary,
          anomaly_detected: anomalyDetected,
          anomaly_status: apiData.phase6_parsed?.anomaly_status || 'NORMAL',
          all_camera_urls: apiData.all_camera_urls || {},
          scene_understanding: {
            summary: cleanPhase6Data.scene_analysis_summary,
            key_findings: cleanPhase6Data.key_findings,
            behavioral_insights: cleanPhase6Data.recommendations
          },
          anomaly_analysis: {
            detected: anomalyDetected,
            tier: anomalyDetected ? (riskScore > 0.7 ? "critical" : riskScore > 0.4 ? "deviation" : "baseline") : "baseline",
            badge_status: apiData.phase6_parsed?.anomaly_status || 'NORMAL',
            risk_level: anomalyDetected ? (riskScore > 0.7 ? "high" : riskScore > 0.4 ? "medium" : "low") : "low",
            description: cleanPhase6Data.anomaly_summary,
            classification: phase6ParsedData.anomaly_classification || {},
            metrics: Object.fromEntries(
              Object.entries(quantifiedMetrics).filter(([key, value]) =>
                key !== 'business_intelligence' && typeof value === 'number'
              ).map(([key, value]) => [key, value as number])
            )
          },
          intelligence_insights: {
            business_impact: String(`${businessIntel.environment_type || businessIntel.scenario_type || 'Unknown'} scenario with ${businessIntel.safety_criticality || 'standard'} safety criticality`),
            training_value: cleanPhase6Data.recommendations?.[0] || "Analysis pending",
            recommendations: cleanPhase6Data.recommendations
          }
        }

        setSceneData(transformedSceneData)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load scene data")
      } finally {
        setLoading(false)
      }
    }

    fetchSceneData()
  }, [sceneId, initialSceneData])

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p className="text-gray-600">Loading scene details...</p>
      </div>
    )
  }

  if (error || !sceneData) {
    return (
      <div className="text-center py-12">
        <div className="text-red-500 mb-4">
          <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-800 mb-2">Scene Not Found</h2>
        <p className="text-gray-600 mb-6">The scene &quot;{sceneId}&quot; could not be loaded. {error}</p>
        <Link href="/">
          <Button variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Fleet Command
          </Button>
        </Link>
      </div>
    )
  }

  // Debug logging for serialization issues

  const formatDate = (timestamp: string) => {
    return new Date(timestamp).toLocaleString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <Link href="/">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="w-10 h-10 bg-[var(--pure-white)] border border-gray-200 rounded-lg flex items-center justify-center hover:bg-[var(--soft-grey)] transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-[var(--slate-grey)]" />
            </motion.button>
          </Link>
          <div>
            <h1 className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
              Forensic Analysis: {sceneId}
            </h1>
            <p className="text-[var(--slate-grey)] mt-1">
              Captured on {formatDate(sceneData.timestamp)} • Multi-angle investigation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Apple-Grade 3-Tier Anomaly Status */}
          {sceneData.anomaly_status === "CRITICAL" && (
            <Badge className="bg-red-500/90 border-0 text-white animate-pulse shadow-lg">
              🔴 CRITICAL
            </Badge>
          )}
          {sceneData.anomaly_status === "DEVIATION" && (
            <Badge className="bg-amber-500/90 border-0 text-white shadow-md">
              🟡 DEVIATION
            </Badge>
          )}
          {sceneData.anomaly_status === "NORMAL" && (
            <Badge className="bg-emerald-500/90 border-0 text-white shadow-sm">
              🟢 NORMAL
            </Badge>
          )}
          <Button variant="outline" size="sm">
            <Share className="w-4 h-4 mr-2" />
            Share
          </Button>
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </motion.div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-3 gap-8">
        {/* Left Column: Video Player (2/3 width) */}
        <div className="col-span-2 space-y-6">
          {/* Multi-Camera Player */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <MultiCameraPlayer
              cameraUrls={sceneData.all_camera_urls}
              defaultCamera={initialCamera || "CAM_FRONT"}
            />
          </motion.div>

          {/* Agent Analysis */}
          <AgentAnalysis sceneData={sceneData} />
        </div>

        {/* Right Column: Metrics & Actions (1/3 width) */}
        <div className="space-y-6">
          {/* Metrics Panel */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <MetricsPanel
              sceneData={{
                risk_score: sceneData.risk_score,
                safety_score: sceneData.safety_score,
                anomaly_detected: sceneData.anomaly_detected,
                anomaly_status: sceneData.anomaly_status,
                anomaly_analysis: sceneData.anomaly_analysis
              }}
            />
          </motion.div>

          {/* Decision Panel */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <Card className="p-6 bg-[var(--pure-white)] border-gray-200">
              <h3 className="font-semibold text-[var(--deep-charcoal)] mb-4">
                Data Retention Decision
              </h3>
              <p className="text-sm text-[var(--slate-grey)] mb-6 leading-relaxed">
                Based on the analysis, should this scene be retained for training data or
                discarded to reduce DTO costs?
              </p>

              <div className="space-y-3">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full p-4 bg-[var(--success-green)] text-white rounded-lg font-medium hover:bg-[var(--success-green)]/90 transition-colors"
                >
                  <span>Retain for Training</span>
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full p-4 bg-[var(--slate-grey)] text-white rounded-lg font-medium hover:bg-[var(--slate-grey)]/90 transition-colors"
                >
                  Archive & Compress
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full p-3 bg-[var(--error-red)]/10 text-[var(--error-red)] rounded-lg font-medium hover:bg-[var(--error-red)]/20 transition-colors border border-[var(--error-red)]/20"
                >
                  <div className="flex items-center justify-center gap-2">
                    <Trash2 className="w-4 h-4" />
                    <span>Discard Scene</span>
                  </div>
                </motion.button>
              </div>
            </Card>
          </motion.div>

          {/* Scene Metadata */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.4 }}
          >
            <Card className="p-6 bg-[var(--pure-white)] border-gray-200">
              <h3 className="font-semibold text-[var(--deep-charcoal)] mb-4">
                Scene Metadata
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--slate-grey)]">Scene ID:</span>
                  <span className="font-mono font-medium text-[var(--deep-charcoal)]">
                    {sceneData.scene_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--slate-grey)]">Cameras:</span>
                  <span className="font-medium text-[var(--deep-charcoal)]">
                    {Object.keys(sceneData.all_camera_urls).length} angles
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--slate-grey)]">Duration:</span>
                  <span className="font-medium text-[var(--deep-charcoal)]">
                    ~30 seconds
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--slate-grey)]">Status:</span>
                  {/* Apple-Grade 3-Tier Status Badge */}
                  {sceneData.anomaly_status === "CRITICAL" && (
                    <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20 animate-pulse">
                      🔴 Critical
                    </Badge>
                  )}
                  {sceneData.anomaly_status === "DEVIATION" && (
                    <Badge variant="outline" className="bg-amber-500/10 text-amber-600 border-amber-500/20">
                      🟡 Deviation
                    </Badge>
                  )}
                  {sceneData.anomaly_status === "NORMAL" && (
                    <Badge variant="outline" className="bg-[var(--success-green)]/10 text-[var(--success-green)] border-[var(--success-green)]/20">
                      🟢 Normal
                    </Badge>
                  )}
                </div>
              </div>

              {/* Tags */}
              {sceneData.tags && sceneData.tags.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-2">
                    Tags
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {sceneData.tags.map((tag, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="text-xs bg-[var(--soft-grey)] border-gray-300 text-[var(--slate-grey)]"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  )
}