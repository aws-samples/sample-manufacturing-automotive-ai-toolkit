/**
 * AuthProvider - Authentication Context Provider
 * 
 * Wraps the application to provide authentication state via React Context.
 * Use useAuthContext() hook to access auth state in child components.
 */
"use client"

import { createContext, useContext } from 'react'
import { useAuth } from '@/hooks/useAuth'

// Import Amplify configuration to initialize
import '@/lib/auth-config'

interface AuthUser {
  username: string
  email?: string
  userId: string
}

interface AuthContextType {
  user: AuthUser | null
  loading: boolean
  signOut: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuth()

  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthContext() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return context
}