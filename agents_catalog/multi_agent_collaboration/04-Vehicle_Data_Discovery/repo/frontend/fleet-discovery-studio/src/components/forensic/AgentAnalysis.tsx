"use client"

import { motion } from "framer-motion"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Brain,
  Search,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  Users,
  Building2,
  Eye
} from "lucide-react"

interface AgentAnalysisProps {
  sceneData: {
    scene_understanding?: {
      summary: string
      key_findings: string[]
      behavioral_insights: string[]
    }
    anomaly_analysis?: {
      detected: boolean  // Legacy field (keep for compatibility)
      risk_level: string
      description: string
      classification?: {
        anomaly_type?: string
        hil_testing_value?: string
        investment_priority?: string
        training_gap_addressed?: string
      }
      metrics: { [key: string]: number }
    }
    anomaly_status?: 'CRITICAL' | 'DEVIATION' | 'NORMAL'  // Apple-grade 3-tier system
    intelligence_insights?: {
      business_impact: string
      training_value: string
      recommendations: string[]
    }
  }
}

const AnalysisSection = ({
  title,
  icon: Icon,
  color,
  children,
  delay = 0
}: {
  title: string
  icon: any
  color: string
  children: React.ReactNode
  delay?: number
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.4 }}
  >
    <Card className="p-6 bg-[var(--pure-white)] border-gray-200 hover:shadow-lg transition-shadow duration-300">
      <div className="flex items-center gap-3 mb-4">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: `${color}15` }}
        >
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        <div>
          <h3 className="font-semibold text-[var(--deep-charcoal)]">{title}</h3>
          <div className="flex items-center gap-1 mt-1">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }}></div>
            <span className="text-xs text-[var(--slate-grey)]">AI Analysis</span>
          </div>
        </div>
      </div>
      {children}
    </Card>
  </motion.div>
)

