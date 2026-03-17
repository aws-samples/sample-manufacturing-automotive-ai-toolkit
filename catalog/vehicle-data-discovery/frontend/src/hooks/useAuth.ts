/**
 * useAuth - Authentication state management hook
 * 
 * Manages user authentication state using AWS Amplify/Cognito.
 * Automatically checks for existing sessions on mount.
 * 
 * @returns {Object} Auth state and methods
 * @returns {AuthUser | null} user - Current authenticated user
 * @returns {boolean} loading - Auth check in progress
 * @returns {boolean} isAuthenticated - Whether user is logged in
 * @returns {Function} signOut - Sign out the current user
 * 
 * @example
 * const { user, isAuthenticated, signOut } = useAuth()
 * if (isAuthenticated) {
 *   console.log(`Logged in as ${user.username}`)
 * }
 */
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
      const currentUser = await getCurrentUser()

      // Extract user information from Cognito user
      const authUser: AuthUser = {
        username: currentUser.username,
        email: currentUser.signInDetails?.loginId,
        userId: currentUser.userId,
      }

      setUser(authUser)
    } catch (error) {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await signOut()
      setUser(null)

      // Redirect to login page
      window.location.href = '/login'
    } catch (error) {
    }
  }

  return {
    user,
    loading,
    signOut: handleSignOut,
    isAuthenticated: !!user,
  }
}