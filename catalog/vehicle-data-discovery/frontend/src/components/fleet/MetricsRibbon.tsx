/**
 * MetricsRibbon - Fleet Statistics Display
 * 
 * Horizontal ribbon showing key fleet metrics: total scenes,
 * anomalies detected, DTO savings, and traffic light distribution.
 */
"use client"

import { motion } from "framer-motion"
import { Card } from "@/components/ui/card"
import { TrendingUp, AlertTriangle, DollarSign, Activity, AlertCircle, Clock, CheckCircle, LucideIcon } from "lucide-react"
import { useFleetStats } from "@/hooks/useFleetData"
import { useTrafficLightStats } from "@/hooks/useTrafficLightStats"
import InfoTooltip from "@/components/ui/InfoTooltip"

const MetricCard = ({
  title,
  value,
  suffix,
  icon: Icon,
  trend,
  color = "cyber-blue",
  delay = 0,
  tooltip
}: {
  title: string
  value: number | string
  suffix?: string
  icon: LucideIcon
  trend?: string
  color?: string
  delay?: number
  tooltip?: {
    title: string
    description: string
    calculation: string
  }
}) => {
  const colorClasses = {
    "cyber-blue": "text-[var(--cyber-blue)] bg-[var(--cyber-blue)]/10",
    "safety-orange": "text-[var(--safety-orange)] bg-[var(--safety-orange)]/10",
    "success-green": "text-[var(--success-green)] bg-[var(--success-green)]/10",
    "warning-amber": "text-[var(--warning-amber)] bg-[var(--warning-amber)]/10",
    "critical-red": "text-red-600 bg-red-50",
    "deviation-amber": "text-amber-600 bg-amber-50",
    "normal-green": "text-green-600 bg-green-50"
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="flex-1"
    >
      <Card className="p-6 bg-[var(--pure-white)] border-gray-200 hover:shadow-lg transition-shadow duration-300">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-[var(--slate-grey)] tracking-wide uppercase">
                {title}
              </p>
              {tooltip && (
                <InfoTooltip
                  title={tooltip.title}
                  description={tooltip.description}
                  calculation={tooltip.calculation}
                  size="sm"
                  position="auto"
                />
              )}
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-3xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
                {value}
              </span>
              {suffix && (
                <span className="text-lg text-[var(--slate-grey)]">
                  {suffix}
                </span>
              )}
            </div>
            {trend && (
              <div className="flex items-center gap-1 mt-2">
                <TrendingUp className="w-4 h-4 text-[var(--success-green)]" />
                <span className="text-sm text-[var(--success-green)]">
                  {trend}
                </span>
              </div>
            )}
          </div>
          <div className={`p-3 rounded-xl ${colorClasses[color as keyof typeof colorClasses]}`}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </Card>
    </motion.div>
  )
}

export default function MetricsRibbon() {
  const hookData = useFleetStats()
  const trafficLightData = useTrafficLightStats()
  const stats = hookData.stats
  const loading = hookData.loading || trafficLightData.loading
  const error = hookData.error || trafficLightData.error

  if (loading) {
    return (
      <div className="flex gap-6 mb-8">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex-1">
            <Card className="p-6 bg-[var(--pure-white)]">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-24 mb-4"></div>
                <div className="h-8 bg-gray-200 rounded w-16 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-20"></div>
              </div>
            </Card>
          </div>
        ))}
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="flex gap-6 mb-8">
        <Card className="p-6 bg-[var(--pure-white)] border-[var(--error-red)] flex-1">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[var(--error-red)]" />
            <span className="text-[var(--error-red)] font-medium">
              Unable to load metrics
            </span>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex gap-4 mb-8">
      <MetricCard
        title="Total Scenes"
        value={stats.scenarios_processed.toLocaleString()}
        icon={Activity}
        color="cyber-blue"
        delay={0}
      />

      {/* Apple-Grade Traffic Light System */}
      <MetricCard
        title="🔴 Critical"
        value={trafficLightData.stats?.critical?.count || 0}
        suffix={`(${trafficLightData.stats?.critical?.percentage || 0}%)`}
        icon={AlertCircle}
        color="critical-red"
        delay={0.1}
      />

      <MetricCard
        title="🟡 Deviation"
        value={trafficLightData.stats?.deviation?.count || 0}
        suffix={`(${trafficLightData.stats?.deviation?.percentage || 0}%)`}
        icon={Clock}
        color="deviation-amber"
        delay={0.15}
      />

      <MetricCard
        title="🟢 Normal"
        value={trafficLightData.stats?.normal?.count || 0}
        suffix={`(${trafficLightData.stats?.normal?.percentage || 0}%)`}
        icon={CheckCircle}
        color="normal-green"
        delay={0.2}
      />

      <MetricCard
        title="DTO Savings"
        value={`$${(stats.dto_savings_usd / 1000).toFixed(1)}`}
        suffix="K"
        icon={DollarSign}
        trend="+23% efficiency"
        color="success-green"
        delay={0.25}
        tooltip={{
          title: "Intelligent DTO Savings Calculation",
          description: "Advanced cost savings through vector similarity-based scenario analysis. Instead of transferring all scenes at $30/scene, we use semantic vector embeddings to discover natural ODD (Operational Design Domain) categories, analyze uniqueness within each category, and transfer only truly unique scenarios. This eliminates redundant data transfer costs.",
          calculation: "🧠 ODD Discovery: Uses HDBSCAN clustering with dual-vector embeddings (Cohere + Cosmos) to discover natural scenario categories. Each category analyzed for similarity patterns and safety risk levels. 🛡️ Safety-Weighted Analysis: Critical risk scenarios (>0.8) use zero-skip policy - all scenes must be tested regardless of similarity. High risk (0.5-0.8) requires minimum 80% testing. Routine scenarios (<0.5) can use similarity-based reduction. 💰 Cost Calculation: Formula = Count × max(Uniqueness, Safety_Multiplier). Prevents dangerous cost-cutting on safety-critical scenarios while optimizing routine data transfers. Saves costs through intelligent risk assessment, not blind similarity reduction."
        }}
      />

    </div>
  )
}