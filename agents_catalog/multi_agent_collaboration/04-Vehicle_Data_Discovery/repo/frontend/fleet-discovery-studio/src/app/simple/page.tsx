"use client"

import { useState, useEffect } from "react"
import DashboardLayout from "@/components/layout/DashboardLayout"

export default function SimplePage() {
  const [stats, setStats] = useState<any>(null)
  const [scenes, setScenes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadData() {
      try {
        console.log("Loading data...")

        // Fetch stats
        const statsRes = await fetch("/api/stats/overview")
        const statsData = await statsRes.json()
        setStats(statsData)
        console.log(" Stats loaded:", statsData)

        // Fetch scenes
        const scenesRes = await fetch("/api/fleet/overview")
        const scenesData = await scenesRes.json()
        setScenes(scenesData.slice(0, 8)) // First 8 scenes only
        console.log("Scenes loaded:", scenesData.length)

        setLoading(false)
        console.log("All data loaded successfully")
      } catch (err) {
        console.error("Load error:", err)
        setError(err instanceof Error ? err.message : "Load failed")
        setLoading(false)
      }
    }

    loadData()
  }, [])

  return (
    <DashboardLayout>
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-8">Simple Fleet Command</h1>

        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {loading ? (
            <>
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white rounded p-4 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded mb-2"></div>
                  <div className="h-8 bg-gray-200 rounded"></div>
                </div>
              ))}
            </>
          ) : stats ? (
            <>
              <div className="bg-white rounded p-4 border">
                <h3 className="text-sm text-gray-600">Total Scenes</h3>
                <p className="text-2xl font-bold">{stats.scenarios_processed}</p>
              </div>
              <div className="bg-white rounded p-4 border">
                <h3 className="text-sm text-gray-600">Anomalies</h3>
                <p className="text-2xl font-bold">{stats.anomalies_detected}</p>
              </div>
              <div className="bg-white rounded p-4 border">
                <h3 className="text-sm text-gray-600">DTO Savings</h3>
                <p className="text-2xl font-bold">${(stats.dto_savings_usd / 1000).toFixed(0)}K</p>
              </div>
              <div className="bg-white rounded p-4 border">
                <h3 className="text-sm text-gray-600">Status</h3>
                <p className="text-2xl font-bold text-green-600">{stats.status}</p>
              </div>
            </>
          ) : error ? (
            <div className="col-span-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              Error: {error}
            </div>
          ) : null}
        </div>

        {/* Scenes Grid */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Recent Scenes</h2>
          {loading ? (
            <div className="grid grid-cols-4 gap-4">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="bg-white rounded p-4 animate-pulse">
                  <div className="h-32 bg-gray-200 rounded mb-2"></div>
                  <div className="h-4 bg-gray-200 rounded mb-1"></div>
                  <div className="h-3 bg-gray-200 rounded"></div>
                </div>
              ))}
            </div>
          ) : scenes.length > 0 ? (
            <div className="grid grid-cols-4 gap-4">
              {scenes.map((scene) => (
                <div key={scene.scene_id} className="bg-white rounded p-4 border hover:shadow-lg transition-shadow">
                  <div className="h-32 bg-gradient-to-br from-gray-800 to-gray-900 rounded mb-2 flex items-center justify-center text-white">
                    📹 {scene.scene_id}
                  </div>
                  <h3 className="font-medium text-sm mb-1">{scene.scene_id}</h3>
                  <p className="text-xs text-gray-600 mb-2">Risk: {(scene.risk_score * 100).toFixed(0)}%</p>
                  <div className="flex flex-wrap gap-1">
                    {scene.tags?.slice(0, 2).map((tag: string, i: number) => (
                      <span key={i} className="text-xs bg-gray-100 px-2 py-1 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              Error loading scenes: {error}
            </div>
          ) : (
            <p>No scenes found</p>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}