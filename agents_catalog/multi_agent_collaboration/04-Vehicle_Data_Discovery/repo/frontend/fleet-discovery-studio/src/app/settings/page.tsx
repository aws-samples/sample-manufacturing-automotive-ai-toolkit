"use client"

import { motion } from "framer-motion"
import { Settings as SettingsIcon, Brain, Target, DollarSign, Shield } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import DashboardLayout from "@/components/layout/DashboardLayout"
import ProtectedRoute from "@/components/auth/ProtectedRoute"

export default function SettingsPage() {
  return (
    <ProtectedRoute>
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
            <SettingsIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
              System Settings
            </h1>
            <p className="text-[var(--slate-grey)] mt-1">
              Configure agents, thresholds, and business objectives
            </p>
          </div>
        </div>
      </motion.div>

      {/* Settings Categories */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Agent Configuration */}
        <Card className="p-6 bg-[var(--pure-white)]">
          <div className="flex items-center gap-3 mb-4">
            <Brain className="w-6 h-6 text-[var(--cyber-blue)]" />
            <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
              Agent Configuration
            </h3>
          </div>
          <p className="text-sm text-[var(--slate-grey)] mb-4">
            Configure the 3-agent system: Scene Understanding, Anomaly Detection, and Similarity Search
          </p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Scene Understanding Agent</span>
              <span className="text-xs bg-[var(--success-green)] text-white px-2 py-1 rounded">Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Anomaly Detection Agent</span>
              <span className="text-xs bg-[var(--success-green)] text-white px-2 py-1 rounded">Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Similarity Search Agent</span>
              <span className="text-xs bg-[var(--success-green)] text-white px-2 py-1 rounded">Active</span>
            </div>
          </div>
          <Button
            className="w-full mt-4 bg-gray-400 text-white cursor-not-allowed opacity-70"
            disabled
          >
            Configure Agents - Coming Soon
          </Button>
        </Card>

        {/* Risk Thresholds */}
        <Card className="p-6 bg-[var(--pure-white)]">
          <div className="flex items-center gap-3 mb-4">
            <Target className="w-6 h-6 text-[var(--safety-orange)]" />
            <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
              Risk Thresholds
            </h3>
          </div>
          <p className="text-sm text-[var(--slate-grey)] mb-4">
            Set risk score thresholds for HIL priority classification
          </p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">High Priority Threshold</span>
              <span className="text-sm font-mono text-[var(--safety-orange)]">≥ 0.3</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Medium Priority Threshold</span>
              <span className="text-sm font-mono text-[var(--warning-amber)]">≥ 0.15</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Low Priority (DTO Savings)</span>
              <span className="text-sm font-mono text-[var(--success-green)]">&lt; 0.15</span>
            </div>
          </div>
          <Button
            className="w-full mt-4 bg-gray-400 text-white cursor-not-allowed opacity-70"
            disabled
          >
            Adjust Thresholds - Coming Soon
          </Button>
        </Card>

        {/* Business Objectives */}
        <Card className="p-6 bg-[var(--pure-white)]">
          <div className="flex items-center gap-3 mb-4">
            <DollarSign className="w-6 h-6 text-[var(--success-green)]" />
            <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
              Business Objectives
            </h3>
          </div>
          <p className="text-sm text-[var(--slate-grey)] mb-4">
            Current objective: Optimize HIL scenario discovery and reduce DTO costs
          </p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">DTO Cost per Scene</span>
              <span className="text-sm font-mono text-[var(--success-green)]">$950</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Current Savings</span>
              <span className="text-sm font-mono text-[var(--success-green)]">$62.7K</span>
            </div>
          </div>
          <Button
            className="w-full mt-4 bg-gray-400 text-white cursor-not-allowed opacity-70"
            disabled
          >
            Update Objectives - Coming Soon
          </Button>
        </Card>

        {/* System Status */}
        <Card className="p-6 bg-[var(--pure-white)]">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-6 h-6 text-[var(--cyber-blue)]" />
            <h3 className="text-lg font-semibold text-[var(--deep-charcoal)]">
              System Status
            </h3>
          </div>
          <p className="text-sm text-[var(--slate-grey)] mb-4">
            Overall system health and performance metrics
          </p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Pipeline Status</span>
              <span className="text-xs bg-[var(--success-green)] text-white px-2 py-1 rounded">Operational</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Processing Rate</span>
              <span className="text-sm font-mono text-[var(--cyber-blue)]">2.8 scenes/hr</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--deep-charcoal)]">Total Scenarios</span>
              <span className="text-sm font-mono text-[var(--deep-charcoal)]">66</span>
            </div>
          </div>
          <Button
            className="w-full mt-4 bg-gray-400 text-white cursor-not-allowed opacity-70"
            disabled
          >
            System Diagnostics - Coming Soon
          </Button>
        </Card>
      </div>

      {/* Configuration Note */}
      <Card className="p-8 bg-[var(--cyber-blue)]/5 border-[var(--cyber-blue)]/20">
        <div className="text-center">
          <SettingsIcon className="w-12 h-12 text-[var(--cyber-blue)] mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-[var(--deep-charcoal)] mb-2">
            Advanced Configuration Available
          </h3>
          <p className="text-[var(--slate-grey)]">
            Fine-tune agent behaviors, customize business logic, and optimize pipeline performance through the configuration API.
          </p>
        </div>
      </Card>
        </div>
      </DashboardLayout>
    </ProtectedRoute>
  )
}