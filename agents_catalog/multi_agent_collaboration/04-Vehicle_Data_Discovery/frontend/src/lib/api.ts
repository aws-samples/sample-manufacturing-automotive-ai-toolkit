/**
 * api - Shared API Client
 * 
 * Centralized API client with error handling, base URL configuration,
 * and typed request/response helpers.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`)
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.status}`)
  }
  return response.json()
}

export async function apiPost<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
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
