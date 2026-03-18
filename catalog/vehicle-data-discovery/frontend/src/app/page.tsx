/**
 * Home Page - Fleet Command Dashboard
 * 
 * Main entry point displaying the fleet overview with scene cards,
 * search functionality, and real-time metrics.
 * 
 * @route /
 */
import DashboardLayout from "@/components/layout/DashboardLayout"
import FleetCommand from "@/components/fleet/FleetCommand"
import ProtectedRoute from "@/components/auth/ProtectedRoute"

export default function Home() {
  return (
    <ProtectedRoute>
      <DashboardLayout>
        <FleetCommand />
      </DashboardLayout>
    </ProtectedRoute>
  )
}
