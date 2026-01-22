"use client"

import { useState, useEffect } from "react"
import { SceneDetail } from "@/types/scene"

const API_BASE_URL = "/api"

export function useSceneDetail(sceneId: string) {
  const [data, setData] = useState<SceneDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchSceneDetail() {
    if (!sceneId) return

    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`${API_BASE_URL}/scene/${sceneId}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch scene details: ${response.statusText}`)
      }

      const apiData = await response.json()

      // Extract real data from backend response structure
      const phase3Data = apiData.phase3_raw_analysis || {}
      const phase6ParsedData = apiData.phase6_parsed || {} // Use new parsed data

      console.log(" Using new phase6_parsed data:", phase6ParsedData)

      // Extract quantified metrics from Phase 3 (real performance data)
      const quantifiedMetrics = phase3Data.quantified_metrics || {}
      const businessIntel = phase3Data.business_intelligence || quantifiedMetrics.business_intelligence || {}

      // Use the new parsed Phase 6 data directly (no more string parsing needed!)
      const sceneAnalysisRaw = {
        scene_analysis: {
          environmental_conditions: phase6ParsedData.scene_analysis_summary || "",
        },
        behavioral_insights: {
          scene_description: phase6ParsedData.scene_analysis_summary || "",
          critical_decisions: phase6ParsedData.key_findings?.[0] || "",
          edge_case_elements: phase6ParsedData.key_findings?.[1] || "",
          performance_indicators: phase6ParsedData.key_findings?.[2] || "",
        }
      }

      const anomalyAnalysisRaw = {
        anomaly_findings: {
          unusual_patterns: phase6ParsedData.anomaly_summary || "",
          anomaly_severity: phase6ParsedData.anomaly_severity || 0.0  // Use real S3 Vectors statistical score
        },
        anomaly_classification: {
          anomaly_type: phase6ParsedData.anomaly_summary || "",
          hil_testing_value: phase6ParsedData.recommendations?.[0]?.split(' -')[0]?.trim()?.toLowerCase() || "low"  // Extract from backend recommendations
        },
        anomaly_recommendations: {
          hil_testing_priority: phase6ParsedData.recommendations?.[0] || ""
        }
      }

      console.log("Parsed scene analysis:", sceneAnalysisRaw)
      console.log("Parsed anomaly analysis:", anomalyAnalysisRaw)

      // Extract real risk and safety scores (from Phase 3 quantified metrics)
      const riskScore = quantifiedMetrics.risk_score || 0.0
      const safetyScore = quantifiedMetrics.safety_score || 0.0

      // Extract real tags from multiple sources (no string matching)
      const extractTags = () => {
        const tags = []

        // From business intelligence - ensure we only push strings
        if (businessIntel.environment_type) {
          const envType = typeof businessIntel.environment_type === 'string' ?
                         businessIntel.environment_type :
                         JSON.stringify(businessIntel.environment_type)
          tags.push(envType)
        }
        if (businessIntel.weather_condition) {
          const weather = typeof businessIntel.weather_condition === 'string' ?
                         businessIntel.weather_condition :
                         JSON.stringify(businessIntel.weather_condition)
          tags.push(weather)
        }
        if (businessIntel.scenario_type) {
          const scenario = typeof businessIntel.scenario_type === 'string' ?
                          businessIntel.scenario_type :
                          JSON.stringify(businessIntel.scenario_type)
          tags.push(scenario)
        }

        // From scene characteristics in agent analysis - ensure we only push strings
        const sceneCharacteristics = (sceneAnalysisRaw as any).scene_characteristics || {}
        if (sceneCharacteristics.scenario_type) {
          const scenario = typeof sceneCharacteristics.scenario_type === 'string' ?
                          sceneCharacteristics.scenario_type :
                          JSON.stringify(sceneCharacteristics.scenario_type)
          tags.push(scenario)
        }
        if (sceneCharacteristics.complexity_level) {
          const complexity = typeof sceneCharacteristics.complexity_level === 'string' ?
                            sceneCharacteristics.complexity_level :
                            JSON.stringify(sceneCharacteristics.complexity_level)
          tags.push(complexity)
        }
        if (sceneCharacteristics.safety_criticality) {
          const safety = typeof sceneCharacteristics.safety_criticality === 'string' ?
                        sceneCharacteristics.safety_criticality :
                        JSON.stringify(sceneCharacteristics.safety_criticality)
          tags.push(safety)
        }

        // From anomaly classification - extract only the priority level (before dash)
        const anomalyClass = anomalyAnalysisRaw.anomaly_classification || {}
        if (anomalyClass.hil_testing_value) {
          const hilPriority = anomalyClass.hil_testing_value.split(' -')[0].trim().toLowerCase()
          tags.push(`hil-${hilPriority}`)
        }

        return [...new Set(tags)].filter(tag => tag && typeof tag === 'string')
      }

      // Determine anomaly status from agent's actual analysis
      const anomalyDetected = (() => {
        const anomalyClass = anomalyAnalysisRaw.anomaly_classification || {}
        const anomalyFindings = anomalyAnalysisRaw.anomaly_findings || {}

        // PRIORITY 1: Use real statistical anomaly severity from S3 Vectors (ground truth)
        if (typeof anomalyFindings.anomaly_severity === 'number') {
          return anomalyFindings.anomaly_severity > 0.3  // Real fleet-wide statistical analysis
        }

        // FALLBACK 2: Use agent's HIL testing value conclusion
        if (anomalyClass.hil_testing_value) {
          const hilValue = anomalyClass.hil_testing_value.toLowerCase()
          return hilValue !== 'low'
        }

        // FALLBACK 3: Use anomaly type from agent
        if (anomalyClass.anomaly_type) {
          return !anomalyClass.anomaly_type.includes('No major anomaly type detected')
        }

        // Default to false (normal scenario)
        return false
      })()

      const transformedData: SceneDetail = {
        scene_id: apiData.scene_id,
        timestamp: apiData.metadata?.processing_timestamp || new Date().toISOString(),
        risk_score: riskScore,
        safety_score: safetyScore,
        tags: extractTags(),
        analysis_summary: phase6ParsedData.scene_analysis_summary || "Scene analysis not available",
        anomaly_detected: anomalyDetected,
        anomaly_status: apiData.phase6_parsed?.anomaly_status || 'NORMAL',
        all_camera_urls: apiData.all_camera_urls || {},
        scene_understanding: {
          summary: phase6ParsedData.scene_analysis_summary || "Scene analysis not available",
          key_findings: phase6ParsedData.key_findings || [],
          behavioral_insights: phase6ParsedData.recommendations || []
        },
        anomaly_analysis: {
          detected: anomalyDetected,
          risk_level: riskScore > 0.5 ? "high" : riskScore > 0.3 ? "medium" : "low",
          description: phase6ParsedData.anomaly_summary || "No anomaly analysis available",
          metrics: quantifiedMetrics
        },
        intelligence_insights: {
          business_impact: `Business impact analysis: ${phase6ParsedData.scene_analysis_summary || 'Analysis pending'}`,
          training_value: `Training value: ${anomalyDetected ? "High value for HIL testing" : "Standard scenario coverage"}`,
          recommendations: phase6ParsedData.recommendations || []
        }
      }

      setData(transformedData)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSceneDetail()
  }, [sceneId])

  return { data, loading, error, refetch: fetchSceneDetail }
}