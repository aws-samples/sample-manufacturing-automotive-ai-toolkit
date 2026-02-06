/**
 * Analytics Page - ODD Coverage Dashboard
 * 
 * Displays comprehensive analytics including risk trends, coverage matrix,
 * AI-discovered categories, and DTO savings metrics.
 * 
 * @route /analytics
 */
"use client"

import { motion } from "framer-motion"
import { useState } from "react"
import { BarChart3, TrendingUp, PieChart, Activity, AlertTriangle, CheckCircle, Clock, Search, AlertCircle, Brain, Target, Zap, DollarSign, RefreshCw, Play, CheckCircle2 } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import InfoTooltip from "@/components/ui/InfoTooltip"
import { useAnalytics } from "@/hooks/useAnalytics"
import { useTrafficLightStats } from "@/hooks/useTrafficLightStats"
import { useOddDiscovery, OddCategory } from "@/hooks/useOddDiscovery"
import { XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart as RechartsPie, Pie, Cell, LineChart, Line } from "recharts"
import DashboardLayout from "@/components/layout/DashboardLayout"
import ProtectedRoute from "@/components/auth/ProtectedRoute"

const COLORS = {
  CRITICAL: '#EF4444',
  WARNING: '#F59E0B',
  HEALTHY: '#10B981',
  PRIMARY: '#3B82F6'
}

interface PriorityItem {
  status?: string
  hil_priority?: string
}

interface RiskTimelineItem {
  date: string
  risk_score?: number
  risk?: number
  scene_id?: string
  id?: string
}

interface CoverageCategory {
  category: string
  description?: string
  type?: string
  status?: string
  hil_priority?: string
  risk_adaptive_target?: number
  actual_scenes?: number
  current?: number
  target?: number
  average_risk_score?: number
  uniqueness_score?: number
  percentage?: number
}

// Helper function for case-insensitive priority classification
const getPriorityLevel = (item: PriorityItem) => {
  const status = item.status?.toLowerCase() || ''
  const hilPriority = item.hil_priority?.toLowerCase() || ''

  if (status === 'critical' || hilPriority === 'critical') return 'critical'
  if (status === 'warning' || hilPriority === 'high' || hilPriority === 'medium') return 'warning'
  return 'normal'
}

// Discovery job status interface
interface DiscoveryJobStatus {
  job_id: string
  status: 'running' | 'completed' | 'failed'
  progress: number
  current_step: string
  duration_seconds?: number
  clusters_discovered?: number
  error_message?: string
  ready_for_use?: boolean
}

