/**
 * api - Shared API Client
 *
 * Centralized API client with error handling, base URL configuration,
 * and typed request/response helpers.
 */

import '@/lib/auth-config' // Ensure Amplify is configured before any auth calls
import { fetchAuthSession } from 'aws-amplify/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const session = await fetchAuthSession()
    const token = session.tokens?.idToken?.toString()
    if (token) return { Authorization: `Bearer ${token}` }
    console.warn('[auth] No ID token in session:', JSON.stringify({ hasTokens: !!session.tokens, hasIdToken: !!session.tokens?.idToken }))
  } catch (e) {
    console.warn('[auth] fetchAuthSession failed:', e)
  }
  return {}
}

export async function authenticatedFetch(url: string, options?: RequestInit): Promise<Response> {
  const authHeaders = await getAuthHeaders()
  return fetch(url, {
    ...options,
    headers: { ...options?.headers, ...authHeaders }
  })
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const response = await authenticatedFetch(`${API_BASE_URL}${endpoint}`)
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.status}`)
  }
  return response.json()
}

export async function apiPost<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await authenticatedFetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.status}`)
  }
  return response.json()
}

export { API_BASE_URL }
