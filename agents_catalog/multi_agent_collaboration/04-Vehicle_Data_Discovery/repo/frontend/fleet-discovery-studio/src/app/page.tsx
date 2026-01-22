import DashboardLayout from "@/components/layout/DashboardLayout"
import FleetCommand from "@/components/fleet/FleetCommand"
import ProtectedRoute from "@/components/auth/ProtectedRoute"

// Skip SSR data fetching for CloudFront deployment - use client-side only
async function fetchFleetData() {
  console.log("SSR: Skipping server-side data fetch for CloudFront deployment...")

  // Return empty data to let client-side hooks handle all fetching
  const stats = null
  const fleetData = {
    scenes: [],
    total_count: 0,
    page: 1,
    limit: 20
  }

  console.log("SSR: Returning empty data - client-side hooks will fetch real data")
  return { stats, fleetData, error: null }
}

export default async function Home() {
  const { stats, fleetData, error } = await fetchFleetData()

  return (
    <ProtectedRoute>
      <DashboardLayout>
        <FleetCommand
          initialStats={stats}
          initialFleetData={fleetData}
          initialError={error}
        />
      </DashboardLayout>
    </ProtectedRoute>
  )
}
