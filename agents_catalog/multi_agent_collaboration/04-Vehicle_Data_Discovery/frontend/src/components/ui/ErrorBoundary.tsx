/**
 * ErrorBoundary - React Error Boundary Component
 * 
 * Catches JavaScript errors in child components and displays
 * a fallback UI instead of crashing the entire application.
 */
"use client"

import { Component, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex flex-col items-center justify-center p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
          <h2 className="text-lg font-semibold text-gray-800 mb-2">Something went wrong</h2>
          <p className="text-gray-600 mb-4">An error occurred while rendering this section.</p>
          <Button 
            variant="outline" 
            onClick={() => this.setState({ hasError: false })}
          >
            Try Again
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