export default function AnalyticsPage() {
  const { data, coverageData, loading } = useAnalytics()
  const trafficLightData = useTrafficLightStats()
  const oddDiscoveryData = useOddDiscovery()

  // Discovery state management
  const [discoveryState, setDiscoveryState] = useState<{
    isRunning: boolean
    currentJobId: string | null
    progress: number
    currentStep: string
    error: string | null
    completed: boolean
  }>({
    isRunning: false,
    currentJobId: null,
    progress: 0,
    currentStep: '',
    error: null,
    completed: false
  })

  // Trigger ODD rediscovery
  const triggerDiscovery = async () => {
    try {
      setDiscoveryState(prev => ({
        ...prev,
        isRunning: true,
        error: null,
        completed: false,
        progress: 0,
        currentStep: 'Initializing discovery process'
      }))

      const response = await fetch('/api/analytics/rediscover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      if (!response.ok) {
        throw new Error(`Discovery trigger failed: ${response.status}`)
      }

      const result = await response.json()
      setDiscoveryState(prev => ({
        ...prev,
        currentJobId: result.job_id,
        currentStep: 'Discovery started - loading embeddings'
      }))

      // Start polling for status
      startStatusPolling(result.job_id)

    } catch (error) {
      setDiscoveryState(prev => ({
        ...prev,
        isRunning: false,
        error: error instanceof Error ? error.message : 'Failed to start discovery'
      }))
    }
  }

  // Poll discovery job status
  const startStatusPolling = (jobId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/analytics/rediscover/${jobId}/status`)
        if (!response.ok) {
          throw new Error('Status polling failed')
        }

        const status: DiscoveryJobStatus = await response.json()

        setDiscoveryState(prev => ({
          ...prev,
          progress: status.progress,
          currentStep: status.current_step,
          completed: status.status === 'completed',
          error: status.status === 'failed' ? status.error_message || 'Discovery failed' : null,
          isRunning: status.status === 'running'
        }))

        // Stop polling when completed or failed
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(pollInterval)

          if (status.status === 'completed') {
            // Refresh ODD discovery data
            setTimeout(() => {
              window.location.reload() // Simple approach to refresh data
            }, 1000)
          }
        }

      } catch {
        clearInterval(pollInterval)
        setDiscoveryState(prev => ({
          ...prev,
          isRunning: false,
          error: 'Status polling failed'
        }))
      }
    }, 2000) // Poll every 2 seconds

    // Cleanup interval on component unmount
    return () => clearInterval(pollInterval)
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gray-100 rounded-xl animate-pulse" />
          <div>
            <div className="h-6 w-48 bg-gray-100 rounded animate-pulse mb-2" />
            <div className="h-4 w-64 bg-gray-100 rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-16 bg-gray-100 rounded" />
            </Card>
          ))}
        </div>
      </div>
    )
  }

  // Format data for traffic light pie chart - use consistent 3-tier system
  const pieData = trafficLightData.stats?.critical ? [
    {
      name: "🔴 Critical",
      value: trafficLightData.stats?.critical?.count ?? 0,
      color: "#EF4444"
    },
    {
      name: "🟡 Deviation",
      value: trafficLightData.stats?.deviation?.count ?? 0,
      color: "#F59E0B"
    },
    {
      name: "🟢 Normal",
      value: trafficLightData.stats?.normal?.count ?? 0,
      color: "#10B981"
    }
  ].filter(item => item.value > 0) : [] // Only show categories with scenes

  const riskTimelineData = data?.risk_timeline?.map((item: RiskTimelineItem) => ({
    date: item.date,
    risk: Math.round((item.risk_score || item.risk || 0) * 100),
    scene: item.scene_id || item.id
  })) || []


  // Extract hybrid coverage matrix data
  const industryCategories = (coverageData?.coverage_matrix?.industry_standard_categories || []) as CoverageCategory[]
  const discoveredCategories = (coverageData?.coverage_matrix?.discovered_categories || []) as CoverageCategory[]
  const allCoverageItems = [...industryCategories, ...discoveredCategories]
  const coverageAnalysis = (coverageData?.coverage_matrix?.coverage_analysis || {}) as {
    total_scenes_analyzed?: number
    industry_approach?: { categories?: number; coverage_percentage?: number }
    discovered_approach?: { categories?: number; coverage_percentage?: number }
  }

  // Calculate critical gaps from both approaches
  const criticalGaps = allCoverageItems.filter(item => getPriorityLevel(item) === 'critical')

  // Coverage Matrix Find Similar handler (text-based twin-engine search)
  const handleCoverageMatrixSimilar = (category: CoverageCategory) => {
    // Enhanced description for better search precision
    const enhancedQuery = `autonomous vehicle driving scenario: ${category.description || category.category}`

    // Navigate to search page with enhanced twin-engine query
    const searchParams = new URLSearchParams({
      q: enhancedQuery,
      auto_query: 'true',
      source: 'coverage_matrix',
      category: category.category,
      type: category.type || ''
    })

    window.location.href = `/search/results?${searchParams.toString()}`
  }

// OddCategory imported from useOddDiscovery hook

  // ODD Discovery Find Similar handler (scene-based twin-engine search)
  const handleOddDiscoverySimilar = (category: OddCategory) => {
    const searchParams = new URLSearchParams({
      source: 'odd_discovery',
      category: category.category,
      type: 'discovered',
      uniqueness_quality: category.uniqueness_quality,
      uniqueness_score: category.uniqueness_score.toString()
    })

    // Enhanced: Use representative scene ID for true scene-to-scene similarity when available
    if (category.representative_scene_id) {
      // Scene-based similarity search using the most representative scene
      searchParams.set('scene_id', category.representative_scene_id)
      searchParams.set('auto_query', 'true')
    } else {
      // Fallback to text-based query for categories without representative scene IDs
      const sceneBasedQuery = `representative driving scenario from discovered category: ${category.category}`
      searchParams.set('q', sceneBasedQuery)
      searchParams.set('auto_query', 'true')
    }

    window.location.href = `/search/results?${searchParams.toString()}`
  }

  return (
    <ProtectedRoute>
      <DashboardLayout>
      <div className="space-y-8">
      {/* Apple-Grade Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-xl flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
              Fleet Analytics
            </h1>
            <p className="text-[var(--slate-grey)] mt-1">
              Statistical analysis & training dataset insights
            </p>
          </div>
        </div>
      </motion.div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
        <Card className="p-6 bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-blue-600">Total Scenes</p>
                <InfoTooltip
                  title="Total Scenes"
                  description="Individual driving scenarios extracted from ROS bag recordings. Each scene represents a continuous segment of multi-camera driving footage (typically 10-30 seconds) that has been processed through our 6-phase pipeline for behavioral analysis."
                  calculation="Counted from pipeline-results folder where each 'scene-XXXX' directory contains one processed driving scenario with multi-camera video, behavioral analysis, and anomaly detection results."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-blue-900">{data?.scenarios_processed || 0}</p>
            </div>
            <Activity className="w-8 h-8 text-blue-500" />
          </div>
        </Card>

        <Card className="p-6 bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-green-600">DTO Efficiency</p>
                <InfoTooltip
                  title="DTO (Data Transfer Object) Efficiency"
                  description="Cost savings achieved by transferring only unique, valuable driving scenarios instead of all collected data. DTO represents the expensive process of manually selecting and transferring training data from vehicle fleets to development teams."
                  calculation="🛡️ Safety-Weighted Approach: Uses risk-adaptive targets with safety multipliers instead of blind similarity reduction. Critical risk scenarios (>0.8) use zero-skip policy - all scenes tested regardless of similarity. High risk (0.5-0.8) requires minimum 80% testing. Routine scenarios can use similarity-based reduction. Formula: Count × max(Uniqueness, Safety_Multiplier). Prevents dangerous cost-cutting on safety-critical scenarios."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-green-900">{data?.dto_efficiency_percent || 0}%</p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
        </Card>

        <Card className="p-6 bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-amber-600">Critical Gaps</p>
                <InfoTooltip
                  title="Critical Training Dataset Gaps"
                  description="Scenario categories that are severely underrepresented in your training dataset (less than 50% of industry targets). These gaps could impact autonomous vehicle safety and regulatory compliance."
                  calculation="Based on semantic vector analysis comparing current scenario coverage to industry-standard targets. Critical status assigned when coverage is below 50% of target (e.g., Construction zones: 45/100 target = 45% coverage = CRITICAL)."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-amber-900">{criticalGaps.length}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-amber-500" />
          </div>
        </Card>

        {/* Apple-Grade Traffic Light System */}
        <Card className="p-6 bg-gradient-to-br from-red-50 to-red-100 border-red-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-red-600">🔴 Critical</p>
                <InfoTooltip
                  title="Critical Scenarios"
                  description="High-risk or extremely rare driving scenarios that require immediate investigation. These represent potential safety hazards or valuable edge cases for autonomous vehicle training."
                  calculation="Critical classification: anomaly_severity ≥ 0.6 OR risk_score ≥ 0.5. Includes emergency braking events, near-miss situations, complex multi-actor scenarios, and unusual environmental conditions."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-red-900">
                {trafficLightData.stats?.critical?.count || 0}
              </p>
              <p className="text-xs text-red-600 mt-1">
                {trafficLightData.stats?.critical?.percentage || 0}%
              </p>
            </div>
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
        </Card>

        <Card className="p-6 bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-amber-600">🟡 Deviation</p>
                <InfoTooltip
                  title="Deviation Scenarios"
                  description="Interesting variations from normal driving behavior that are worth reviewing. These scenarios show moderate anomaly patterns but aren't immediately dangerous - they represent learning opportunities and edge cases."
                  calculation="Deviation classification: anomaly_severity ≥ 0.2 AND not low priority. Examples include unusual traffic patterns, atypical pedestrian behavior, or moderate weather conditions affecting driving."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-amber-900">
                {trafficLightData.stats?.deviation?.count || 0}
              </p>
              <p className="text-xs text-amber-600 mt-1">
                {trafficLightData.stats?.deviation?.percentage || 0}%
              </p>
            </div>
            <Clock className="w-8 h-8 text-amber-500" />
          </div>
        </Card>

        <Card className="p-6 bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-1">
                <p className="text-sm font-medium text-green-600">🟢 Normal</p>
                <InfoTooltip
                  title="Normal Scenarios"
                  description="Standard driving scenarios that represent typical, everyday situations. These scenes have low anomaly scores and represent routine driving behavior that forms the baseline for comparison."
                  calculation="Normal classification: anomaly_severity < 0.2 OR agent priority assessment is 'Low'. Examples include highway cruising, routine lane changes, standard intersections, and normal traffic flow patterns."
                  size="sm"
                  position="auto"
                />
              </div>
              <p className="text-2xl font-bold text-green-900">
                {trafficLightData.stats?.normal?.count || 0}
              </p>
              <p className="text-xs text-green-600 mt-1">
                {trafficLightData.stats?.normal?.percentage || 0}%
              </p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </Card>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Traffic Light Distribution */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="font-semibold text-[var(--deep-charcoal)]">Traffic Light System</h3>
            <InfoTooltip
              title="Apple-Grade 3-Tier Classification"
              description="Consistent traffic light system across the platform. 🔴 Critical: High-risk scenarios requiring immediate investigation (severity ≥ 0.6 OR risk ≥ 0.5). 🟡 Deviation: Interesting variances worth reviewing (severity ≥ 0.2 AND not low priority). 🟢 Normal: Standard driving scenarios."
              calculation="Based on anomaly_severity and risk_score thresholds from Phase 6 agent analysis. Boundary values promote escalation for safety."
              size="sm"
              position="auto"
            />
          </div>
          <div className="w-full h-80 flex items-center justify-center">
            {!loading && typeof window !== 'undefined' && pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%" minHeight={300} minWidth={300}>
                <RechartsPie>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%" cy="50%"
                    outerRadius={100}
                    label={({name, percent}) => `${name} ${percent ? (percent * 100).toFixed(0) : '0'}%`}
                    labelLine={false}
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={Object.values(COLORS)[index]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </RechartsPie>
              </ResponsiveContainer>
            ) : loading ? (
              <div className="text-center text-gray-500">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--cyber-blue)] mx-auto mb-4"></div>
                <p className="text-sm">Loading traffic light data...</p>
              </div>
            ) : (
              <div className="text-center text-gray-500">
                <PieChart className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-sm">No traffic light data available</p>
                <p className="text-xs text-gray-400 mt-1">Categories with 0 scenes are filtered</p>
              </div>
            )}
          </div>
        </Card>

        {/* Risk Timeline */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="font-semibold text-[var(--deep-charcoal)]">Risk Timeline</h3>
            <InfoTooltip
              title="Risk Timeline"
              description="Tracks safety risk levels of driving scenarios over time. Higher peaks indicate more dangerous situations (emergency braking, complex intersections). Lower values show routine driving. Use this to identify patterns - are certain time periods more risky?"
              calculation="Risk Score: AI analysis of driving complexity, hazards, and safety criticality (0-100%). Each point = one analyzed driving scene. Timeline helps spot risk trends and seasonal patterns."
              size="sm"
              position="auto"
            />
          </div>
          <div className="w-full h-80 flex items-center justify-center">
            {!loading && typeof window !== 'undefined' && riskTimelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%" minHeight={300} minWidth={300}>
                <LineChart data={riskTimelineData}>
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis />
                  <Tooltip formatter={(value) => [`${value}%`, 'Risk Score']} />
                  <Line
                    type="monotone"
                    dataKey="risk"
                    stroke={COLORS.CRITICAL}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : loading ? (
              <div className="text-center text-gray-500">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--cyber-blue)] mx-auto mb-4"></div>
                <p className="text-sm">Loading risk timeline...</p>
              </div>
            ) : (
              <div className="text-center text-gray-500">
                <TrendingUp className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-sm">No risk timeline data available</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Coverage Matrix - THE STAR FEATURE */}
      <Card className="p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-xl font-semibold text-[var(--deep-charcoal)]">
                Training Dataset Coverage Matrix
              </h3>
              <InfoTooltip
                title="Smart Coverage Analysis"
                description="Uses advanced semantic vector similarity to analyze scenario coverage vs industry targets. Instead of just keyword matching, it understands meaning - finding 'heavy precipitation' when searching for 'rain' scenarios, or 'nighttime driving' for 'night' scenarios."
                calculation="Semantic Analysis: Creates vector embeddings for each category concept, then queries S3 Vectors for semantically similar scenes with similarity threshold ≥0.35. Much more accurate than string matching. Fallback to legacy keyword matching if vectors unavailable."
                size="sm"
                position="auto"
              />
            </div>

            {/* Coverage Matrix Sync Badge */}
            {discoveryState.isRunning && (
              <div className="flex items-center gap-2 mt-2 mb-2">
                <Badge variant="outline" className="text-xs px-3 py-1 text-blue-600 border-blue-300 bg-blue-50">
                  <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                  Syncing with Deep Discovery
                </Badge>
                <span className="text-xs text-blue-600">
                  Progress: {discoveryState.progress}%
                </span>
              </div>
            )}

            <p className="text-[var(--slate-grey)] mt-1">
              Statistical analysis of scenario representation vs industry targets
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-sm px-3 py-1">
              {coverageAnalysis?.total_scenes_analyzed || 0} scenes analyzed
            </Badge>
            <Badge className="text-xs px-2 py-1 bg-gradient-to-r from-purple-500 to-blue-500 border-0 text-white">
              🧠 Hybrid Analysis
            </Badge>
            <Badge variant="outline" className="text-xs px-2 py-1 text-green-600 border-green-300">
              Industry: {industryCategories.length} | Discovered: {discoveredCategories.length}
            </Badge>
          </div>
        </div>

        {/* Coverage Analysis Summary */}
        {(coverageAnalysis?.total_scenes_analyzed ?? 0) > 0 && (
          <div className="mb-6 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-lg font-semibold text-blue-800">
                  {coverageAnalysis.industry_approach?.categories || 0} Categories
                </div>
                <div className="text-sm text-blue-600">Industry Standards</div>
                <div className="text-xs text-blue-500">
                  {coverageAnalysis.industry_approach?.coverage_percentage || 0}% estimated coverage
                </div>
              </div>
              <div>
                <div className="text-lg font-semibold text-purple-800">
                  {coverageAnalysis.discovered_approach?.categories || 0} Categories
                </div>
                <div className="text-sm text-purple-600">AI Discovered</div>
                {(coverageAnalysis.discovered_approach?.categories || 0) === 0 ? (
                  <div className="text-xs text-purple-400 italic">
                    Run Deep Discovery to populate AI insights
                  </div>
                ) : (
                  <div className="text-xs text-purple-500">
                    {coverageAnalysis.discovered_approach?.coverage_percentage || 0}% actual coverage
                  </div>
                )}
              </div>
              <div>
                <div className="text-lg font-semibold text-green-800">
                  {(coverageAnalysis.industry_approach?.categories || 0) + (coverageAnalysis.discovered_approach?.categories || 0)} Total
                </div>
                <div className="text-sm text-green-600">Combined Approach</div>
                <div className="text-xs text-green-500">Comprehensive ODD Coverage</div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {allCoverageItems.map((item: CoverageCategory, index: number) => (
            <motion.div
              key={item.category}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className={`p-4 transition-all duration-300 hover:shadow-md border-l-4 ${
                item.type === 'discovered' ? 'border-l-purple-500 bg-gradient-to-br from-purple-50 to-blue-50' :
                'border-l-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50'
              }`}>
                {/* Apple-level clean header with unified badge layout */}
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-[var(--deep-charcoal)] flex-1 mr-4 min-w-0 truncate">
                    {item.category}
                  </h4>
                  {/* Unified badge container - no flex-wrap, properly contained */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <Badge
                      variant="outline"
                      className={`text-xs px-2 py-0.5 whitespace-nowrap ${
                        item.type === 'discovered' ? 'text-purple-600 border-purple-300 bg-purple-50' :
                        'text-blue-600 border-blue-300 bg-blue-50'
                      }`}
                    >
                      {item.type === 'discovered' ? 'AI' : 'Industry'}
                    </Badge>
                    {/* Dynamic Target - only for discovered categories */}
                    {item.type === 'discovered' && item.risk_adaptive_target && (
                      <Badge className="text-xs px-2 py-0.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0 whitespace-nowrap">
                        Dynamic
                      </Badge>
                    )}
                    {/* Priority Badge with proper color coding */}
                    <Badge
                      variant="outline"
                      className={`text-xs px-2 py-0.5 whitespace-nowrap ${
                        getPriorityLevel(item) === 'critical' ? 'text-red-600 border-red-300 bg-red-50' :
                        getPriorityLevel(item) === 'warning' ? 'text-amber-600 border-amber-300 bg-amber-50' :
                        'text-green-600 border-green-300 bg-green-50'
                      }`}
                    >
                      {item.hil_priority || item.status || 'normal'}
                    </Badge>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--slate-grey)]">
                      {item.type === 'discovered' ? 'Actual Scenes:' : 'Current:'}
                    </span>
                    <span className="font-medium">{item.actual_scenes || item.current || 0}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--slate-grey)]">Target:</span>
                    <div className="flex items-center gap-1">
                      <span className="font-medium">{item.risk_adaptive_target || item.target || 0}</span>
                      {item.risk_adaptive_target && (
                        <InfoTooltip
                          title="Risk-Adaptive Target"
                          description={`🛡️ Safety-Weighted Formula: Count × max(Uniqueness, Safety_Multiplier). Risk score: ${item.average_risk_score?.toFixed(2) || 0.5}. Critical scenarios (>0.8) use 100% testing (zero-skip policy). High risk (0.5-0.8) requires 80% minimum. Routine scenarios use uniqueness-based reduction. Target: ${item.risk_adaptive_target} scenes ensures safety-first training coverage.`}
                          size="sm"
                          position="auto"
                        />
                      )}
                    </div>
                  </div>
                  {item.type === 'discovered' && item.uniqueness_score && (
                    <div className="flex justify-between text-sm">
                      <span className="text-[var(--slate-grey)]">Uniqueness:</span>
                      <span className="font-medium text-purple-600">{(item.uniqueness_score * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>

                {/* Progress Bar */}
                <div className="mt-3">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs text-[var(--slate-grey)]">Coverage Progress</span>
                    <span className="text-xs font-medium">
                      {item.type === 'discovered' ?
                        `${Math.round((item.actual_scenes || 0) / Math.max(item.risk_adaptive_target || 1, 1) * 100)}%` :
                        `${item.percentage || 0}%`
                      }
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-1000 ${
                        item.type === 'discovered' ? 'bg-gradient-to-r from-purple-500 to-blue-500' :
                        'bg-gradient-to-r from-blue-500 to-indigo-500'
                      }`}
                      style={{
                        width: `${Math.min(
                          item.type === 'discovered' ?
                            ((item.actual_scenes || 0) / Math.max(item.risk_adaptive_target || 1, 1) * 100) :
                            (item.percentage || 0),
                          100
                        )}%`
                      }}
                    />
                  </div>
                </div>

                {/* Find Similar Button - Enhanced for Coverage Matrix */}
                {(getPriorityLevel(item) === 'critical' || getPriorityLevel(item) === 'warning') && (
                  <Button
                    size="sm"
                    variant="outline"
                    className={`w-full mt-3 text-xs transition-all duration-300 ${
                      getPriorityLevel(item) === 'critical'
                        ? 'border-red-300 text-red-600 hover:bg-red-50 hover:border-red-400'
                        : 'border-amber-300 text-amber-600 hover:bg-amber-50 hover:border-amber-400'
                    }`}
                    onClick={() => handleCoverageMatrixSimilar(item)}
                  >
                    <Search className="w-3 h-3 mr-1" />
                    Find Similar Scenes
                  </Button>
                )}
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Critical Gaps Alert */}
        {criticalGaps.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg"
          >
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <h4 className="font-medium text-red-800">Critical Training Gaps Identified</h4>
            </div>
            <p className="text-sm text-red-700 mb-3">
              {criticalGaps.length} scenario categories are severely underrepresented in your training dataset.
            </p>
            <div className="flex flex-wrap gap-2">
              {criticalGaps.map((gap: CoverageCategory) => (
                <Badge key={gap.category} variant="outline" className="text-red-600 border-red-300">
                  {gap.category}: {gap.percentage}% coverage
                </Badge>
              ))}
            </div>
          </motion.div>
        )}
      </Card>

      {/* 🧠 ODD DISCOVERY SECTION - Apple-Grade Intelligence */}
      <Card className="p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-[var(--cyber-blue)] rounded-lg flex items-center justify-center">
                <Brain className="w-4 h-4 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-[var(--deep-charcoal)]">
                ODD Discovery Intelligence
              </h3>
              <InfoTooltip
                title="Vector Similarity-Based ODD Discovery"
                description="Revolutionary approach to discovering natural Operational Design Domain categories through semantic vector analysis. Instead of predefined categories, we analyze actual driving scenarios using Cohere embed-v4 and Cosmos visual embeddings with S3 Vectors similarity search to discover organic scenario groupings. Each category is analyzed for similarity strength, uniqueness patterns, and DTO transfer value."
                calculation="🧠 Discovery Method: Creates vector embeddings for scene descriptions, uses similarity search (threshold ≥0.35) to find natural clusters. 📊 Quality Analysis: Measures category cohesion through similarity distribution patterns. 💰 Value Assessment: Calculates unique scene ratios and transfer costs per category for intelligent DTO optimization."
                size="sm"
                position="auto"
              />
            </div>

            {/* ODD Discovery Sync Badge */}
            {discoveryState.isRunning && (
              <div className="flex items-center gap-2 mt-2 mb-2">
                <Badge variant="outline" className="text-xs px-3 py-1 text-purple-600 border-purple-300 bg-purple-50">
                  <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                  Updating via Deep Discovery
                </Badge>
                <span className="text-xs text-purple-600">
                  Sync Progress: {discoveryState.progress}%
                </span>
              </div>
            )}

            <p className="text-[var(--slate-grey)]">
              Automatically discovered scenario categories through vector similarity analysis
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-sm px-3 py-1">
              {oddDiscoveryData.data?.total_scenes_analyzed || 0} scenes analyzed
            </Badge>
            <Badge variant="outline" className="text-xs px-3 py-1 text-purple-600 border-purple-300">
              Vector Similarity Analysis
            </Badge>
            {/* Discovery Trigger Button */}
            <Button
              onClick={triggerDiscovery}
              disabled={discoveryState.isRunning}
              size="sm"
              className={`transition-all duration-300 ${
                discoveryState.isRunning
                  ? 'bg-gradient-to-r from-purple-500 to-blue-500'
                  : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700'
              }`}
            >
              {discoveryState.isRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Discovering...
                </>
              ) : discoveryState.completed ? (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Rediscover
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Deep Discovery
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Discovery Progress Banner */}
        {discoveryState.isRunning && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-5 h-5 text-purple-600 animate-spin" />
                <span className="font-medium text-purple-800">
                  ODD Discovery in Progress
                </span>
                <Badge variant="outline" className="text-xs px-2 py-1 text-purple-600 border-purple-300">
                  {discoveryState.progress}%
                </Badge>
              </div>
              <div className="text-sm text-purple-600">
                Job ID: {discoveryState.currentJobId}
              </div>
            </div>
            <div className="mb-2">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm text-purple-700">
                  {discoveryState.currentStep}
                </span>
                <span className="text-sm font-medium text-purple-600">
                  {discoveryState.progress}%
                </span>
              </div>
              <div className="h-2 bg-purple-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
                  style={{ width: `${discoveryState.progress}%` }}
                />
              </div>
            </div>
            <p className="text-xs text-purple-600">
              Performing HDBSCAN clustering and intelligent naming - estimated 2-5 minutes
            </p>
          </motion.div>
        )}

        {/* Discovery Error Banner */}
        {discoveryState.error && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <span className="font-medium text-red-800">Discovery Failed</span>
            </div>
            <p className="text-sm text-red-700 mb-3">{discoveryState.error}</p>
            <Button
              onClick={triggerDiscovery}
              size="sm"
              variant="outline"
              className="text-red-600 border-red-300 hover:bg-red-50"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry Discovery
            </Button>
          </motion.div>
        )}

        {/* Loading State */}
        {oddDiscoveryData.loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-40 bg-gray-100 rounded-xl"></div>
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {oddDiscoveryData.error && (
          <div className="text-center py-12">
            <AlertTriangle className="w-12 h-12 mx-auto text-amber-500 mb-4" />
            <p className="text-[var(--slate-grey)] mb-2">Unable to load ODD discovery data</p>
            <p className="text-sm text-gray-500">{oddDiscoveryData.error}</p>
          </div>
        )}

        {/* ODD Categories Grid */}
        {oddDiscoveryData.data?.uniqueness_results && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {oddDiscoveryData.data?.uniqueness_results?.map((category: OddCategory, index: number) => (
                <motion.div
                  key={category.category}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <Card className={`p-5 transition-all duration-300 hover:shadow-lg border-l-4 ${
                    category.uniqueness_quality === 'excellent' ? 'border-l-green-500 bg-green-50' :
                    category.uniqueness_quality === 'good' ? 'border-l-blue-500 bg-blue-50' :
                    category.uniqueness_quality === 'moderate' ? 'border-l-amber-500 bg-amber-50' :
                    'border-l-red-500 bg-red-50'
                  }`}>
                    {/* Category Header */}
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold text-[var(--deep-charcoal)] capitalize">
                        {category.category.replace(/_/g, ' ')}
                      </h4>
                      <Badge className={`text-xs px-2 py-1 ${
                        category.uniqueness_quality === 'excellent' ? 'bg-green-100 border-green-300 text-green-700' :
                        category.uniqueness_quality === 'good' ? 'bg-blue-100 border-blue-300 text-blue-700' :
                        category.uniqueness_quality === 'moderate' ? 'bg-amber-100 border-amber-300 text-amber-700' :
                        'bg-red-100 border-red-300 text-red-700'
                      }`}>
                        {category.uniqueness_quality}
                      </Badge>
                    </div>

                    {/* Key Metrics */}
                    <div className="space-y-3 mb-4">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-[var(--slate-grey)] flex items-center gap-1">
                          <Target className="w-3 h-3" />
                          Total Scenes:
                          <InfoTooltip
                            title="Total Scenes (Category)"
                            description="Number of driving scenarios in this specific ODD category, discovered through vector similarity analysis. Each scene represents a unique driving situation that was classified as belonging to this category based on semantic similarity."
                            calculation="Found by querying S3 Vectors with this category's concept description using Cohere embed-v4 embeddings. Scenes with ≥35% similarity to the category concept are included."
                            size="sm"
                            position="auto"
                          />
                        </span>
                        <span className="font-medium">{category.total_scenes}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-[var(--slate-grey)] flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          Unique Scenes:
                          <InfoTooltip
                            title="Unique Scenes"
                            description="Estimated number of truly unique driving scenarios within this category after removing similar/redundant scenes. Uses vector similarity analysis to identify scenes that are too similar to each other (potential training data redundancy)."
                            calculation="🛡️ Safety-Weighted Uniqueness Analysis: Safety-first approach prevents dangerous similarity-based reduction on critical scenarios. Critical risk (>0.8): 100% uniqueness assumed - no skipping for safety. High risk (0.5-0.8): Minimum 80% testing required. Routine scenarios (<0.5): Traditional uniqueness calculation using similarity patterns. Formula adapted for safety: Count × max(Similarity_Uniqueness, Safety_Override_Multiplier)"
                            size="sm"
                            position="auto"
                          />
                        </span>
                        <span className="font-medium text-[var(--cyber-blue)]">
                          {category.estimated_unique_scenes.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-[var(--slate-grey)] flex items-center gap-1">
                          <DollarSign className="w-3 h-3" />
                          DTO Value:
                          <InfoTooltip
                            title="DTO Value (Category)"
                            description="Estimated cost to transfer only the unique, valuable scenes from this category. Represents the intelligent approach of transferring only non-redundant scenarios instead of all collected data."
                            calculation="🛡️ Safety-Weighted DTO Calculation: Uses safety-first target calculation instead of blind uniqueness reduction. Critical risk scenarios (>0.8): All scenes transferred regardless of similarity (safety override). High risk (0.5-0.8): Minimum 80% transferred. Routine scenarios: Traditional uniqueness-based reduction. Formula: Safety_Weighted_Target × $30/scene. Prevents dangerous cost-cutting on safety-critical scenarios while optimizing routine transfers."
                            size="sm"
                            position="auto"
                          />
                        </span>
                        <span className="font-semibold text-green-600">
                          ${category.dto_value_estimate}
                        </span>
                      </div>
                    </div>

                    {/* Uniqueness Progress Bar */}
                    <div className="mb-4">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs text-[var(--slate-grey)] flex items-center gap-1">
                          Uniqueness Score
                          <InfoTooltip
                            title="Uniqueness Score"
                            description="Percentage indicating how diverse and non-redundant the scenes are within this category. Higher scores mean more valuable training data with less redundancy and better coverage of edge cases."
                            calculation="🛡️ Safety-Weighted Uniqueness Score: Calculated using safety-first methodology that prevents dangerous reduction on critical scenarios. Critical risk (>0.8): Fixed 100% uniqueness (safety override). High risk (0.5-0.8): Minimum 80% uniqueness floor. Routine scenarios: Traditional similarity-based calculation. Formula adapts for safety: max(Similarity_Based_Uniqueness, Safety_Floor_Multiplier) × 100%"
                            size="sm"
                            position="auto"
                          />
                        </span>
                        <span className="text-xs font-medium">
                          {(category.uniqueness_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-1000 ${
                            category.uniqueness_quality === 'excellent' ? 'bg-green-500' :
                            category.uniqueness_quality === 'good' ? 'bg-blue-500' :
                            category.uniqueness_quality === 'moderate' ? 'bg-amber-500' :
                            'bg-red-500'
                          }`}
                          style={{ width: `${category.uniqueness_score * 100}%` }}
                        />
                      </div>
                    </div>

                    {/* Similarity Distribution Mini-Chart */}
                    <div className="mb-3">
                      <div className="flex items-center gap-1 mb-2">
                        <span className="text-xs text-[var(--slate-grey)] font-medium">Similarity Distribution</span>
                        <InfoTooltip
                          title="Similarity Distribution"
                          description="Shows how similar scenes are to the core concept of this category. High Sim = very typical examples of the category (potentially more redundant). Low Sim = edge cases within the category that are still related but more unique (higher training value)."
                          calculation="High Sim: ≥60% similarity to category concept (potentially redundant). Med Sim: 40-60% similarity (moderate uniqueness). Low Sim: 35-40% similarity (likely unique edge cases). Based on Cohere embed-v4 vector embeddings comparing scene descriptions to category definition using cosine similarity."
                          size="sm"
                          position="auto"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div className="text-center">
                          <div className="text-red-600 font-medium">
                            {category.similarity_distribution.high_similarity_count}
                          </div>
                          <div className="text-gray-500">High Sim</div>
                        </div>
                        <div className="text-center">
                          <div className="text-amber-600 font-medium">
                            {category.similarity_distribution.medium_similarity_count}
                          </div>
                          <div className="text-gray-500">Med Sim</div>
                        </div>
                        <div className="text-center">
                          <div className="text-green-600 font-medium">
                            {category.similarity_distribution.low_similarity_count}
                          </div>
                          <div className="text-gray-500">Low Sim</div>
                        </div>
                      </div>
                    </div>

                    {/* Find Similar Button for ODD Discovered Categories */}
                    {(category.uniqueness_quality === 'excellent' || category.uniqueness_quality === 'good') && (
                      <Button
                        variant="outline"
                        size="sm"
                        className={`w-full mt-4 text-xs transition-all duration-300 ${
                          category.uniqueness_quality === 'excellent'
                            ? 'border-green-300 text-green-600 hover:bg-green-50 hover:border-green-400'
                            : 'border-blue-300 text-blue-600 hover:bg-blue-50 hover:border-blue-400'
                        }`}
                        onClick={() => handleOddDiscoverySimilar(category)}
                      >
                        <Search className="w-3 h-3 mr-1" />
                        Find Similar Scenes
                      </Button>
                    )}
                  </Card>
                </motion.div>
              ))}
            </div>

            {/* DTO Savings Summary */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-br from-green-50 to-emerald-100 border border-green-200 rounded-xl p-6"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
                  <DollarSign className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h4 className="font-semibold text-green-800">Intelligent DTO Savings Analysis</h4>
                  <p className="text-sm text-green-700">
                    Vector similarity-based cost optimization vs naive approach
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-800">
                    ${oddDiscoveryData.data?.dto_savings_estimate?.estimated_savings_usd?.toLocaleString() ?? 0}
                  </div>
                  <div className="flex items-center justify-center gap-1 text-sm text-green-600">
                    <span>Total Savings</span>
                    <InfoTooltip
                      title="Total Savings (Cost Difference)"
                      description="Cost difference between transferring all scenes versus transferring only unique, valuable scenes identified through HDBSCAN clustering and vector similarity analysis."
                      calculation="🛡️ Safety-Weighted Savings Calculation: Naive Cost (all scenes × $30) minus Safety-Weighted Cost (safety-targeted scenes × $30). Safety-weighted approach uses risk-adaptive targets: Critical scenarios (>0.8) get 100% testing (zero-skip policy), High risk (0.5-0.8) get minimum 80%, Routine scenarios use similarity reduction. Saves money while maintaining safety standards - no dangerous cost-cutting on critical scenarios."
                      size="sm"
                      position="bottom"
                    />
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-800">
                    {oddDiscoveryData.data?.dto_savings_estimate?.efficiency_gain_percent?.toFixed(1) ?? 0}%
                  </div>
                  <div className="flex items-center justify-center gap-1 text-sm text-green-600">
                    <span>Efficiency Gain</span>
                    <InfoTooltip
                      title="Efficiency Gain (Percentage Improvement)"
                      description="How much more efficient our intelligent approach is compared to the naive 'transfer everything' approach. Higher percentages mean bigger cost savings and better resource utilization."
                      calculation="📊 Calculation Method: (Total Savings ÷ Naive Cost) × 100% = Efficiency Gain. Example: ($3,891 savings ÷ $14,100 naive cost) = 27.6% efficiency improvement. This means we're spending 27.6% less money while getting the same training value by avoiding redundant scenario transfers."
                      size="sm"
                      position="bottom"
                    />
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-medium text-gray-700">
                    ${oddDiscoveryData.data?.dto_savings_estimate?.naive_cost_usd?.toLocaleString() ?? 0}
                  </div>
                  <div className="flex items-center justify-center gap-1 text-sm text-gray-500">
                    <span>Naive Cost</span>
                    <InfoTooltip
                      title="Naive Cost (Transfer Everything)"
                      description="The cost of the old-fashioned approach: transferring ALL driving scenarios from vehicles to training teams without any intelligence or filtering. This wastes money on redundant data that doesn't improve AI training."
                      calculation="🚫 Wasteful Approach: Total Scenes × $30/scene = Total Naive Cost. Example: 470 scenes × $30 = $14,100. The $30 includes: • Manual data curation labor (~$20/scene) • AWS data transfer costs (~$5/scene) • Storage and processing costs (~$5/scene). Without intelligence, you pay full price for redundant scenarios that don't add training value."
                      size="sm"
                      position="bottom"
                    />
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-medium text-green-700">
                    ${oddDiscoveryData.data?.dto_savings_estimate?.intelligent_cost_usd?.toLocaleString() ?? 0}
                  </div>
                  <div className="flex items-center justify-center gap-1 text-sm text-green-600">
                    <span>Intelligent Cost</span>
                    <InfoTooltip
                      title="Intelligent Cost (Smart Transfer)"
                      description="The cost of our AI-powered approach: only transferring unique, valuable driving scenarios that actually improve autonomous vehicle training. We use vector similarity analysis to identify and skip redundant scenarios."
                      calculation="🛡️ Safety-Weighted Smart Approach: Uses safety-first target calculation instead of blind uniqueness reduction. Formula: Safety_Weighted_Target_Scenes × $30/scene = Intelligent Cost. Critical risk scenarios (>0.8): All transferred (safety override - no skipping). High risk (0.5-0.8): Minimum 80% transferred. Routine scenarios: Traditional similarity-based reduction. Maintains training quality while preventing dangerous cost-cutting on safety-critical edge cases."
                      size="sm"
                      position="bottom"
                    />
                  </div>
                </div>
              </div>

              <div className="mt-4 text-center">
                <div className="inline-block">
                  <Badge className="bg-green-200 border-green-300 text-green-800 px-4 py-2 flex items-center gap-2">
                    <span>🧠 Uniqueness Ratio: {((oddDiscoveryData.data?.overall_uniqueness_ratio ?? 0) * 100).toFixed(1)}%
                    ({oddDiscoveryData.data?.total_unique_scenes_estimated?.toFixed(1) ?? 0}/{oddDiscoveryData.data?.total_scenes_analyzed ?? 0} scenes)</span>
                    <InfoTooltip
                      title="Uniqueness Ratio (Overall)"
                      description="Overall percentage of scenarios that are estimated to be unique and valuable for training, across all discovered ODD categories. Higher ratios indicate a more diverse, less redundant dataset."
                      calculation="Total Unique Scenes / Total Scenes × 100% = 340.3/470 × 100% = 72.4%"
                      size="sm"
                      position="top"
                    />
                  </Badge>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </Card>
      </div>
    </DashboardLayout>
    </ProtectedRoute>
  )
}