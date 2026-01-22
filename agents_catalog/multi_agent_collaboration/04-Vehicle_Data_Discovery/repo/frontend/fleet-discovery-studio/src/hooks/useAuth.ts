"use client"

import { useState, useEffect } from 'react'
import { getCurrentUser, signOut } from 'aws-amplify/auth'

interface AuthUser {
  username: string
  email?: string
  userId: string
}

interface UseAuthReturn {
  user: AuthUser | null
  loading: boolean
  signOut: () => Promise<void>
  isAuthenticated: boolean
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuthState()
  }, [])

  const checkAuthState = async () => {
    try {
      console.log(" Checking authentication state...")
      const currentUser = await getCurrentUser()
      console.log("User authenticated:", currentUser.username)

      // Extract user information from Cognito user
      const authUser: AuthUser = {
        username: currentUser.username,
        email: currentUser.signInDetails?.loginId,
        userId: currentUser.userId,
      }

      setUser(authUser)
    } catch (error) {
      console.log(" User not authenticated:", error)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSignOut = async () => {
    try {
      console.log("Signing out user...")
      await signOut()
      setUser(null)
      console.log("User signed out successfully")

      // Redirect to login page
      window.location.href = '/login'
    } catch (error) {
      console.error(" Error signing out:", error)
    }
  }

  return {
    user,
    loading,
    signOut: handleSignOut,
    isAuthenticated: !!user,
  }
}