'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function NotFound() {
  const router = useRouter()

  useEffect(() => {
    // For static export SPA fallback - handle direct navigation to dynamic routes
    if (typeof window !== 'undefined') {
      const currentPath = window.location.pathname + window.location.search + window.location.hash

      // If we're on a known route that should exist, try to navigate there
      const knownRoutes = ['/forensic', '/analytics', '/pipeline', '/search', '/settings']
      const isKnownRoute = knownRoutes.some(route => currentPath.startsWith(route))

      if (isKnownRoute) {
        // Use router.replace to navigate to the intended route
        router.replace(currentPath)
      }
    }
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8 text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Page Not Found</h2>
        <p className="text-gray-600 mb-6">
          The page you are looking for might have been removed or is temporarily unavailable.
        </p>
        <button
          onClick={() => router.push('/')}
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
        >
          Go to Home
        </button>
      </div>
    </div>
  )
}