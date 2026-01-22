"use client"

import { useAuthContext } from './AuthProvider'
import LoginPage from '@/app/login/page'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuthContext()

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[var(--deep-charcoal)] via-gray-900 to-black flex items-center justify-center">
        <div className="text-center">
          {/* Fleet Loading Animation */}
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 border-2 border-[var(--cyber-blue)] border-t-transparent rounded-full animate-spin"></div>
            <div className="absolute inset-2 border-2 border-purple-500 border-t-transparent rounded-full animate-spin animate-reverse"></div>
          </div>
          <p className="text-white/70 text-sm">Connecting to Fleet Discovery...</p>
        </div>
      </div>
    )
  }

  // Show login page if user is not authenticated
  if (!user) {
    return <LoginPage />
  }

  // Render protected content
  return <>{children}</>
}