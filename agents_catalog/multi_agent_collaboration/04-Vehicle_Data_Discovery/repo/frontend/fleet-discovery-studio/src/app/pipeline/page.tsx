"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Database, Play, CheckCircle, Clock, AlertCircle, RefreshCw } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import DashboardLayout from "@/components/layout/DashboardLayout"
import RosBagUpload from "@/components/upload/RosBagUpload"

interface PipelineExecution {
  execution_id: string
  status: "RUNNING" | "SUCCEEDED" | "FAILED"
  start_date: string
  scene_id: string
  state_machine: string
  current_phase?: number
  phase_number?: number
}

interface PipelineData {
  executions: PipelineExecution[]
  total_running: number
  state_machine_arn: string
}

interface StatsData {
  scenarios_processed: number
  dto_savings_usd: number
  anomalies_detected: number
  status: string
}

export default function PipelinePage() {
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null)
  const [statsData, setStatsData] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  const fetchData = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api'
      const [pipelineResponse, statsResponse] = await Promise.all([
        fetch(`${apiUrl}/pipeline/executions`),
        fetch(`${apiUrl}/stats/overview`)
      ])

      const pipelineResult = await pipelineResponse.json()
      const statsResult = await statsResponse.json()

      setPipelineData(pipelineResult)
      setStatsData(statsResult)
      setLastUpdated(new Date())
    } catch (error) {
      console.error('Error fetching pipeline data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Dynamic refresh rate: faster when pipeline is active
    const getRefreshInterval = () => {
      return (pipelineData?.total_running ?? 0) > 0 ? 5000 : 15000  // 5s when active, 15s when idle
    }

    const interval = setInterval(fetchData, getRefreshInterval())
    return () => clearInterval(interval)
  }, [pipelineData?.total_running])

  const handleRefresh = () => {
    setLoading(true)
    fetchData()
  }

  const currentExecution = pipelineData?.executions?.find(exec => exec.status === "RUNNING")
  const recentExecutions = pipelineData?.executions?.slice(0, 5) || []

  // Determine which phase is currently active based on real Step Functions data
  const getPhaseStatus = (phaseNumber: number) => {
    if (!currentExecution || currentExecution.status !== "RUNNING") {
      // No running execution - all phases should be idle
      return "IDLE"
    }

    // Use phase_number (actual number) for comparison logic
    const currentPhase = currentExecution.phase_number || 1

    if (phaseNumber < currentPhase) return "COMPLETE"
    if (phaseNumber === currentPhase) return "ACTIVE"
    return "IDLE"
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString()
  }

  const formatDuration = (startDate: string) => {
    const start = new Date(startDate)
    const now = new Date()
    const diffMinutes = Math.floor((now.getTime() - start.getTime()) / (1000 * 60))
    return `${diffMinutes}m`
  }

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-xl flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
                Data Pipeline
              </h1>
              <p className="text-[var(--slate-grey)] mt-1">
                6-Phase processing pipeline status and monitoring
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge className={`${(pipelineData?.total_running ?? 0) > 0 ? 'bg-[var(--success-green)]' : 'bg-[var(--slate-grey)]'} text-white`}>
              <Play className="w-3 h-3 mr-1" />
              {(pipelineData?.total_running ?? 0) > 0 ? 'Active' : 'Idle'}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={loading}
              className="bg-[var(--pure-white)] border-gray-300 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)]"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </motion.div>

        {/* Upload Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <RosBagUpload />
        </motion.div>

        {/* Current Execution Status - Only show if actually running */}
        {currentExecution && currentExecution.status === "RUNNING" && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="p-6 bg-gradient-to-r from-[var(--cyber-blue)]/10 to-purple-500/10 border-[var(--cyber-blue)]/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-[var(--cyber-blue)] rounded-full flex items-center justify-center animate-pulse">
                    <Play className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
                      Currently Processing
                    </h3>
                    <p className="text-[var(--slate-grey)]">
                      {currentExecution.scene_id} • Started {formatDate(currentExecution.start_date)} • {formatDuration(currentExecution.start_date)} running
                    </p>
                  </div>
                </div>
                {(() => {
                  // Use phase_number (actual number) for display
                  const activePhase = currentExecution.phase_number || 1
                  const phaseNames = ["", "ROS Extraction", "Video Reconstruction", "InternVideo Analysis", "S3 Vectors", "Vector Storage", "Agent Analysis"]
                  return (
                    <Badge className="bg-[var(--cyber-blue)] text-white px-3 py-1">
                      Phase {activePhase}: {phaseNames[activePhase] || "Processing"}
                    </Badge>
                  )
                })()}
              </div>
            </Card>
          </motion.div>
        )}

        {/* Pipeline Phases */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {[
            { phase: 1, title: "ROS Extraction", desc: "Multi-sensor data extraction from ROS bags" },
            { phase: 2, title: "Video Reconstruction", desc: "6-camera MP4 generation from binary data" },
            { phase: 3, title: "InternVideo Analysis", desc: "Multi-camera behavioral understanding" },
            { phase: 4, title: "S3 Vectors", desc: "Semantic embeddings generation" },
            { phase: 5, title: "Vector Storage", desc: "Behavioral embeddings indexed" },
            { phase: 6, title: "Agent Analysis", desc: "Multi-agent scene understanding" },
          ].map(({ phase, title, desc }, index) => {
            const status = getPhaseStatus(phase)
            const isActive = status === "ACTIVE"
            const isComplete = status === "COMPLETE"

            return (
              <motion.div
                key={phase}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 * index }}
              >
                <Card className={`p-6 bg-[var(--pure-white)] ${isActive ? 'ring-2 ring-[var(--cyber-blue)]/50' : ''}`}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      isActive ? 'bg-[var(--cyber-blue)] animate-pulse' :
                      isComplete ? 'bg-[var(--success-green)]' : 'bg-[var(--slate-grey)]'
                    }`}>
                      {isActive ? (
                        <Clock className="w-4 h-4 text-white" />
                      ) : isComplete ? (
                        <CheckCircle className="w-4 h-4 text-white" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-white" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-[var(--deep-charcoal)]">Phase {phase}: {title}</h3>
                      <p className={`text-xs font-medium ${
                        isActive ? 'text-[var(--cyber-blue)]' :
                        isComplete ? 'text-[var(--success-green)]' : 'text-[var(--slate-grey)]'
                      }`}>
                        {status}
                      </p>
                    </div>
                  </div>
                  <p className="text-sm text-[var(--slate-grey)]">
                    {desc}
                  </p>
                </Card>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Current Status */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="p-8 bg-[var(--pure-white)]">
            <div className="text-center">
              <Database className="w-12 h-12 text-[var(--cyber-blue)] mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-[var(--deep-charcoal)] mb-2">
                Pipeline Status: {statsData?.status === 'active' ? 'Operational' : 'Idle'}
              </h3>
              <p className="text-[var(--slate-grey)] mb-4">
                Processing {statsData?.scenarios_processed || 0} scenarios with {statsData?.anomalies_detected || 0} anomalies detected
              </p>
              <div className="flex justify-center gap-4">
                <Badge className="bg-[var(--success-green)] text-white">
                  ${((statsData?.dto_savings_usd || 0) / 1000).toFixed(1)}K DTO Savings
                </Badge>
                <Badge className="bg-[var(--cyber-blue)] text-white">
                  {pipelineData?.total_running ?? 0} Running
                </Badge>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Recent Executions */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <Card className="p-6 bg-[var(--pure-white)]">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
                Recent Executions
              </h3>
              <p className="text-sm text-[var(--slate-grey)]">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </p>
            </div>
            <div className="space-y-3">
              {recentExecutions.map((execution, index) => (
                <motion.div
                  key={execution.execution_id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 * index }}
                  className="flex items-center justify-between p-3 bg-[var(--soft-grey)] rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${
                      execution.status === 'RUNNING' ? 'bg-[var(--cyber-blue)] animate-pulse' :
                      execution.status === 'SUCCEEDED' ? 'bg-[var(--success-green)]' : 'bg-[var(--safety-orange)]'
                    }`} />
                    <div>
                      <p className="font-medium text-[var(--deep-charcoal)]">
                        {execution.scene_id}
                      </p>
                      <p className="text-sm text-[var(--slate-grey)]">
                        Started {formatDate(execution.start_date)}
                        {execution.status === 'RUNNING' && ` • ${formatDuration(execution.start_date)} running`}
                      </p>
                    </div>
                  </div>
                  <Badge variant={
                    execution.status === 'RUNNING' ? 'default' :
                    execution.status === 'SUCCEEDED' ? 'secondary' : 'destructive'
                  } className={
                    execution.status === 'RUNNING' ? 'bg-[var(--cyber-blue)]' :
                    execution.status === 'SUCCEEDED' ? 'bg-[var(--success-green)]' : 'bg-[var(--safety-orange)]'
                  }>
                    {execution.status}
                  </Badge>
                </motion.div>
              ))}
            </div>
          </Card>
        </motion.div>
      </div>
    </DashboardLayout>
  )
}