export default function AgentAnalysis({ sceneData }: AgentAnalysisProps) {
  // Clean and format agent responses for display (NO TRUNCATION - full text display)
  const cleanAgentText = (value: any): string => {
    if (typeof value === 'string') {
      // Clean up obvious JSON artifacts but keep full text
      let cleaned = value
        .replace(/^\{.*?\}$/g, '') // Remove if it's pure JSON
        .replace(/^"(.*)"$/, '$1')  // Remove quotes around strings
        .replace(/\\"/g, '"')       // Unescape quotes
        .trim()

      return cleaned
    }
    if (value === null || value === undefined) return ''
    if (typeof value === 'object') return 'Complex data structure'
    return String(value)
  }

  // Defensive function to ensure all values are clean strings
  const safeString = (value: any): string => {
    return cleanAgentText(value)
  }

  // Ensure all arrays contain only clean strings (NO TRUNCATION - full text display)
  const safeArray = (arr: any[]): string[] => {
    if (!Array.isArray(arr)) return []
    return arr
      .map(item => cleanAgentText(item)) // No truncation - full text display
      .filter(item => item.trim().length > 0)
      .slice(0, 10) // Allow more items since no truncation
  }

  // Smart color analysis based on content sentiment/severity
  const getSemanticColor = (text: string, field: string): { primary: string, bg: string, border: string } => {
    if (!text) return { primary: '#64748b', bg: '#f8fafc', border: '#e2e8f0' }

    const lowerText = text.toLowerCase()

    // Comprehensive semantic keywords based on real agent language patterns
    const criticalKeywords = [
      'critical', 'urgent', 'high priority', 'major gaps', 'severe', 'significant deficiency',
      'immediate attention', 'substantial improvement', 'concerning', 'problematic',
      'critical gaps', 'significant gaps', 'serious gaps', 'substantial gaps',
      'immediate need', 'high risk', 'major deficiency', 'critical training gaps'
    ]

    const warningKeywords = [
      'medium', 'moderate', 'some gaps', 'areas for improvement', 'enhancement needed',
      'partial', 'limited', 'could benefit', 'opportunities', 'considerations',
      // Real agent language patterns from your examples
      'additional training data', 'could help', 'would help', 'could be beneficial',
      'mildly beneficial', 'moderately beneficial', 'reinforcement', 'enhancement',
      'improvement', 'address gaps', 'help address', 'additional', 'supplemental',
      'could improve', 'would improve', 'beneficial', 'valuable', 'useful',
      'worthwhile', 'recommended', 'suggested', 'advisable', 'training gaps',
      'gaps in', 'room for improvement', 'potential improvement'
    ]

    const positiveKeywords = [
      'low', 'well-established', 'no gaps', 'sufficient', 'adequate', 'good', 'excellent',
      'normal', 'baseline', 'standard', 'meets requirements', 'no significant',
      // Real agent patterns for minimal/no gaps
      'not explicitly flagged', 'no significant gaps', 'adequately covers', 'well covered',
      'existing data covers', 'baseline coverage', 'sufficiently covered', 'already adequate',
      'no critical gaps', 'minimal gaps', 'not flagged', 'adequately addressed',
      'existing training', 'well represented', 'sufficient coverage'
    ]

    // Priority-based context checking - check positive first for priority/value contexts
    const startsWithPositive = lowerText.startsWith('low') || lowerText.startsWith('good') || lowerText.startsWith('excellent')
    const startsWithCritical = lowerText.startsWith('high') || lowerText.startsWith('critical') || lowerText.startsWith('urgent')
    const startsWithWarning = lowerText.startsWith('medium') || lowerText.startsWith('moderate')

    // Prioritize sentence start context (most important indicator)
    if (startsWithPositive) {
      return { primary: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' }
    }

    if (startsWithCritical) {
      return { primary: '#dc2626', bg: '#fef2f2', border: '#fecaca' }
    }

    if (startsWithWarning) {
      return { primary: '#d97706', bg: '#fffbeb', border: '#fed7aa' }
    }

    // Fallback to keyword matching for non-priority contexts
    if (criticalKeywords.some(keyword => lowerText.includes(keyword))) {
      return { primary: '#dc2626', bg: '#fef2f2', border: '#fecaca' }
    }

    if (warningKeywords.some(keyword => lowerText.includes(keyword))) {
      return { primary: '#d97706', bg: '#fffbeb', border: '#fed7aa' }
    }

    if (positiveKeywords.some(keyword => lowerText.includes(keyword))) {
      return { primary: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' }
    }

    // Field-specific defaults when no clear sentiment
    switch (field) {
      case 'hil_testing_value':
        return { primary: '#0ea5e9', bg: '#f0f9ff', border: '#bae6fd' }
      case 'investment_priority':
        return { primary: '#d97706', bg: '#fffbeb', border: '#fed7aa' }
      case 'training_gap_addressed':
        return { primary: '#64748b', bg: '#f8fafc', border: '#e2e8f0' }
      default:
        return { primary: '#64748b', bg: '#f8fafc', border: '#e2e8f0' }
    }
  }

  // Check if all analysis data is missing
  const hasNoData = !sceneData.scene_understanding &&
                    !sceneData.anomaly_analysis &&
                    !sceneData.intelligence_insights

  // Debug logging
  console.log("🧪 AgentAnalysis receiving data:");
  console.log("scene_understanding:", JSON.stringify(sceneData.scene_understanding, null, 2));
  console.log("key_findings type:", typeof sceneData.scene_understanding?.key_findings);
  console.log("key_findings value:", sceneData.scene_understanding?.key_findings);
  console.log("behavioral_insights type:", typeof sceneData.scene_understanding?.behavioral_insights);
  console.log("behavioral_insights value:", sceneData.scene_understanding?.behavioral_insights);
  console.log("summary type:", typeof sceneData.scene_understanding?.summary);
  console.log("summary value:", sceneData.scene_understanding?.summary);
  console.log("hasNoData:", hasNoData);

  // Show fallback UI when no agent analysis data is available
  if (hasNoData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--deep-charcoal)]">
            AI Agent Analysis
          </h2>
          <Badge variant="outline" className="bg-[var(--slate-grey)]/10 text-[var(--slate-grey)] border-[var(--slate-grey)]/20">
            <Brain className="w-3 h-3 mr-1" />
            Analysis Pending
          </Badge>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="p-8 bg-[var(--pure-white)] border-gray-200 text-center">
            <div className="w-16 h-16 bg-[var(--slate-grey)]/10 rounded-xl flex items-center justify-center mx-auto mb-4">
              <Brain className="w-8 h-8 text-[var(--slate-grey)]" />
            </div>
            <h3 className="text-lg font-semibold text-[var(--deep-charcoal)] mb-2">
              Agent Analysis In Progress
            </h3>
            <p className="text-[var(--slate-grey)] leading-relaxed max-w-md mx-auto">
              This scene is currently being processed by our 3-agent system. Analysis results will be available shortly.
            </p>
            <div className="flex justify-center mt-6 space-x-6 text-sm text-[var(--slate-grey)]">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-[var(--slate-grey)]/30 rounded-full"></div>
                Scene Understanding
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-[var(--slate-grey)]/30 rounded-full"></div>
                Anomaly Detection
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-[var(--slate-grey)]/30 rounded-full"></div>
                Intelligence Gathering
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--deep-charcoal)]">
          AI Agent Analysis
        </h2>
        <Badge variant="outline" className="bg-[var(--cyber-blue)]/10 text-[var(--cyber-blue)] border-[var(--cyber-blue)]/20">
          <Brain className="w-3 h-3 mr-1" />
          3-Agent System
        </Badge>
      </div>

      {/* Scene Understanding Agent */}
      {sceneData.scene_understanding && (
        <AnalysisSection
          title="Scene Understanding Agent"
          icon={Eye}
          color="var(--cyber-blue)"
          delay={0}
        >
          <div className="space-y-4">
            {/* Summary */}
            <div className="p-4 bg-[var(--soft-grey)] rounded-lg">
              <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-2">
                Scene Analysis Summary
              </h4>
              <p className="text-sm text-[var(--slate-grey)] leading-relaxed">
                {(() => {
                  const summaryValue = sceneData.scene_understanding?.summary
                  console.log(" Summary value before safeString:", summaryValue, typeof summaryValue)
                  const safeSummary = safeString(summaryValue)
                  console.log(" Summary after safeString:", safeSummary, typeof safeSummary)
                  return safeSummary
                })()}
              </p>
            </div>

            {/* Key Findings */}
            {(() => {
              const safeKeyFindings = safeArray(sceneData.scene_understanding.key_findings || [])
              return safeKeyFindings.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                    Key Findings
                  </h4>
                  <ul className="space-y-2">
                    {safeKeyFindings.map((finding, index) => (
                      <motion.li
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.1 + index * 0.05 }}
                        className="flex items-start gap-2 text-sm"
                      >
                        <CheckCircle className="w-4 h-4 text-[var(--success-green)] mt-0.5 flex-shrink-0" />
                        <span className="text-[var(--slate-grey)]">{finding}</span>
                      </motion.li>
                    ))}
                  </ul>
                </div>
              )
            })()}

            {/* Behavioral Insights */}
            {(() => {
              const safeBehavioralInsights = safeArray(sceneData.scene_understanding.behavioral_insights || [])
              return safeBehavioralInsights.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                    Behavioral Insights
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {safeBehavioralInsights.map((insight, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="bg-[var(--cyber-blue)]/5 text-[var(--cyber-blue)] border-[var(--cyber-blue)]/20 max-w-full break-words whitespace-normal"
                        style={{
                          wordBreak: 'break-word',
                          overflowWrap: 'break-word',
                          hyphens: 'auto'
                        }}
                      >
                        <Users className="w-3 h-3 mr-1 flex-shrink-0" />
                        <span className="flex-1 text-wrap">{insight}</span>
                      </Badge>
                    ))}
                  </div>
                </div>
              )
            })()}
          </div>
        </AnalysisSection>
      )}

      {/* Anomaly Detection Agent */}
      {sceneData.anomaly_analysis && (
        <AnalysisSection
          title="Anomaly Detection Agent"
          icon={AlertTriangle}
          color={
            sceneData.anomaly_status === "CRITICAL" ? "var(--safety-orange)" :
            sceneData.anomaly_status === "DEVIATION" ? "var(--warning-amber)" :
            "var(--success-green)"
          }
          delay={0.1}
        >
          <div className="space-y-4">
            {/* Apple-Grade 3-Tier Status */}
            <div className={`p-4 rounded-lg ${
              sceneData.anomaly_status === "CRITICAL" ? "bg-red-500/10" :
              sceneData.anomaly_status === "DEVIATION" ? "bg-amber-500/10" :
              "bg-[var(--success-green)]/10"
            }`}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-[var(--deep-charcoal)]">
                  Anomaly Status
                </h4>
                {/* Apple-Grade 3-Tier Badge */}
                {sceneData.anomaly_status === "CRITICAL" && (
                  <Badge className="bg-red-500 border-red-500 text-white font-medium animate-pulse">
                    🔴 CRITICAL
                  </Badge>
                )}
                {sceneData.anomaly_status === "DEVIATION" && (
                  <Badge className="bg-amber-500 border-amber-500 text-white font-medium">
                    🟡 DEVIATION
                  </Badge>
                )}
                {sceneData.anomaly_status === "NORMAL" && (
                  <Badge className="bg-[var(--success-green)] border-[var(--success-green)] text-white font-medium">
                    🟢 NORMAL
                  </Badge>
                )}
              </div>
              <p className="text-sm text-[var(--slate-grey)]">
                Classification: <span className="font-medium">
                  {sceneData.anomaly_status === "CRITICAL" ? "Requires immediate attention" :
                   sceneData.anomaly_status === "DEVIATION" ? "Interesting variance detected" :
                   "Standard driving behavior"}
                </span>
              </p>
            </div>


            {/* Description */}
            {sceneData.anomaly_analysis.description && (
              <div>
                <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-2">
                  Analysis Description
                </h4>
                <p className="text-sm text-[var(--slate-grey)] leading-relaxed">
                  {safeString(sceneData.anomaly_analysis.description)}
                </p>
              </div>
            )}

            {/* Classification Analysis */}
            {sceneData.anomaly_analysis.classification && Object.values(sceneData.anomaly_analysis.classification).some(val => val && String(val).trim()) && (
              <div>
                <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                  Classification Analysis
                </h4>
                <div className="space-y-3">
                  {sceneData.anomaly_analysis.classification.anomaly_type && (
                    <div className="p-3 bg-[var(--soft-grey)] rounded-lg">
                      <div className="text-xs text-[var(--slate-grey)] uppercase tracking-wide mb-1">
                        Scenario Type
                      </div>
                      <div className="text-sm text-[var(--deep-charcoal)] font-medium">
                        {safeString(sceneData.anomaly_analysis.classification.anomaly_type)}
                      </div>
                    </div>
                  )}
                  {sceneData.anomaly_analysis.classification.hil_testing_value && (() => {
                    const colors = getSemanticColor(sceneData.anomaly_analysis.classification.hil_testing_value, 'hil_testing_value')
                    return (
                      <div className="p-3 rounded-lg border-2" style={{ backgroundColor: colors.bg, borderColor: colors.border }}>
                        <div className="text-xs uppercase tracking-wide mb-1 font-medium" style={{ color: colors.primary }}>
                          HIL Testing Value
                        </div>
                        <div className="text-sm text-[var(--deep-charcoal)] leading-relaxed">
                          {safeString(sceneData.anomaly_analysis.classification.hil_testing_value)}
                        </div>
                      </div>
                    )
                  })()}
                  {sceneData.anomaly_analysis.classification.investment_priority && (() => {
                    const colors = getSemanticColor(sceneData.anomaly_analysis.classification.investment_priority, 'investment_priority')
                    return (
                      <div className="p-3 rounded-lg border-2" style={{ backgroundColor: colors.bg, borderColor: colors.border }}>
                        <div className="text-xs uppercase tracking-wide mb-1 font-medium" style={{ color: colors.primary }}>
                          Investment Priority
                        </div>
                        <div className="text-sm text-[var(--deep-charcoal)] leading-relaxed">
                          {safeString(sceneData.anomaly_analysis.classification.investment_priority)}
                        </div>
                      </div>
                    )
                  })()}
                  {sceneData.anomaly_analysis.classification.training_gap_addressed && (() => {
                    const colors = getSemanticColor(sceneData.anomaly_analysis.classification.training_gap_addressed, 'training_gap_addressed')
                    return (
                      <div className="p-3 rounded-lg border-2" style={{ backgroundColor: colors.bg, borderColor: colors.border }}>
                        <div className="text-xs uppercase tracking-wide mb-1 font-medium" style={{ color: colors.primary }}>
                          Training Gap Analysis
                        </div>
                        <div className="text-sm text-[var(--deep-charcoal)] leading-relaxed">
                          {safeString(sceneData.anomaly_analysis.classification.training_gap_addressed)}
                        </div>
                      </div>
                    )
                  })()}
                </div>
              </div>
            )}

            {/* Metrics */}
            {sceneData.anomaly_analysis.metrics && Object.keys(sceneData.anomaly_analysis.metrics).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                  Performance Metrics (Phase 3 Analysis)
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(sceneData.anomaly_analysis.metrics).map(([key, value]) => {
                    // Skip business_intelligence object and non-numeric metrics
                    if (key === 'business_intelligence' || key === 'visual_evidence_summary') return null

                    // Define user-friendly labels and descriptions
                    const metricInfo = {
                      'risk_score': {
                        label: 'Risk Score',
                        description: 'Overall safety risk assessment',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.5 ? 'text-red-600' : val > 0.3 ? 'text-yellow-600' : 'text-green-600'
                      },
                      'safety_score': {
                        label: 'Safety Score',
                        description: 'Driving safety performance',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.8 ? 'text-green-600' : val > 0.6 ? 'text-yellow-600' : 'text-red-600'
                      },
                      'speed_compliance': {
                        label: 'Speed Compliance',
                        description: 'Adherence to speed limits',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.8 ? 'text-green-600' : val > 0.6 ? 'text-yellow-600' : 'text-red-600'
                      },
                      'lane_positioning_quality': {
                        label: 'Lane Position Quality',
                        description: 'Quality of lane keeping',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.8 ? 'text-green-600' : val > 0.6 ? 'text-yellow-600' : 'text-red-600'
                      },
                      'behavioral_complexity_score': {
                        label: 'Scenario Complexity',
                        description: 'Driving scenario difficulty',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.7 ? 'text-red-600' : val > 0.4 ? 'text-yellow-600' : 'text-green-600'
                      },
                      'confidence_score': {
                        label: 'Analysis Confidence',
                        description: 'AI analysis reliability',
                        format: (val: number) => `${(val * 100).toFixed(0)}%`,
                        color: (val: number) => val > 0.8 ? 'text-green-600' : val > 0.6 ? 'text-yellow-600' : 'text-red-600'
                      }
                    }

                    const info = (metricInfo as any)[key] || {
                      label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                      description: 'Performance metric',
                      format: (val: number) => val.toFixed(3),
                      color: () => 'text-[var(--deep-charcoal)]'
                    }

                    if (typeof value !== 'number') return null

                    return (
                      <div key={key} className="p-3 bg-[var(--soft-grey)] rounded-lg">
                        <div className="text-xs text-[var(--slate-grey)] uppercase tracking-wide mb-1">
                          {info.label}
                        </div>
                        <div className={`text-lg font-bold mt-1 ${info.color(value)}`}>
                          {info.format(value)}
                        </div>
                        <div className="text-xs text-[var(--slate-grey)] mt-1">
                          {info.description}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </AnalysisSection>
      )}

      {/* Intelligence Gathering Agent */}
      {sceneData.intelligence_insights && (
        <AnalysisSection
          title="Intelligence Gathering Agent"
          icon={Search}
          color="var(--warning-amber)"
          delay={0.2}
        >
          <div className="space-y-4">
            {/* Business Impact */}
            {sceneData.intelligence_insights.business_impact && (
              <div className="p-4 bg-[var(--warning-amber)]/10 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Building2 className="w-4 h-4 text-[var(--warning-amber)]" />
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)]">
                    Business Impact Assessment
                  </h4>
                </div>
                <p className="text-sm text-[var(--slate-grey)] leading-relaxed">
                  {safeString(sceneData.intelligence_insights.business_impact)}
                </p>
              </div>
            )}

            {/* Training Value */}
            {sceneData.intelligence_insights.training_value && (
              <div className="p-4 bg-[var(--success-green)]/10 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-[var(--success-green)]" />
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)]">
                    Training Data Value
                  </h4>
                </div>
                <p className="text-sm text-[var(--slate-grey)] leading-relaxed">
                  {safeString(sceneData.intelligence_insights.training_value)}
                </p>
              </div>
            )}

            {/* Recommendations */}
            {(() => {
              const safeRecommendations = safeArray(sceneData.intelligence_insights.recommendations || [])
              return safeRecommendations.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                    AI Recommendations
                  </h4>
                  <ul className="space-y-2">
                    {safeRecommendations.map((rec, index) => (
                      <motion.li
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.3 + index * 0.05 }}
                        className="flex items-start gap-2 text-sm"
                      >
                        <div className="w-5 h-5 bg-[var(--warning-amber)]/20 rounded-full flex items-center justify-center mt-0.5 flex-shrink-0">
                          <span className="text-xs font-medium text-[var(--warning-amber)]">
                            {index + 1}
                          </span>
                        </div>
                        <span className="text-[var(--slate-grey)]">{rec}</span>
                      </motion.li>
                    ))}
                  </ul>
                </div>
              )
            })()}
          </div>
        </AnalysisSection>
      )}
    </div>
  )
}