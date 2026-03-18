/**
 * MetricsPanel - Scene Metrics Display
 * 
 * Shows risk score, safety score, and anomaly status for a scene
 * using radial charts and color-coded indicators.
 */
"use client"

import { Card } from "@/components/ui/card"
import InfoTooltip from "@/components/ui/InfoTooltip"
import { getMetricDefinition } from "@/lib/metricDefinitions"
import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer
} from "recharts"
import {
  Shield,
  AlertTriangle,
  Activity
} from "lucide-react"

interface MetricsPanelProps {
  sceneData: {
    risk_score: number
    safety_score: number
    anomaly_detected: boolean  // Legacy field (keep for compatibility)
    anomaly_status: 'CRITICAL' | 'DEVIATION' | 'NORMAL'  // Apple-grade 3-tier system
    anomaly_analysis?: {
      risk_level: string
      metrics: { [key: string]: number }
    }
  }
}

export default function MetricsPanel({ sceneData }: MetricsPanelProps) {
  const riskData = [
    {
      name: "Risk",
      value: sceneData.risk_score * 100,
      fill: sceneData.risk_score >= 0.7 ? "var(--safety-orange)" :
            sceneData.risk_score >= 0.4 ? "var(--warning-amber)" : "var(--success-green)"
    }
  ]

  const safetyData = [
    {
      name: "Safety",
      value: sceneData.safety_score * 100,
      fill: "var(--success-green)"
    }
  ]


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--deep-charcoal)]">
          Risk Assessment
        </h2>
        {/* Apple-Grade 3-Tier Status Display */}
        {sceneData.anomaly_status === "CRITICAL" && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-red-500/10 text-red-600 animate-pulse">
            <AlertTriangle className="w-4 h-4" />
            🔴 Critical Analysis
          </div>
        )}
        {sceneData.anomaly_status === "DEVIATION" && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-amber-500/10 text-amber-600">
            <Activity className="w-4 h-4" />
            🟡 Deviation Detected
          </div>
        )}
        {sceneData.anomaly_status === "NORMAL" && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-[var(--success-green)]/10 text-[var(--success-green)]">
            <Shield className="w-4 h-4" />
            🟢 Normal Behavior
          </div>
        )}
      </div>

      {/* Primary Metrics */}
      <div className="grid grid-cols-2 gap-6">
        {/* Risk Score */}
        <Card className="p-6 bg-[var(--pure-white)] border-gray-200">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1.5 mb-4">
              <h3 className="text-sm font-medium text-[var(--slate-grey)]">
                Risk Score
              </h3>
              <InfoTooltip
                title={getMetricDefinition('risk_score')?.title || 'Risk Score'}
                description={getMetricDefinition('risk_score')?.description || 'Overall safety risk assessment for this driving scenario'}
                calculation={getMetricDefinition('risk_score')?.calculation}
                size="sm"
                position="auto"
              />
            </div>
            <div className="relative w-32 h-32 mx-auto">
              {sceneData.risk_score !== undefined ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="70%"
                    outerRadius="90%"
                    data={riskData}
                    startAngle={90}
                    endAngle={450}
                  >
                    <RadialBar
                      dataKey="value"
                      cornerRadius={10}
                      fill={riskData[0].fill}
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
              ) : (
                <div className="w-full h-full flex items-center justify-center border-2 border-gray-200 rounded-full">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--cyber-blue)]"></div>
                </div>
              )}
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold text-[var(--deep-charcoal)]">
                  {sceneData.risk_score !== undefined ? (sceneData.risk_score * 100).toFixed(0) : '--'}
                </span>
              </div>
            </div>
            <p className="text-xs text-[var(--slate-grey)] mt-2">
              {sceneData.risk_score >= 0.7 ? "High Risk" :
               sceneData.risk_score >= 0.4 ? "Medium Risk" : "Low Risk"}
            </p>
          </div>
        </Card>

        {/* Safety Score */}
        <Card className="p-6 bg-[var(--pure-white)] border-gray-200">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1.5 mb-4">
              <h3 className="text-sm font-medium text-[var(--slate-grey)]">
                Safety Score
              </h3>
              <InfoTooltip
                title={getMetricDefinition('safety_score')?.title || 'Safety Score'}
                description={getMetricDefinition('safety_score')?.description || 'How well the autonomous vehicle handled safety-critical aspects'}
                calculation={getMetricDefinition('safety_score')?.calculation}
                size="sm"
                position="auto"
              />
            </div>
            <div className="relative w-32 h-32 mx-auto">
              {sceneData.safety_score !== undefined ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="70%"
                    outerRadius="90%"
                    data={safetyData}
                    startAngle={90}
                    endAngle={450}
                  >
                    <RadialBar
                      dataKey="value"
                      cornerRadius={10}
                      fill="var(--success-green)"
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
              ) : (
                <div className="w-full h-full flex items-center justify-center border-2 border-gray-200 rounded-full">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--cyber-blue)]"></div>
                </div>
              )}
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold text-[var(--deep-charcoal)]">
                  {sceneData.safety_score !== undefined ? (sceneData.safety_score * 100).toFixed(0) : '--'}
                </span>
              </div>
            </div>
            <p className="text-xs text-[var(--slate-grey)] mt-2">
              Safety Compliance
            </p>
          </div>
        </Card>
      </div>


      {/* Removed duplicate Anomaly Analysis section - already shown in main Performance Metrics */}
    </div>
  )
}